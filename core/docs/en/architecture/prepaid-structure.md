# The Prepaid Structure Principle

> Canonical source: strata-kit `core/docs/en/architecture/prepaid-structure.md` — migrated from strata `docs/03-architecture/prepaid-structure.md` (order 2026.10.29-06, 2026-10-29). The rule YAML is in `core/rules/`.

> Machine-readable source of the layer rules: `core/rules/layer-rules.yaml` / per-layer description: `core/docs/en/architecture/backend-cqrs.md`
> This document is the higher-level principle explaining "why the structure is built up front". (DEC-2026-09-30-01, strata)

## Summary

- **Principle:** If the structural cost paid now sufficiently offsets the cost of later changes, build that structure from the start. A structure that does not offset it is not built until it is needed.
- **There are three criteria:** the cost now, the cost when that change becomes necessary later, and the likelihood that the change actually happens.
- **Do not reduce layers according to scale.** The layer roles and the dependency direction are the same at every scale. Only the number of domains and the deployment units vary with scale.
- **The goal is that layers barely change when moving from a monolith to MSA.** The costs that layers cannot cover concentrate in three places — data ownership, writes across domains, and reads across domains — so the rules for these three are also fixed in advance.
- **A prepaid structure is maintained only by enforcement.** A boundary that neither the compiler nor CI blocks leaks little by little over time, and the value paid in advance disappears with it.

## Verdict list

### Structures always put in place

| Structure | Cost now | Change cost it offsets |
|---|---|---|
| Layer roles and one-directional dependency | The effort of fitting file placement and call paths to the rules | The cost of being unable to predict what comes along when a feature is moved or split out |
| Services split into command and query (CQS) | Service files double and the transaction location must be kept in mind | The cost of having to tear up the write code when detaching the read model or moving it to a cache or replica |
| Build modules split into entity modules and service modules | Build configuration, inter-module dependency declarations, and the complexity of transactions and sync/async handling | The cost of drawing code boundaries anew when separating services. The modules themselves become candidate deployment units |
| Ports and adapters at external-system boundaries (DB, messaging, external APIs) | One interface and one implementation per boundary | The cost of replacing an external system, or of turning an in-process call into a network call |

### Structures put in place only when needed

| Structure | When to put it in place |
|---|---|
| Event sourcing (`es-cqrs` variant) | When audit trails, reconstruction of past points in time, or event replay are confirmed as requirements |
| Separate read store | When the query load or the query model has actually diverged from the write model |

### Structures not put in place

| Structure | Reason |
|---|---|
| Interface abstractions at every internal layer | Internal implementations are rarely replaced, so there is no change cost to offset. The layer direction rule alone achieves the same effect |
| A full hexagonal architecture | Ports and adapters produce value only at external boundaries. Extending them inside only increases cost |

## Three boundaries the layers do not cover

When a service is split out of a monolith, the layer code moves almost unchanged. The remaining cost arises in the three places below. These three are fixed as rules from the start.

### Data ownership

- One table is owned by one entity module. The table's schema change history (changelog) is also owned by that module.
- Other modules do not write to that table directly. Writes go through the owning module's command service.
- Reason: when splitting services, the cost of dividing the DB grows the more scattered "who writes to which table" is.

### Writes across domains

- Do not bind the writes of two domains into one transaction. After one domain's write completes, publish an event, and the other domain receives that event and performs its own write.
- The publication record is saved together within the transaction (outbox approach, e.g. the Spring Modulith event publication table). The point that changes from in-process delivery in a monolith to broker delivery in MSA then becomes this single place.
- Reason: two domains bound in one transaction become a distributed-transaction problem the moment they are split into services.

### Reads across domains

- The path for reading another domain's data is fixed to one place per domain. Choose one of a read-only window (a query service or a coordination layer) or a DB-level foreign-table lookup (FDW, etc.), and do not mix them.
- Do not use another domain's entity types directly. Receive query results as types of your own domain.
- Reason: if the read path is a single place, splitting the services only requires changing that one place to a network query.

## Scale and deployment units

- Even a small project has the same layer and module structure. If there is only one domain, there is simply one domain module.
- The difference between a monolith and MSA is viewed as "how many modules are bundled into one process for deployment". Moving a module to another process amounts to changing the delivery method of the three boundaries above.
- Depending on budget and operating conditions, deployment units can be merged or split at any time. As long as the layer and module boundaries are kept, this choice is not a decision to redo the code structure.

## Cheap compile-time boundaries per language

The way to lower the prepaid cost the most is to use the boundaries that the language and its build tools already provide. Each language binding states "what makes the module boundary, and what blocks the layer direction inside a module".

| Language | Module boundary (compiler-enforced) | Layer direction inside a module | Cycles |
|---|---|---|---|
| Kotlin / Java | Gradle multi-module (`implementation` by default) | ArchUnit (blocks in CI) | Gradle rejects module cycles |
| Go | Modules and `internal/` packages | Import rules such as depguard | Package import cycles are compile errors |
| Rust | cargo workspace crates | Crate separation or module visibility (`pub(crate)`) | cargo rejects crate cycles |
| TypeScript / JavaScript | Workspace packages (public surface limited by `exports`) | dependency-cruiser, eslint-plugin-boundaries | The package manager allows them, so a `no-circular` rule is required |
| Swift | SwiftPM packages and targets | Target separation + checker (`profiles/frontend.swiftui/enforcement/`) | SwiftPM rejects target cycles |

The binding documents are in `profiles/<id>/docs/en/`. A new language binding is added when a real project appears.

## An example of applying the same principle to the frontend

- The three token tiers (raw value → alias → component) pay for the alias layer in advance, reducing the cost of changing a theme or brand to a single alias definition. Details: `core/docs/en/architecture/frontend-design-contract.md`
- The component hierarchy is used only from top to bottom. Details: `core/docs/en/architecture/frontend-web.md`

## Preserving the prepayment

- Module boundaries are blocked by the build tool, and the layer direction inside a module is blocked by the architecture tests in CI. Editor-time hooks are only quick feedback, not the authoritative verdict.
- If violations have piled up in existing code, pin them as a baseline and block only newly arising violations. The baseline is updated only in the direction of shrinking.

## Evidence case (a backend project, 2026-09)

- When moving the 3.0 design of the order module to the billing module, the work ended with creating new entity, document and service modules and running the gateway path. The layer rules and the shape of the service code did not change (that project's decision of 2026-09-08).
- The costs actually struggled with were the mechanism for letting two modules coexist in the same DB, and the data migration. This experience is the basis for raising the "data ownership" boundary into a rule.
- In the 2026-07 ArchUnit measurement, nearly 1,500 in-module layer violations appeared. The module boundary was kept by the compiler, but the in-module boundary relied only on warnings. This is the basis of the "Preserving the prepayment" section.
