# Strata 마커

> 정본: strata-kit `core/docs/ko/conventions/strata-markers.md` — strata `docs/05-conventions/strata-markers.md` 에서 이관 (오더 2026.10.29-06, 2026-10-29). 규칙 YAML 은 `core/rules/`.

> 기계 판독 가능한 정의: `core/rules/naming-convention.yaml` → `markers` 섹션

소스코드에 삽입하는 주석 기반 어노테이션으로, 파일이 어떤 레이어/포트/도메인에 속하는지 선언합니다.

> **집행 상태 (2026-07 기준)**: 마커는 현재 **grep/사람 판독용**이다. Hook 스크립트
> (`check-layer-violation.py`, `validate-naming.py`)는 아직 마커를 파싱하지 않으며,
> `@strata:generated` 검증 제외도 미구현 상태다 (레이어 식별은 layer-map/디렉토리 기반).
> 마커 파서 구현 여부는 `methodology-backlog.yaml` MB-strata-2026-003의 집행 위임
> 전략에 따라 결정한다 — JVM 정본 집행은 ArchUnit(`profiles/backend.kotlin-spring-cqrs/enforcement/`)이 담당.

## 문법

```
@strata:{tag} {value}
```

Go는 `@` 없이 사용합니다 (godoc 관습):

```
strata:{tag} {value}
```

## 지원 태그

| 태그 | 용도 | 패턴 | 예시 |
|---|---|---|---|
| `port` | 레이어 포트(서비스 인터페이스) 선언 | `{Layer}-{ServiceName}` | `@strata:port L2-InventoryQueryService` |
| `layer` | 파일이 속한 레이어 선언 | `{Layer}` | `@strata:layer L2` |
| `domain` | 파일이 속한 비즈니스 도메인 선언 | `{domain}` | `@strata:domain inventory` |
| `generated` | 자동 생성 파일 (레이어 검증 제외) | (값 없음) | `@strata:generated` |
| `adapter` | 외부 라이브러리 어댑터 선언 | `{library}` | `@strata:adapter sqlc` |
| `depends` | 명시적 의존 포트 선언 | `{Layer}-{ServiceName}` | `@strata:depends L2-OrderQueryService` |
| `token-exception` | Foundation 밖 raw 토큰 값의 임시 허용. **만료일 필수** — 지나면 diff 검사 실패 (`core/docs/ko/architecture/frontend-design-contract.md` §예외 정책) | `{reason} until {YYYY-MM-DD}` | `@strata:token-exception 디자인 확정 전 임시 색 until 2026-10-31` |

## 언어별 형식

### Kotlin (KDoc)

```kotlin
/**
 * @strata:port L2-InventoryCommandService
 * @strata:layer L2
 * @strata:domain inventory
 */
class InventoryCommandService(
    private val repository: InventoryRepository
) { ... }
```

### Go (godoc)

Go는 `@` 접두사 없이 `strata:` 형식을 사용합니다.

```go
// InventoryQueryRepository provides read-only access to inventory views.
//
// strata:port L2-InventoryQueryRepository
// strata:layer L2
// strata:domain inventory
type InventoryQueryRepository interface {
    FindByID(ctx context.Context, id uuid.UUID) (*InventoryView, error)
}
```

### Swift (문서 주석)

```swift
/// 오늘 상태 번역 규칙 — 순수 함수만.
/// @strata:layer Contract
/// @strata:domain today
enum StateEngine { … }
```

### TypeScript (JSDoc)

```typescript
/**
 * @strata:port L2-InventoryQueryService
 * @strata:layer L2
 * @strata:domain inventory
 */
export class InventoryQueryService {
    constructor(private readonly repo: InventoryRepository) {}
}
```

## 검색 패턴

```bash
# 특정 레이어의 모든 포트 검색
grep -r "@strata:port L2" --include="*.kt" --include="*.ts"
grep -r "strata:port L2" --include="*.go"

# 특정 도메인의 모든 파일 검색
grep -r "strata:domain inventory" --include="*.kt" --include="*.go" --include="*.ts"

# 자동 생성 파일 검색
grep -r "strata:generated" --include="*.kt" --include="*.go" --include="*.ts"
```

## PAL 마커로부터의 마이그레이션

PAL(Port-Adapter Layered) 마커는 strata 이전 프로젝트 레벨 컨벤션입니다.
PAL 레이어 번호는 strata 정식 번호와 불일치하므로, 마이그레이션 시 번호 변환이 필요합니다.

| PAL 마커 | strata 마커 | 번호 변환 |
|---|---|---|
| `@pal-port L1-SomeService` | `@strata:port L2-SomeService` | PAL L1 → strata L2 |
| `@pal-layer l1` | `@strata:layer L2` | PAL L1 → strata L2 |
| `@pal-layer l2` | `@strata:layer L3` | PAL L2 → strata L3+Route |
| `@pal-domain inventories` | `@strata:domain inventories` | (동일) |
| `@pal-generated` | `@strata:generated` | (동일) |
| `@pal-adapter jooq` | `@strata:adapter jooq` | (동일) |
| `@pal-depends L1-Other` | `@strata:depends L2-Other` | PAL L1 → strata L2 |

### 마이그레이션 절차

1. strata 코어에 마커 명세 추가 (이 문서)
2. 대상 프로젝트에서 PAL → strata 일괄 치환 (`sed` 또는 IDE)
3. 레이어 번호 매핑 적용 (PAL L1 → strata L2 등)
4. 기존 `PAL-MARKERS.md`를 이 문서 참조로 교체
