# 백엔드 Rust — 개념 모델의 투영

> 정본: strata-kit `profiles/service.rust/docs/ko/backend-rust-layers.md` (2026-10-29, DEC-2026-10-29-06)
> 개념 모델: `core/docs/ko/architecture/backend-cqrs.md` · 코드 스타일·마커: `profiles/service.rust/docs/ko/backend-rust.md` (Google Rust Style Guide 바탕, DEC-2026-10-22-01)

## 요약

- Rust 의 경계 단위는 **크레이트** 다. `Cargo.toml` 에 의존을 선언하지 않으면 import 자체가 컴파일 오류가 되므로, 레이어 방향을 **컴파일 시점에** 막을 수 있다. 그래서 Rust 투영은 Cargo 워크스페이스의 크레이트 나눔이 중심이다.
- 기준 스택: `axum`(HTTP) · `tokio`(런타임) · `sqlx`(컴파일 시 검증되는 SQL) · `serde` · `thiserror`(라이브러리 오류)·`anyhow`(바이너리 오류) · `tracing`.
- 크레이트 이름은 Rust 진영의 흔한 어휘(domain·app·infra·api)를 쓰고, 각각이 개념 레이어 어디에 해당하는지는 아래 표가 정한다. 마커(`@strata:layer`)는 개념 레이어 이름을 쓴다.
- 트레이트는 대체가 필요한 경계(저장소 포트·외부 시스템)에만 둔다. 코드를 묶으려고 만들지 않는다(backend-rust.md).

## 워크스페이스 배치

```
Cargo.toml                [workspace] members = ["crates/*"]
crates/
  kit/          L1      순수 함수·오류 코드·페이지 타입. 의존: 없음(serde 정도)
  domain/       L1(도메인)·포트  엔티티·값 객체·불변식 검사·순수 계산, 저장소 트레이트(포트). 의존: kit
  infra/        LM1·L2 아래 단  sqlx PgPool·트랜잭션, 포트 구현(Repository·쿼리). 의존: kit, domain
  app/          L2 위 단·LM2·L3  CommandService·QueryService·Coordinator·CompositeService. 의존: kit, domain (infra 를 모른다)
  api/          Route   axum Router·핸들러·추출기·응답 변환, main 에서 infra 구현을 app 에 주입. 의존: app, infra, kit
```

| 개념 레이어 | 크레이트·모듈 | 이름 예 |
|---|---|---|
| L1 | `kit`, `domain::<도메인>` 의 타입·자유 함수 | `PageRequest`, `fn convert_unit(...)` |
| LM1 | `infra::db` | `PgPool` 설정, `with_tx` |
| L2 아래 단 | `infra::<도메인>` — 포트 구현 | `PgOrderRepository`, `order_queries.rs` |
| L2 위 단 | `app::<도메인>::{command, query}` | `OrderCommandService`, `OrderQueryService` |
| LM2 | `app::<관심사>::coordinator` | `PaymentCoordinator` |
| L3 | `app::<도메인>::usecase` | `OrderCommandCompositeService` |
| Route | `api::<도메인>` | `async fn create_order(State(app): State<AppState>, Json(body): Json<CreateOrder>)` |

- `app` 이 `infra` 를 의존하지 않는 것이 핵심이다. `app` 은 `domain` 의 포트 트레이트만 보고, 구현은 `api`(조립 지점)가 넣는다. 이 방향은 `Cargo.toml` 이 강제한다.
- 크레이트 안의 단 경계는 **가시성** 으로: 다른 크레이트에 내보낼 것만 `pub`, 크레이트 안에서만 쓸 것은 `pub(crate)`, 모듈 안 것은 비공개. 예를 들어 `app` 의 엔티티 단위 쓰기 헬퍼는 `pub(crate)` 로 두어 `api` 가 직접 못 부르게 한다.
- 같은 단 참조 금지(서비스 ↔ 서비스, 도메인 usecase 끼리)는 `app` 안의 모듈 경계라 컴파일러가 막지 못한다. 리뷰와 아래 집행표로 지킨다.

## 포트와 명령·조회

```rust
// crates/domain/src/order/port.rs — 포트(소비자 쪽 소유)
pub trait OrderStore: Send + Sync {
    async fn insert(&self, tx: &mut Tx, new: NewOrder) -> Result<OrderId, StoreError>;
}

// crates/app/src/order/usecase.rs — L3
pub struct OrderCommandCompositeService<S: OrderStore, P: PaymentAuthorizer> {
    cmd: OrderCommandService<S>,
    payments: P,
}
```

- 쓰기: `OrderCommandService` 가 트랜잭션을 연다(트랜잭션 타입은 `domain` 의 추상 또는 `infra` 가 넘긴 핸들). 트랜잭션은 L2 위 단에만.
- 읽기: `OrderQueryService` 는 `sqlx::query_as!` 로 조인 결과를 DTO 에 바로 담는다. 읽기 모델은 도메인 엔티티를 거치지 않아도 된다.
- 포트는 위 예처럼 네이티브 `async fn`(Rust 1.75+)과 제네릭으로 쓰는 것이 기본이다. 네이티브 `async fn` 트레이트는 `dyn` 으로 쓸 수 없으므로, 실행 시 구현을 갈아 끼워야 해서 `Arc<dyn Trait>` 가 필요하면 `async-trait` 크레이트를 쓴다.

## 집행

| 무엇 | 도구 |
|---|---|
| 레이어 방향(`app` → `infra` 금지 등) | 각 크레이트 `Cargo.toml` 의 의존 선언 — 컴파일 시점 |
| 크레이트 밖 노출 | `pub(crate)`·비공개 모듈 |
| 포맷·린트 | `cargo fmt --check`, `cargo clippy --no-deps -D warnings` |
| 테스트 | `cargo test`, `sqlx` 오프라인 메타데이터(`cargo sqlx prepare`)로 CI 에서도 쿼리 검증 |

## 마커

문서 주석에 개념 레이어 이름으로 적는다(`backend-rust.md` §Strata 마커):

```rust
/// @strata:layer L2-QueryService
pub struct OrderQueryService { … }
```
