# 后端 Rust — 概念模型的投影

> 正本: strata-kit `profiles/service.rust/docs/zh/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> 概念模型: `core/docs/zh/architecture/backend-cqrs.md` · 代码风格与标记: `profiles/service.rust/docs/zh/backend-rust.md` (以 Google Rust Style Guide 为基础, DEC-2026-10-22-01)

## 摘要

- Rust 的边界单位是 **crate**。如果没有在 `Cargo.toml` 中声明依赖,import 本身就是编译错误,因此可以在**编译期**拦截层的方向。所以 Rust 的投影以 Cargo 工作区的 crate 划分为核心。
- 基准技术栈: `axum`(HTTP)、`tokio`(运行时)、`sqlx`(编译期校验的 SQL)、`serde`、`thiserror`(库错误)/`anyhow`(二进制错误)、`tracing`。
- crate 名称采用 Rust 阵营常见的词汇(domain、app、infra、api),各自对应概念层的哪一层由下表规定。标记(`@strata:layer`)使用概念层名称。
- trait 只放在需要替换的边界(仓储端口、外部系统)。不要为了归拢代码而创建(backend-rust.md)。

## 工作区布局

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      纯函数、错误码、分页类型。依赖: 无(至多 serde)
  domain/       L1(领域)、端口  实体、值对象、不变式检查、纯计算、仓储 trait(端口)。依赖: kit
  infra/        LM1、L2 下层  sqlx PgPool、事务、端口实现(Repository、查询)。依赖: kit, domain
  app/          L2 上层、LM2、L3  CommandService、QueryService、Coordinator、CompositeService。依赖: kit, domain (不知道 infra)
  api/          Route   axum Router、处理器、提取器、响应转换,在 main 中把 infra 的实现注入 app。依赖: app, infra, kit
```

| 概念层 | crate、模块 | 名称示例 |
|---|---|---|
| L1 | `kit`、`domain::<领域>` 的类型与自由函数 | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | `PgPool` 配置, `with_tx` |
| L2 下层 | `infra::<领域>` — 端口实现 | `PgOrderRepository`, `order_queries.rs` |
| L2 上层 | `app::<领域>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<关注点>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<领域>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<领域>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- 关键在于 `app` 不依赖 `infra`。`app` 只看 `domain` 的端口 trait,实现由 `api`(装配点)注入。这个方向由 `Cargo.toml` 强制。
- crate 内部的层级边界用**可见性**表达: 只有要导出给其他 crate 的才用 `pub`,只在 crate 内使用的用 `pub(crate)`,模块内的保持私有。例如 `app` 中以实体为单位的写入辅助函数用 `pub(crate)`,使 `api` 无法直接调用。
- 同层引用禁令(服务 ↔ 服务、领域 usecase 之间)属于 `app` 内部的模块边界,编译器无法拦截。通过评审和下面的强制执行表来保证。

## 端口与命令、查询

```rust
// crates/domain/src/order/port.rs — 端口(由使用方拥有)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- 写: `OrderCommandService` 开启事务(事务类型是 `domain` 中的抽象,或由 `infra` 传入的句柄)。事务只放在 L2 上层。
- 读: `OrderQueryService` 用 `sqlx::query_as!` 把连接结果直接放入 DTO。读取模型不必经过领域实体。
- 端口默认如上例所示,用原生 `async fn`(Rust 1.75+)加泛型来写。原生 `async fn` trait 不能作为 `dyn` 使用,所以如果因为需要在运行时替换实现而必须用 `Arc<dyn Trait>`,就使用 `async-trait` crate。

## 强制执行

| 对象 | 工具 |
|---|---|
| 层的方向(禁止 `app` → `infra` 等) | 各 crate `Cargo.toml` 中的依赖声明 — 编译期 |
| 对 crate 外暴露 | `pub(crate)`、私有模块 |
| 格式、lint | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| 测试 | `cargo test`,借助 `sqlx` 离线元数据(`cargo sqlx prepare`)在 CI 中也校验查询 |

## 标记

在文档注释中使用概念层名称书写(`backend-rust.md` §Strata 标记):

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
