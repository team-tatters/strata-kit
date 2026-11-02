# 백엔드 Go — 개념 모델의 투영

> 정본: strata-kit `profiles/backend.go-service/docs/ko/backend-go.md` (2026-10-29, DEC-2026-10-29-06)
> 개념 모델: `core/docs/ko/architecture/backend-cqrs.md` — 레이어 의미·의존 방향·같은 단 참조 금지는 그쪽이 정본이다. 이 문서는 Go 에서 그것을 어떻게 드러내는지만 정한다.

## 요약

- Go 의 캡슐화 단위는 **패키지** 다. 그래서 레이어를 디렉터리(`internal/component/`·`internal/data/`…)로 펼치지 않고, **기능(도메인) 패키지가 먼저** 오고 레이어는 그 안의 **역할 파일** 로 드러낸다. Go 커뮤니티가 피하는 것은 CQRS 가 아니라 "레이어별 디렉터리와 구조체마다 인터페이스" 다.
- 기준 스택: 표준 `net/http`(Go 1.22 패턴 라우팅) · `pgx` · `sqlc`(SQL 에서 타입 있는 쿼리 함수 생성) · `log/slog`. 프레임워크(gin·echo)는 선택이고 투영은 같다.
- 인터페이스는 **쓰는 쪽에서** 작게 정의한다("accept interfaces, return structs"). 이것이 헥사고날의 포트 소유 원칙과 같다.
- 경계는 컴파일러(순환 import 금지)·`internal/` 디렉터리·`depguard`(golangci-lint) 가 막는다.

## 배치

```
cmd/api/main.go                 Route 조립 — 서버 시작, 의존 연결(손으로 쓰는 DI)
internal/
  platform/                     LM1 — db 풀·트랜잭션 헬퍼·설정 (pgxpool, slog)
  kit/                          L1 — 순수 함수·오류 코드·페이지 타입 (프레임워크 import 없음)
  order/                        기능 패키지 하나 = 도메인 하나
    order.go                    L1(도메인) — 엔티티 타입·값 객체·순수 계산
    store.go                    L2 아래 단 — sqlc 생성 Queries 를 감싼 조회·저장 (Repository·Template 역할)
    command.go                  L2 위 단 — CommandService: 트랜잭션 안의 생성·수정·삭제
    query.go                    L2 위 단 — QueryService: 읽기 전용, DTO 로 바로 반환
    coordinate.go               LM2 — 같은 관심사의 L2 조합 (필요할 때만)
    usecase.go                  L3 — CompositeService: 유스케이스
    http.go                     Route — 핸들러: 검증·인증 맥락·응답 변환, usecase 만 호출
    queries.sql / db/           sqlc 입력·생성물
  payment/ …
```

| 개념 레이어 | Go 에서 | 이름 |
|---|---|---|
| L1 | `internal/kit` 패키지, 기능 패키지의 타입·순수 함수 | `PageRequest`, `func Convert(...)` |
| LM1 | `internal/platform` | `NewPool`, `WithTx` |
| L2 아래 단 | `store.go` — sqlc `Queries` 래퍼 | `type store struct{ q *db.Queries }` (소문자: 패키지 밖에 숨김) |
| L2 위 단 | `command.go` · `query.go` | `type CommandService struct`, `type QueryService struct` |
| LM2 | `coordinate.go` 또는 `internal/<관심사>` 패키지 | `type PaymentCoordinator struct` |
| L3 | `usecase.go` | `type CommandCompositeService struct` (패키지가 도메인이라 `order.CommandCompositeService`) |
| Route | `http.go`, `cmd/api` | `func (h *Handler) CreateOrder(w, r)` |

- 같은 패키지 안이라 Go 컴파일러는 파일 사이 참조를 막지 못한다. **같은 단 참조 금지는 리뷰와 린터** 로 지킨다: L2 위 단 타입끼리 필드로 갖지 않는다, `store` 는 서비스 타입을 모른다.
- 아래 단(`store`)과 생성된 sqlc 코드는 **소문자 타입** 으로 두어 패키지 밖(다른 도메인·핸들러)에서 직접 못 쓰게 한다. 다른 패키지가 쓸 것은 서비스·유스케이스 타입뿐이다.
- 이름 말더듬을 피한다: `order.OrderService` 가 아니라 `order.CommandService`.

## 의존과 인터페이스

```go
// internal/order/usecase.go — L3
type CommandCompositeService struct {
    cmd      *CommandService
    payments PaymentAuthorizer          // 다른 도메인은 쓰는 쪽에서 정의한 작은 인터페이스로
}

type PaymentAuthorizer interface {     // 포트: 소비자(order)가 소유
    Authorize(ctx context.Context, orderID int64, amount Money) error
}

func (s *CommandCompositeService) PlaceOrder(ctx context.Context, in PlaceOrderInput) (OrderID, error) {
    id, err := s.cmd.Create(ctx, in.toNew())
    if err != nil { return 0, err }
    return id, s.payments.Authorize(ctx, int64(id), in.Total)
}
```

- 도메인 패키지끼리는 서로 import 하지 않는다(L3 ↔ L3 금지). 필요한 것은 쓰는 쪽 인터페이스로 받고, `cmd/api/main.go` 가 구현을 연결한다.
- 구조체마다 인터페이스를 미리 만들지 않는다. 인터페이스는 대체(테스트 대역·다른 구현)가 필요한 경계에서만.

## 명령과 조회

- 쓰기: `CommandService` 메서드가 `platform.WithTx(ctx, pool, func(q *db.Queries) error {...})` 안에서 실행된다. 트랜잭션은 L2 위 단에만.
- 읽기: `QueryService` 는 sqlc 가 만든 조회 함수(조인 포함)를 그대로 DTO 로 돌려준다. 도메인 타입을 거치지 않아도 된다.

## 집행

| 무엇 | 도구 |
|---|---|
| 도메인 패키지 간 import 금지, `kit` 은 아무것도 import 하지 않음 | `golangci-lint` 의 `depguard` 규칙(패키지 경로 기준) 또는 `go-arch-lint` |
| 패키지 밖 노출 차단 | 소문자 식별자, `internal/` |
| 순환 의존 | 컴파일러 |
| 포맷·정적 검사 | `gofmt`, `go vet`, `staticcheck` |
| 테스트 | `go test ./...` (store 는 testcontainers 의 실제 PG 로) |

## 마커

Go 는 godoc 주석에 `@` 없이 둔다(`core/rules/naming-convention.yaml` markers.language_format.go, `core/docs/ko/conventions/strata-markers.md`):

```go
// strata:layer L2-QueryService
type QueryService struct{ … }
```
