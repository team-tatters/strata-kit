# Backend Rust — Projection of the Conceptual Model

> Canonical: strata-kit `profiles/service.rust/docs/en/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> Conceptual model: `core/docs/en/architecture/backend-cqrs.md` · code style and markers: `profiles/service.rust/docs/en/backend-rust.md` (based on the Google Rust Style Guide, DEC-2026-10-22-01)

## Summary

- The boundary unit in Rust is the **crate**. If a dependency is not declared in `Cargo.toml`, the import itself is a compile error, so the layer direction can be blocked **at compile time**. The Rust projection is therefore centered on how the Cargo workspace is divided into crates.
- Reference stack: `axum` (HTTP), `tokio` (runtime), `sqlx` (SQL verified at compile time), `serde`, `thiserror` (library errors) / `anyhow` (binary errors), `tracing`.
- Crate names use the common vocabulary of the Rust camp (domain, app, infra, api), and the table below decides which conceptual layer each corresponds to. Markers (`@strata:layer`) use the conceptual layer names.
- Traits exist only at boundaries that need substitution (repository ports, external systems). Do not create them just to group code (backend-rust.md).

## Workspace Layout

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      pure functions, error codes, page types. Depends on: nothing (serde at most)
  domain/       L1 (domain), ports  entities, value objects, invariant checks, pure calculation, repository traits (ports). Depends on: kit
  infra/        LM1, L2 lower tier  sqlx PgPool, transactions, port implementations (Repository, queries). Depends on: kit, domain
  app/          L2 upper tier, LM2, L3  CommandService, QueryService, Coordinator, CompositeService. Depends on: kit, domain (does not know infra)
  api/          Route   axum Router, handlers, extractors, response conversion; main injects infra implementations into app. Depends on: app, infra, kit
```

| Conceptual layer | Crate / module | Example names |
|---|---|---|
| L1 | `kit`, types and free functions of `domain::<domain>` | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | `PgPool` setup, `with_tx` |
| L2 lower tier | `infra::<domain>` — port implementations | `PgOrderRepository`, `order_queries.rs` |
| L2 upper tier | `app::<domain>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<concern>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<domain>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<domain>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- The key point is that `app` does not depend on `infra`. `app` sees only the port traits of `domain`, and `api` (the assembly point) supplies the implementations. `Cargo.toml` enforces this direction.
- Tier boundaries inside a crate are expressed by **visibility**: only what is exported to other crates is `pub`, what is used only within the crate is `pub(crate)`, and what is inside a module is private. For example, the entity-level write helpers of `app` are `pub(crate)` so that `api` cannot call them directly.
- The ban on same-tier references (service ↔ service, domain usecase to domain usecase) is a module boundary inside `app`, so the compiler cannot block it. Keep it with review and the enforcement table below.

## Ports and Commands/Queries

```rust
// crates/domain/src/order/port.rs — port (owned by the consumer side)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- Writes: `OrderCommandService` opens the transaction (the transaction type is an abstraction in `domain` or a handle passed in by `infra`). Transactions live only in the L2 upper tier.
- Reads: `OrderQueryService` puts join results directly into DTOs with `sqlx::query_as!`. The read model does not have to pass through domain entities.
- By default, ports are written with native `async fn` (Rust 1.75+) and generics, as in the example above. Native `async fn` traits cannot be used as `dyn`, so if you need `Arc<dyn Trait>` because the implementation must be swapped at run time, use the `async-trait` crate.

## Enforcement

| What | Tool |
|---|---|
| Layer direction (`app` → `infra` forbidden, etc.) | dependency declarations in each crate's `Cargo.toml` — at compile time |
| Exposure outside the crate | `pub(crate)`, private modules |
| Format and lint | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| Tests | `cargo test`; queries are also verified in CI through `sqlx` offline metadata (`cargo sqlx prepare`) |

## Markers

Write them in doc comments using the conceptual layer name (`backend-rust.md` §Strata Markers):

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
