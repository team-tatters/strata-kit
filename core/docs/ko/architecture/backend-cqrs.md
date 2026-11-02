# 백엔드 아키텍처 — 개념 모델

> 정본: strata-kit `core/docs/ko/architecture/backend-cqrs.md`. 기계 판독 규칙은 `core/rules/layer-rules.yaml`, 구조를 처음부터 갖추는 이유는 `core/docs/ko/architecture/prepaid-structure.md`.
> 2026-10-29 개정 — 언어 무관 개념 모델과 언어별 투영을 나눴다(DEC-2026-10-29-06), 같은 레이어 참조의 의미를 반영했다(DEC-2026-09-30-04, strata), L3 접미를 CompositeService 로 맞췄다(DEC-2026-10-29-05).

## 요약

- 이 문서는 **어느 언어에서나 같은 것** 만 정한다: 레이어의 역할, 의존 방향, 같은 단 참조 금지, 명령과 조회의 분리. 디렉터리·패키지·모듈 배치와 이름, 집행 도구는 **언어별 투영 문서** 가 정한다(맨 아래 표).
- 레이어는 아래에서 위로만 참조한다: L1 → LM1 → L2 → LM2 → L3 → Route. 로직 레이어(L2 서비스 단·LM2·L3)는 **같은 단의 요소끼리** 참조하지 않는다.
- L2 는 두 단이다. 아래 단은 데이터 접근(Repository·DSL Template), 위 단은 서비스(Command·Query). 서비스는 아래 단을 쓰고, 같은 단끼리는 쓰지 않는다.
- 재사용이 필요하면 LM2 Coordinator 를 둔다. 묶는 기준은 "재사용되는가" 가 아니라 **"같은 도메인 관심사인가"** 다. 주입이 필요 없는 순수 계산은 단 밖의 순수 객체로 뺀다.
- 투영은 그 진영에서 가장 지지받는 프레임워크와 이디엄을 따른다. 레이어를 디렉터리 이름으로 강제하지 않는다. 레이어는 **역할** 이고, 어떤 물리 구조로 드러낼지는 언어가 정한다.

## 레이어

| 레이어 | 역할 | 참조 가능 | 같은 레이어 안 참조 |
|---|---|---|---|
| L1 Component | 프레임워크 무관 순수 함수·상수·타입. 공통·도메인·유틸 | 없음 | 허용(공통 유틸) |
| LM1 Inherite | L2 에 주입되는 공통 기반 — 감사 필드 Base Entity, DB·캐시 연결 설정, 공통 Repository 인터페이스, 트랜잭션 기반 | L1 | 허용 |
| L2 DataLayer | 도메인별 데이터 접근. **아래 단** Repository·DSL Template, **위 단** CommandService·QueryService | L1, LM1 | 아래 단은 위 단을 모른다. 같은 단끼리 금지 |
| LM2 Coordinate | 같은 도메인 관심사의 L2 조합을 묶는 재사용 비즈니스 흐름 | L2 | 금지 |
| L3 Composite | 유스케이스 하나. CompositeService·Listener(이벤트)·Task(스케줄) | LM2, L2 | 금지 |
| Route Controller | HTTP 수신·검증·인증 맥락 주입·응답 변환·오류 매핑 | L3 | 허용(공통 미들웨어) |

### L1 Component

프레임워크에 종속되지 않는 순수 함수, 상수, 타입이다. 예: 날짜 유틸, 검증 규칙, 오류 코드, 페이지 타입, 정렬 방향. 공통(모든 도메인), 도메인 전용, 범용 유틸로 나뉜다.

### LM1 Inherite

L2 가 상속하거나 주입받는 기반이다. Base Entity(createdAt·updatedAt·createdBy 등 감사 필드), DB·캐시 연결 설정, 공통 Repository 인터페이스, 트랜잭션 관리 기반.

### L2 DataLayer — 두 단

| 단 | 요소 | 규칙 |
|---|---|---|
| 아래 단 — 데이터 접근 | `Repository`(ORM·ODM 인터페이스 구현), `Template`(DSL 기반 복잡 쿼리) | 위 단을 참조하지 않는다. Repository ↔ Template 끼리도 참조하지 않는다 |
| 위 단 — 서비스 | `CommandService`(생성·수정·삭제, 트랜잭션), `QueryService`(읽기 전용) | 아래 단을 쓴다. 서비스 ↔ 서비스 참조 금지 |

- 하나의 함수는 하나의 엔티티만 다룬다. 여러 엔티티를 조합하는 일은 LM2·L3 의 책임이다.
- 조회 쪽은 여러 테이블을 조인해 DTO 로 바로 돌려줄 수 있다. 읽기 모델은 도메인 모델을 거치지 않아도 된다.

### LM2 Coordinate

같은 도메인 관심사에 속한 L2 호출 조합이 여러 L3 에서 쓰일 때 둔다. 묶는 기준은 재사용 횟수가 아니라 **도메인 관심사가 같은가** 다 — 서로 다른 관심사를 "같이 불리니까" 한 Coordinator 에 넣지 않는다. 예: `PaymentCoordinator`(결제 처리 공통 흐름), `ReviewCoordinator`(검토 도메인의 결재선 흐름).

### L3 Composite

하나의 유스케이스를 수행한다.

- `{Domain}CommandCompositeService` · `{Domain}QueryCompositeService` — 행위가 드러나야 하면 `{Domain}{Action}CompositeService`(예: `EmissionManageCompositeService`)
- `{Domain}Listener` — 이벤트 기반 백그라운드 처리
- `{Domain}Task` — 스케줄 기반 백그라운드 처리

"주문 생성" = `OrderCommandCompositeService.createOrder()`. 하나의 CompositeService 는 하나의 유스케이스 묶음에 대응한다.

### Route Controller

URI 매핑, 요청 파라미터·본문 검증, 인증·인가 맥락 주입, 응답 DTO 변환, 오류를 HTTP 상태로 매핑한다. **Controller 에서 L2 를 직접 부르지 않는다** — 아무리 단순한 CRUD 도 L3 를 거친다. 리스너·스케줄 Task 도 같은 L3 를 부르는 진입점이라, 진입 어댑터를 늘려도 유스케이스 코드는 그대로다.

## 순수 계산

단위 환산, 산식 평가처럼 주입이 필요 없는 계산은 어느 단에도 넣지 않고 **주입 없는 순수 객체**(Kotlin `object`, Go 패키지 함수, Rust 자유 함수, TS 모듈 함수)로 뺀다. 그러면 같은 단 참조 금지 때문에 계산을 복제하거나 억지로 Coordinator 를 만들 일이 없다.

## 의존 방향

```
Route_Controller
    ↓ (L3 만)
L3_Composite
    ↓ (LM2 또는 L2)
LM2_Coordinate
    ↓ (L2 만)
L2_DataLayer   위 단 Command·Query → 아래 단 Repository·Template
    ↓ (L1, LM1)
LM1_Inherite
    ↓ (L1)
L1_Component
```

화살표 반대 방향 참조는 금지다. 로직 레이어의 같은 단 참조도 금지다.

## 명령과 조회

명령과 조회의 분리는 **마이크로서비스 분리가 아니라 같은 프로세스 안의 경로 분리** 다.

- 조회 경로는 부수효과가 없어 다른 저장소(복제본·캐시·외부 테이블·뷰)로 옮기거나 바꾸는 비용이 낮다.
- 명령 경로의 트랜잭션 경계는 서비스를 나눌 때의 자연스러운 분리선이 된다.
- 둘을 처음부터 나눠 두면 모놀리스에서 여러 배포 단위로 갈 때 레이어가 거의 바뀌지 않는다(prepaid-structure).

## Variants

두 variant 모두 레이어 방향은 같고 L2 쓰기 쪽 처리만 다르다. 프로젝트는 `layer-map.yaml` 의 `variant` 로 고른다(없으면 `cqrs`).

| | CQRS (기본) | ES-CQRS |
|---|---|---|
| 진실의 원천 | DB 현재 행 | 이벤트 로그 |
| L2 쓰기 쪽 | CommandService | Aggregate → EventStore (ES Track) |
| L2 읽기 쪽 | QueryService | QueryService (같음) |
| 추가 구성요소 | 없음 | Aggregate, EventStore, Projection |
| 맞는 경우 | 일반 CRUD, 단순 도메인 | 감사 추적, 이중 시간축, 이벤트 기반 도메인 |

### ES-CQRS

ES-CQRS 는 L2 쓰기 쪽을 ES Track 으로 대체한다. 명령은 L3 → Aggregate(이벤트 발행) → EventStore(저장) → Projection(읽기 모델 갱신) → L2 QueryService 로 흐르고, 조회는 L3 → L2 QueryService 로 흐른다.

| 구성요소 | 규칙 |
|---|---|
| Aggregate | 이벤트를 발행하는 도메인 모델. L1 만 참조, 다른 Aggregate 를 직접 참조하지 않는다(Saga·ProcessManager 로 통신). 불변식 검증 후 이벤트 생성 |
| EventStore | L1·LM1 만 참조. Aggregate·Projection 을 직접 참조하지 않는다. PG + JSONB 기본, 필요 시 스냅샷 |
| Projection | ES Track 과 레이어를 잇는 유일한 다리. 동기(inline) 또는 비동기(outbox) |

| 규칙 | 내용 | 범위 |
|---|---|---|
| R1 | 명령 진입점은 반드시 L3 CompositeService 경유 | 양쪽 |
| R2 | Aggregate 는 L1 외 레이어를 import 하지 않는다 | es-cqrs |
| R3 | L2 DataLayer 는 읽기 전용(CommandService 없음) | es-cqrs |
| R4 | Projection 이 ES → 읽기 모델의 유일한 다리 | es-cqrs |
| R5 | Aggregate 간 직접 참조 금지(Saga 로 통신) | es-cqrs |
| R6 | Rebase 정책은 Projection 수준(Aggregate 는 정책을 모른다) | es-cqrs |

인프라 수준은 단계적으로 고른다: PG 만 쓰는 inline projection(추가 비용 없음, 즉시 일관성) → PG outbox + 프로세스 내 worker → 메시지 브로커 → 서비스별 EventStore + 브로커.

## 언어별 투영

같은 레이어 의미를 각 언어의 지지받는 구조로 옮긴다. 공통 원칙은 셋이다 — **배포·모듈 단위가 먼저** 오고(기능·도메인별 모듈), 레이어는 그 안에서 **역할(파일·타입·접미)** 로 드러나며, 경계는 **그 언어의 컴파일러·패키지 시스템·린터** 가 막는다.

| 언어 | 대표 스택 | 모듈 단위 | 레이어 표현 | 경계 집행 | 문서 |
|---|---|---|---|---|---|
| Kotlin·Java | Spring Boot · Spring Data JPA · jOOQ | Gradle 모듈(entity·service) | 패키지 + 접미(CommandService·CompositeService) | ArchUnit(이 규칙 YAML 을 런타임에 읽음), Kotlin `internal` | `profiles/backend.kotlin-spring-cqrs/docs/ko/backend-kotlin-spring.md` |
| Go | 표준 `net/http`(1.22 라우팅) · `pgx` · `sqlc` | 기능 패키지(`internal/<domain>/`) | 패키지 안의 역할 파일(`command.go`·`query.go`·`store.go`·`http.go`) | 순환 import 금지(컴파일러), `internal/`, `depguard`·`go-arch-lint` | `profiles/backend.go-service/docs/ko/backend-go.md` |
| Rust | `axum` · `tokio` · `sqlx` | Cargo 워크스페이스 크레이트 | 크레이트(domain·app·infra·api)와 모듈, `pub(crate)` | `Cargo.toml` 의존 방향(컴파일 시점), 가시성 | `profiles/service.rust/docs/ko/backend-rust-layers.md` |
| TypeScript | NestJS · (Prisma 또는 TypeORM) | Nest 모듈(도메인별) | provider 접미와 모듈 `exports` | Nest DI(내보내지 않은 provider 는 주입 불가), `dependency-cruiser` | `profiles/backend.typescript-nest/docs/ko/backend-nest.md` |

기계 판독 규칙(`core/rules/layer-rules.yaml`)의 `language_patterns` 는 kotlin·go·rust·typescript 네 투영을 갖고, L2 는 `tiers`(lower·upper)로 두 단을 선언한다(오더 2026.10.29-07 task-04, 교차 검증 2026-10-29). 지금 집행 도구가 읽는 것은 kotlin 투영(ArchUnit 템플릿)과 레이어 수준의 `can_reference`·`cross_reference` 뿐이라, `tiers` 와 같은 도메인 안의 같은 단 참조 금지는 아직 선언이다 — 집행은 별도 변경으로 실측 뒤에 올린다.

## 결정 전의 확장 (분석 단계)

2026-10-29 분석에서 나온 다음 셋은 아직 결정이 아니다. 결정되면 이 문서와 투영 문서에 반영한다.

- **모듈의 공개 계약** — 다른 모듈은 계약(인터페이스·전용 타입·이벤트)만 본다. 지금 소비자 쪽에 있는 원격 호출 인터페이스를 공급자 쪽으로 옮기고 전송 방식에서 떼어 내는 것.
- **쓰기 단위를 애그리거트로** — L2 쓰기 쪽을 "엔티티 하나" 에서 "애그리거트 하나" 로, 엔티티 단위 쓰기는 모듈 가시성으로 숨김. 위의 L2 두 단과 함께 다룬다.
- **마이그레이션 이력의 모듈 소유** — 스키마와 이력 테이블을 모듈이 소유하고, 모듈 간 DB 의존은 공개 뷰로만.
