# Backend Rust — Proyección del modelo conceptual

> Canónico: strata-kit `profiles/service.rust/docs/es/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> Modelo conceptual: `core/docs/es/architecture/backend-cqrs.md` · estilo de código y marcadores: `profiles/service.rust/docs/es/backend-rust.md` (basado en la Google Rust Style Guide, DEC-2026-10-22-01)

## Resumen

- La unidad de límite en Rust es el **crate**. Si una dependencia no se declara en `Cargo.toml`, el propio import es un error de compilación, de modo que la dirección de las capas se puede bloquear **en tiempo de compilación**. Por eso la proyección de Rust se centra en cómo se divide en crates el workspace de Cargo.
- Stack de referencia: `axum` (HTTP), `tokio` (runtime), `sqlx` (SQL verificado en compilación), `serde`, `thiserror` (errores de biblioteca) / `anyhow` (errores de binario), `tracing`.
- Los nombres de crate usan el vocabulario común del campo de Rust (domain, app, infra, api), y la tabla de abajo decide a qué capa conceptual corresponde cada uno. Los marcadores (`@strata:layer`) usan los nombres de las capas conceptuales.
- Los traits existen solo en los límites que necesitan sustitución (puertos de repositorio, sistemas externos). No los crees solo para agrupar código (backend-rust.md).

## Disposición del workspace

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      funciones puras, códigos de error, tipos de página. Depende de: nada (serde como mucho)
  domain/       L1 (dominio), puertos  entidades, objetos de valor, comprobación de invariantes, cálculo puro, traits de repositorio (puertos). Depende de: kit
  infra/        LM1, L2 nivel inferior  sqlx PgPool, transacciones, implementaciones de puertos (Repository, consultas). Depende de: kit, domain
  app/          L2 nivel superior, LM2, L3  CommandService, QueryService, Coordinator, CompositeService. Depende de: kit, domain (no conoce infra)
  api/          Route   axum Router, handlers, extractores, conversión de respuesta; main inyecta las implementaciones de infra en app. Depende de: app, infra, kit
```

| Capa conceptual | Crate / módulo | Nombres de ejemplo |
|---|---|---|
| L1 | `kit`, tipos y funciones libres de `domain::<dominio>` | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | configuración de `PgPool`, `with_tx` |
| L2 nivel inferior | `infra::<dominio>` — implementaciones de puertos | `PgOrderRepository`, `order_queries.rs` |
| L2 nivel superior | `app::<dominio>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<preocupación>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<dominio>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<dominio>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- Lo esencial es que `app` no depende de `infra`. `app` solo ve los traits de puerto de `domain`, y `api` (el punto de ensamblado) aporta las implementaciones. `Cargo.toml` hace cumplir esta dirección.
- Los límites de nivel dentro de un crate se expresan con la **visibilidad**: solo lo que se exporta a otros crates es `pub`, lo que se usa solo dentro del crate es `pub(crate)` y lo que está dentro de un módulo es privado. Por ejemplo, los ayudantes de escritura a nivel de entidad de `app` son `pub(crate)` para que `api` no pueda llamarlos directamente.
- La prohibición de referencias en el mismo nivel (servicio ↔ servicio, usecase de dominio con usecase de dominio) es un límite de módulo dentro de `app`, así que el compilador no puede bloquearla. Se hace cumplir con revisión y con la tabla de cumplimiento de abajo.

## Puertos y comandos/consultas

```rust
// crates/domain/src/order/port.rs — puerto (pertenece al lado consumidor)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- Escritura: `OrderCommandService` abre la transacción (el tipo de transacción es una abstracción en `domain` o un handle que pasa `infra`). Las transacciones viven solo en el nivel superior de L2.
- Lectura: `OrderQueryService` coloca los resultados de joins directamente en DTO con `sqlx::query_as!`. El modelo de lectura no tiene que pasar por las entidades de dominio.
- Por defecto, los puertos se escriben con `async fn` nativo (Rust 1.75+) y genéricos, como en el ejemplo anterior. Los traits con `async fn` nativo no pueden usarse como `dyn`, así que si necesitas `Arc<dyn Trait>` porque la implementación debe intercambiarse en tiempo de ejecución, usa el crate `async-trait`.

## Cumplimiento

| Qué | Herramienta |
|---|---|
| Dirección de las capas (`app` → `infra` prohibido, etc.) | declaraciones de dependencias en el `Cargo.toml` de cada crate — en tiempo de compilación |
| Exposición fuera del crate | `pub(crate)`, módulos privados |
| Formato y lint | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| Pruebas | `cargo test`; las consultas también se verifican en CI mediante los metadatos sin conexión de `sqlx` (`cargo sqlx prepare`) |

## Marcadores

Escríbelos en comentarios de documentación con el nombre de la capa conceptual (`backend-rust.md` §Marcadores de Strata):

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
