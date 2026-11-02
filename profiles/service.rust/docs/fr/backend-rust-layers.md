# Backend Rust — Projection du modèle conceptuel

> Référence : strata-kit `profiles/service.rust/docs/fr/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> Modèle conceptuel : `core/docs/fr/architecture/backend-cqrs.md` · style de code et marqueurs : `profiles/service.rust/docs/fr/backend-rust.md` (fondé sur le Google Rust Style Guide, DEC-2026-10-22-01)

## Résumé

- L'unité de frontière en Rust est le **crate**. Si une dépendance n'est pas déclarée dans `Cargo.toml`, l'import lui-même est une erreur de compilation ; le sens des couches peut donc être bloqué **à la compilation**. La projection Rust est de ce fait centrée sur la division du workspace Cargo en crates.
- Pile de référence : `axum` (HTTP), `tokio` (runtime), `sqlx` (SQL vérifié à la compilation), `serde`, `thiserror` (erreurs de bibliothèque) / `anyhow` (erreurs de binaire), `tracing`.
- Les noms de crate utilisent le vocabulaire courant du camp Rust (domain, app, infra, api), et le tableau ci-dessous décide à quelle couche conceptuelle chacun correspond. Les marqueurs (`@strata:layer`) utilisent les noms des couches conceptuelles.
- Les traits n'existent qu'aux frontières qui exigent une substitution (ports de dépôt, systèmes externes). Ne les créez pas simplement pour regrouper du code (backend-rust.md).

## Disposition du workspace

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      fonctions pures, codes d'erreur, types de page. Dépend de : rien (serde tout au plus)
  domain/       L1 (domaine), ports  entités, objets valeur, vérification d'invariants, calcul pur, traits de dépôt (ports). Dépend de : kit
  infra/        LM1, L2 niveau inférieur  sqlx PgPool, transactions, implémentations de ports (Repository, requêtes). Dépend de : kit, domain
  app/          L2 niveau supérieur, LM2, L3  CommandService, QueryService, Coordinator, CompositeService. Dépend de : kit, domain (ne connaît pas infra)
  api/          Route   axum Router, handlers, extracteurs, conversion de la réponse ; main injecte les implémentations d'infra dans app. Dépend de : app, infra, kit
```

| Couche conceptuelle | Crate / module | Exemples de noms |
|---|---|---|
| L1 | `kit`, types et fonctions libres de `domain::<domaine>` | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | configuration de `PgPool`, `with_tx` |
| L2 niveau inférieur | `infra::<domaine>` — implémentations de ports | `PgOrderRepository`, `order_queries.rs` |
| L2 niveau supérieur | `app::<domaine>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<sujet>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<domaine>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<domaine>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- L'essentiel est que `app` ne dépend pas d'`infra`. `app` ne voit que les traits de port de `domain`, et `api` (le point d'assemblage) fournit les implémentations. `Cargo.toml` impose ce sens.
- Les frontières de niveau à l'intérieur d'un crate s'expriment par la **visibilité** : seul ce qui est exporté vers d'autres crates est `pub`, ce qui n'est utilisé qu'au sein du crate est `pub(crate)`, et ce qui est dans un module est privé. Par exemple, les aides d'écriture au niveau de l'entité dans `app` sont `pub(crate)` pour que `api` ne puisse pas les appeler directement.
- L'interdiction de références au sein d'un même niveau (service ↔ service, usecase de domaine à usecase de domaine) est une frontière de module à l'intérieur d'`app`, donc le compilateur ne peut pas la bloquer. On la tient par la revue et par le tableau d'application des règles ci-dessous.

## Ports et commandes/requêtes

```rust
// crates/domain/src/order/port.rs — port (appartient au côté consommateur)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- Écriture : `OrderCommandService` ouvre la transaction (le type de transaction est une abstraction de `domain` ou un handle transmis par `infra`). Les transactions ne vivent que dans le niveau supérieur de L2.
- Lecture : `OrderQueryService` place directement les résultats de jointures dans des DTO avec `sqlx::query_as!`. Le modèle de lecture n'a pas à passer par les entités de domaine.
- Par défaut, les ports s'écrivent avec `async fn` natif (Rust 1.75+) et des génériques, comme dans l'exemple ci-dessus. Les traits à `async fn` natif ne peuvent pas être utilisés comme `dyn` ; si vous avez besoin de `Arc<dyn Trait>` parce que l'implémentation doit être échangée à l'exécution, utilisez le crate `async-trait`.

## Application des règles

| Quoi | Outil |
|---|---|
| Sens des couches (`app` → `infra` interdit, etc.) | déclarations de dépendances dans le `Cargo.toml` de chaque crate — à la compilation |
| Exposition hors du crate | `pub(crate)`, modules privés |
| Format et lint | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| Tests | `cargo test` ; les requêtes sont aussi vérifiées en CI grâce aux métadonnées hors ligne de `sqlx` (`cargo sqlx prepare`) |

## Marqueurs

Écrivez-les dans les commentaires de documentation avec le nom de la couche conceptuelle (`backend-rust.md` §Marqueurs Strata) :

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
