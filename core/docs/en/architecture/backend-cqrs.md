# Backend Architecture — Conceptual Model

> Canonical source: strata-kit `core/docs/en/architecture/backend-cqrs.md`. The machine-readable rules are in `core/rules/layer-rules.yaml`; the reason for building the structure up front is in `core/docs/en/architecture/prepaid-structure.md`.
> Revised 2026-10-29 — split the language-independent conceptual model from the per-language projections (DEC-2026-10-29-06), reflected the meaning of same-layer references (DEC-2026-09-30-04, strata), and aligned the L3 suffix to CompositeService (DEC-2026-10-29-05).

## Summary

- This document defines only what is **the same in every language**: the role of each layer, the dependency direction, the ban on same-tier references, and the separation of commands and queries. Directory, package and module layout, names, and enforcement tools are defined by the **per-language projection documents** (table at the bottom).
- Layers reference only from bottom to top: L1 → LM1 → L2 → LM2 → L3 → Route. Logic layers (the L2 service tier, LM2, L3) do not reference **elements of the same tier** among themselves.
- L2 has two tiers. The lower tier is data access (Repository, DSL Template); the upper tier is services (Command, Query). A service uses the lower tier, and elements of the same tier do not use each other.
- When reuse is needed, add an LM2 Coordinator. The criterion for grouping is not "is it reused" but **"is it the same domain concern"**. Pure computation that needs no injection is pulled out into a pure object outside any tier.
- A projection follows the framework and idioms best supported in that camp. Layers are not enforced through directory names. A layer is a **role**, and the language decides what physical structure expresses it.

## Layers

| Layer | Role | May reference | Reference within the same layer |
|---|---|---|---|
| L1 Component | Framework-independent pure functions, constants, types. Common, domain, utility | None | Allowed (common utilities) |
| LM1 Inherite | Common foundation injected into L2 — audit-field Base Entity, DB and cache connection settings, common Repository interfaces, transaction foundation | L1 | Allowed |
| L2 DataLayer | Per-domain data access. **Lower tier** Repository, DSL Template; **upper tier** CommandService, QueryService | L1, LM1 | The lower tier does not know the upper tier. Same-tier references are forbidden |
| LM2 Coordinate | Reusable business flow that bundles a combination of L2 elements for the same domain concern | L2 | Forbidden |
| L3 Composite | One use case. CompositeService, Listener (events), Task (schedules) | LM2, L2 | Forbidden |
| Route Controller | Receives HTTP, validates, injects auth context, converts responses, maps errors | L3 | Allowed (common middleware) |

### L1 Component

Pure functions, constants and types that do not depend on a framework. Examples: date utilities, validation rules, error codes, page types, sort directions. They divide into common (all domains), domain-specific, and general-purpose utilities.

### LM1 Inherite

The foundation that L2 inherits or has injected. Base Entity (audit fields such as createdAt, updatedAt, createdBy), DB and cache connection settings, common Repository interfaces, transaction management foundation.

### L2 DataLayer — two tiers

| Tier | Elements | Rule |
|---|---|---|
| Lower tier — data access | `Repository` (implements an ORM or ODM interface), `Template` (complex DSL-based queries) | Does not reference the upper tier. Repository and Template do not reference each other either |
| Upper tier — services | `CommandService` (create, update, delete; transactions), `QueryService` (read-only) | Uses the lower tier. A service must not reference another service |

- One function handles only one entity. Combining multiple entities is the responsibility of LM2 and L3.
- The query side may join several tables and return a DTO directly. The read model need not go through the domain model.

### LM2 Coordinate

Place it when a combination of L2 calls belonging to the same domain concern is used by several L3 elements. The criterion for grouping is not the number of reuses but **whether the domain concern is the same** — do not put different concerns into one Coordinator just because "they are called together". Examples: `PaymentCoordinator` (the common flow of payment processing), `ReviewCoordinator` (the approval-line flow of the review domain).

### L3 Composite

Performs one use case.

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — if the action must be visible, `{Domain}{Action}CompositeService` (example: `EmissionManageCompositeService`)
- `{Domain}Listener` — event-driven background processing
- `{Domain}Task` — schedule-driven background processing

"Create order" = `OrderCommandCompositeService.createOrder()`. One CompositeService corresponds to one group of use cases.

### Route Controller

Maps URIs, validates request parameters and bodies, injects authentication and authorization context, converts to response DTOs, and maps errors to HTTP statuses. **A Controller does not call L2 directly** — even the simplest CRUD goes through L3. Listeners and scheduled Tasks are also entry points that call the same L3, so adding entry adapters leaves the use-case code unchanged.

## Pure computation

Computation that needs no injection, such as unit conversion or formula evaluation, is not placed in any tier but pulled out into a **pure object without injection** (Kotlin `object`, Go package function, Rust free function, TS module function). That way, the ban on same-tier references never forces you to duplicate the computation or to create a Coordinator artificially.

## Dependency direction

```
Route_Controller
    ↓ (L3 only)
L3_Composite
    ↓ (LM2 or L2)
LM2_Coordinate
    ↓ (L2 only)
L2_DataLayer   upper tier Command·Query → lower tier Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

References against the arrow direction are forbidden. Same-tier references among logic layers are also forbidden.

## Commands and queries

The separation of commands and queries is **not a microservice split but a separation of paths within the same process**.

- The query path has no side effects, so moving it to or swapping in another store (replica, cache, external table, view) is cheap.
- The transaction boundary of the command path becomes the natural dividing line when services are split.
- If the two are separated from the start, the layers barely change when moving from a monolith to multiple deployment units (prepaid-structure).

## Variants

Both variants share the same layer direction and differ only in how the L2 write side is handled. A project picks one through `variant` in `layer-map.yaml` (`cqrs` if absent).

| | CQRS (default) | ES-CQRS |
|---|---|---|
| Source of truth | Current rows in the DB | Event log |
| L2 write side | CommandService | Aggregate → EventStore (ES Track) |
| L2 read side | QueryService | QueryService (same) |
| Additional components | None | Aggregate, EventStore, Projection |
| Fits | Ordinary CRUD, simple domains | Audit trails, bitemporal needs, event-driven domains |

### ES-CQRS

ES-CQRS replaces the L2 write side with the ES Track. A command flows L3 → Aggregate (emits events) → EventStore (persists) → Projection (updates the read model) → L2 QueryService, and a query flows L3 → L2 QueryService.

| Component | Rule |
|---|---|
| Aggregate | The domain model that emits events. References only L1 and does not reference other Aggregates directly (they communicate through a Saga or ProcessManager). Creates events after validating invariants |
| EventStore | References only L1 and LM1. Does not reference Aggregate or Projection directly. PG + JSONB by default, snapshots when needed |
| Projection | The only bridge between the ES Track and the layers. Synchronous (inline) or asynchronous (outbox) |

| Rule | Content | Scope |
|---|---|---|
| R1 | The command entry point must go through an L3 CompositeService | both |
| R2 | An Aggregate does not import any layer other than L1 | es-cqrs |
| R3 | The L2 DataLayer is read-only (no CommandService) | es-cqrs |
| R4 | The Projection is the only bridge from ES to the read model | es-cqrs |
| R5 | No direct references between Aggregates (communicate through a Saga) | es-cqrs |
| R6 | Rebase policy lives at the Projection level (the Aggregate does not know the policy) | es-cqrs |

The infrastructure level is chosen in stages: inline projection using PG only (no extra cost, immediate consistency) → PG outbox + in-process worker → message broker → per-service EventStore + broker.

## Per-language projections

The same layer meaning is carried into each language's best-supported structure. There are three common principles — the **deployment/module unit comes first** (modules by feature or domain), layers are expressed inside it as **roles (files, types, suffixes)**, and boundaries are blocked by **that language's compiler, package system and linter**.

| Language | Representative stack | Module unit | Layer expression | Boundary enforcement | Document |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Gradle module (entity, service) | Package + suffix (CommandService, CompositeService) | ArchUnit (reads this rule YAML at runtime), Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/en/backend-kotlin-spring.md` |
| Go | Standard `net/http` (1.22 routing) · `pgx` · `sqlc` | Feature package (`internal/<domain>/`) | Role files inside the package (`command.go`, `query.go`, `store.go`, `http.go`) | No import cycles (compiler), `internal/`, `depguard`, `go-arch-lint` | `profiles/backend.go-service/docs/en/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Cargo workspace crate | Crates (domain, app, infra, api) and modules, `pub(crate)` | `Cargo.toml` dependency direction (compile time), visibility | `profiles/service.rust/docs/en/backend-rust-layers.md` |
| TypeScript | NestJS · (Prisma or TypeORM) | Nest module (per domain) | Provider suffix and module `exports` | Nest DI (a provider that is not exported cannot be injected), `dependency-cruiser` | `profiles/backend.typescript-nest/docs/en/backend-nest.md` |

The `language_patterns` of the machine-readable rules (`core/rules/layer-rules.yaml`) carry four projections — kotlin, go, rust, typescript — and L2 declares its two tiers through `tiers` (lower, upper) (order 2026.10.29-07 task-04, cross-checked 2026-10-29). What the enforcement tools read today is only the kotlin projection (the ArchUnit template) and the layer-level `can_reference` and `cross_reference`, so `tiers` and the ban on same-tier references within the same domain are still declarations — enforcement will be added in a separate change after measurement.

## Extensions pending a decision (analysis stage)

The following three from the 2026-10-29 analysis are not yet decisions. Once decided, they will be reflected in this document and in the projection documents.

- **Public contract of a module** — other modules see only the contract (interfaces, dedicated types, events). Move the remote-call interfaces that now live on the consumer side to the provider side and detach them from the transport.
- **Write unit as the aggregate** — change the L2 write side from "one entity" to "one aggregate", and hide entity-level writes behind module visibility. Handle it together with the two L2 tiers above.
- **Module ownership of migration history** — a module owns its schema and history tables, and DB dependencies between modules go only through public views.
