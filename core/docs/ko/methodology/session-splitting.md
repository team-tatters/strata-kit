# 02 — 세션 분할 가이드

> 정본: strata-kit `core/docs/ko/methodology/session-splitting.md` (2026-10-29 strata `docs/02-session-splitting.md` 에서 이관, DEC-2026-10-29-11).

> Builder가 작업 지시서를 작성하기 전에 반드시 참조하는 문서입니다.
> 세션 분할은 "컨텍스트 유실 방지"를 위한 가장 효과적인 전략입니다.

## 1. 분할 판단 매트릭스

### 1.1 정량 기준

| 지표 | 단일 세션 | 2-3 세션 | 4+ 세션 |
|---|---|---|---|
| 변경 파일 수 | ≤15 | 16-40 | 40+ |
| 영향 레이어 수 | 1-2 | 3 | 4+ |
| 참조 파일 수 | ≤10 | 11-25 | 25+ |
| 예상 대화 턴 | ≤20 | 21-40 | 40+ |
| 새 도메인 개수 | 1 | 2 | 3+ |
| 필요한 탐색 단계 | ≤2 | 3-4 | 5+ |

### 1.2 정성 기준

**즉시 분할이 필요한 상황:**
- "먼저 A를 조사해보고, 결과에 따라 B 방향을 결정" → 탐색 세션 + 구현 세션
- "기존 코드를 리팩토링하면서 새 기능도 추가" → 리팩토링 세션 + 기능 추가 세션
- "프론트엔드와 백엔드를 동시에 변경" → FE 세션 + BE 세션
- "테스트를 먼저 작성하고, 구현 후 검증" → TDD 세션 (Writer/Reviewer 패턴)

**단일 세션이 적합한 상황:**
- 단일 파일 버그 수정
- 기존 패턴과 동일한 CRUD 추가
- 테스트 보완
- 문서 업데이트
- 설정 변경

## 2. 분할 패턴 카탈로그

### 2.1 레이어 순차 분할 (Layer-Sequential)

가장 일반적인 패턴. 새로운 기능을 바닥부터 올려야 할 때.

```
요청: "주문(Order) 도메인을 새로 구현해주세요"

Session 1: L1 + LM1 (기초)
├── OrderEntity, OrderStatus enum, OrderType 정의
├── MongoDB Document 매핑
└── 공통 Audit Entity 상속 설정
    → 핸드오프: 엔티티/타입 확정, 다음은 L2

Session 2: L2 DataLayer (데이터)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── 단위 테스트
    → 핸드오프: L2 완성, 다음은 LM2 또는 L3

Session 3: L3 Composite (비즈니스)
├── OrderCompositionService
├── 결제 연동 로직 (PaymentCoordinator 사용)
├── 재고 차감 로직 (InventoryCoordinator 사용)
└── 통합 테스트
    → 핸드오프: L3 완성, 다음은 Controller

Session 4: Route Controller (API)
├── OrderController (엔드포인트 정의)
├── Request/Response DTO
├── Validation 설정
└── API 문서 생성
```

### 2.2 도메인 병렬 분할 (Domain-Parallel)

같은 레이어에서 여러 도메인을 동시에 작업할 때.

```
요청: "User, Order, Product 도메인의 L2를 모두 구현해주세요"

Session A: L2 — User 도메인 (독립)
Session B: L2 — Order 도메인 (독립)
Session C: L2 — Product 도메인 (독립)

전제: L1 Component가 사전 확정되어야 함
전제: 각 도메인 간 L2 상호참조가 없어야 함 (Strata 규칙에 의해 보장)
```

### 2.3 탐색-구현 분할 (Explore-Implement)

방향이 불확실한 작업에서 사용.

```
요청: "성능이 느린 부분을 찾아서 최적화해주세요"

Session 1: 탐색 (Explore)
├── 코드 분석 및 병목 지점 식별
├── 프로파일링 결과 해석
├── 최적화 전략 3가지 도출
└── 탐색 결과를 $STRATA_VAULT/projects/{name}/sessions/ 에 기록 (Tier V)
    → 핸드오프: 최적화 전략 확정, 세부 구현 계획

Session 2-N: 구현 (Implement)
├── 확정된 전략에 따른 코드 변경
├── 성능 테스트
└── 결과 기록
```

### 2.4 TDD 분할 (Writer/Reviewer)

Anthropic이 권장하는 Writer/Reviewer 패턴.

> **검증 축과의 관계:** 이 Writer/Reviewer 패턴은 `core/docs/ko/methodology/verification-tier.md`의 **Verification Tier**
> (Self-Verified / Cross-Verified)를 세션 분할로 구현한 **사례 중 하나**다.
> Tier 정의는 `core/docs/ko/methodology/verification-tier.md`가 source of truth이며, 여기서는 중복 정의하지 않는다.
> - Reviewer가 같은 도구군이면 → **Self-Verified**
> - 다른 모델 계열이면 → **Cross-Verified** (구현: `skills/strata.review/SKILL.md`)

```
Session 1: 테스트 작성 (Writer)
├── 요구사항 기반 테스트 케이스 작성
├── 모든 테스트가 실패하는 것을 확인
└── 테스트 파일을 commit

Session 2: 구현 (Writer)
├── Session 1의 테스트를 통과시키는 코드 작성
├── 모든 테스트 통과 확인
└── 구현 코드를 commit

Session 3 (선택): 리뷰 (Reviewer)
├── 새로운 컨텍스트로 코드 리뷰
├── Session 2의 코드가 레이어 규칙을 준수하는지 검증
└── 리팩토링 제안
```

### 2.5 프론트-백 분할 (Frontend-Backend)

```
요청: "주문 기능의 UI와 API를 모두 구현해주세요"

Session BE: 백엔드
├── L2-L3-Controller 구현
├── API 스펙 문서 확정 ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── 핸드오프: API 엔드포인트 + DTO 확정

Session FE: 프론트엔드
├── API 스펙(Contract)을 참조 — BE 완료가 아니라 **Contract 확정**이 선행 조건. mock transport 로 먼저 갈 수 있다
├── Frontend variant에 맞춘 Contract/DataState/Feature 순서
├── entry_point(design_first | dev_first | spec_first | change) 선언 — 순서는 고정하지 않고 정합 검사가 게이트 (core/docs/ko/architecture/frontend-design-contract.md)
└── API 통합 테스트 + Impl↔Design 정합 확인 (design_sync)
```

BE 세션과 FE 세션은 Contract가 확정되면 병행할 수 있다. FE가 먼저 나가는 `dev_first`도 허용된다 — 이 경우 Contract는 FE 세션의 산출물이고 BE 세션이 그것을 검증한다.

## 3. 작업 지시서 (Task Specification) 형식

Builder가 각 세션을 위해 작성하는 문서:

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "Order L2 DataLayer 구현"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (다른 도메인)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # 이전 세션 ID (없으면 null)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # 패턴 참조

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "CUD 트랜잭션 서비스"
    - path: "src/data/order/OrderQueryService.ts"
      description: "읽기 전용 쿼리 서비스"
    - path: "src/data/order/OrderRepository.ts"
      description: "MongoDB Repository 구현"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "CommandService 단위 테스트"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "QueryService 단위 테스트"

acceptance_criteria:
  - "모든 단위 테스트 통과"
  - "레이어 의존성 위반 없음 (Hook 검증 통과)"
  - "네이밍 컨벤션 준수"
  - "하나의 메서드는 하나의 엔티티만 관리"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # 참조 파일 토큰 한도
  compaction_strategy: "file-based"  # 결정사항은 파일에, 컨텍스트는 가볍게
```

## 4. Builder의 분할 제안 프로토콜

Builder가 사용자 요청을 받았을 때 수행하는 분석 절차:

```
사용자: "주문 관리 기능을 전체적으로 구현해줘"

Builder 분석:
┌─────────────────────────────────────────┐
│ 📋 작업 범위 분석                        │
│                                          │
│ 영향 레이어: L1, L2, LM2, L3, Route (5) │
│ 예상 변경 파일: ~35개                     │
│ 예상 참조 파일: ~15개                     │
│ 예상 대화 턴: ~60회                       │
│                                          │
│ ⚠ 판정: 세션 분할 필요 (4개 세션 권장)    │
│                                          │
│ 제안:                                    │
│ Session 1: L1 엔티티/타입 (15분, ~8턴)   │
│ Session 2: L2 DataLayer (30분, ~15턴)    │
│ Session 3: L3 Composite (30분, ~15턴)    │
│ Session 4: Controller + API (20분, ~12턴)│
│                                          │
│ 병렬 가능: Session 2의 하위 도메인 분리   │
│ 의존 체인: S1 → S2 → S3 → S4            │
└─────────────────────────────────────────┘
```

Builder는 이 분석을 **사용자에게 먼저 보여주고 승인을 받은 후** 작업 지시서를 생성합니다.

## 5. 세션 종료 신호

Builder가 현재 세션을 종료하고 핸드오프해야 하는 시점:

| 신호 | 대응 |
|---|---|
| 대화 턴 15회 초과 | 현재 작업 단위 완료 후 핸드오프 |
| Compaction 발생 | 즉시 상태 저장, 가능하면 현재 단위 완료 후 핸드오프 |
| "이전에 말씀드린..." 재설명 필요 | 컨텍스트 유실 징후 — 즉시 핸드오프 준비 |
| 레이어 경계를 넘는 작업 진입 | 현재 레이어 완료 후 다음 세션으로 |
| 탐색 결과 기반 방향 전환 | 탐색 결과 문서화, 구현은 새 세션 |
| 사용자의 요구사항 변경 | 변경 사항 문서화, 재분석 후 새 계획 |
| 대화가 경고선(기본 약 40만 토큰)을 넘음 | 하던 단위를 마무리하고 다음 작업 경계에서 핸드오프(사실과 가설 절 포함) 후 새 세션. 늦어도 한계선(기본 약 60만) 전에 — 5.1 |
| 같은 가설로 시도가 두 번 막힘 | 세 번째 우회를 찾지 않고 멈춰서 실측 사실과 선택지를 보고 — 5.1 |

### 5.1 재시작 신호: 토큰 경고선과 같은 가설의 두 번 실패

두 신호는 지금 하던 일을 그 자리에서 끊으라는 기준이 아니라, 하던 단위를 마무리하고 다음 작업 경계에서 나누라는 신호다(카드 `rec.session.split-at-task-boundary`). 압축은 창이 거의 찼을 때 일어나므로 창이 클수록 늦게 개입하고, 한 가설에 매달린 대화는 길이와 상관없이 판단을 흐린다. 두 신호는 이 두 경우를 잡는다.

**토큰 경고선과 한계선.** 대화가 약 40만 토큰을 넘으면 하던 단위를 마무리하고 다음 작업 경계에서 핸드오프를 쓴 뒤 새 세션으로 넘어간다. 다음 경계가 멀어도 약 60만 토큰 전에는 넘긴다. 두 값은 창 크기의 비율이 아니라 고정 토큰 수다(DEC-2026-10-31-09, 값은 DEC-2026-10-31-33). 1M 창을 기본으로 쓸 때 압축보다 한참 앞에서 세션을 정리하려는 출발값이고, 우리 작업에서 실측한 근거는 아직 없다. 사용자 설정 `~/.strata/config.yaml` 의 `session.restart_tokens`·`session.restart_limit` 으로 바꾸며, 시작 헤더의 `restart signal` 줄이 지금 값을 보인다. Claude Code 에서는 `/context` 명령이나 상태 줄의 사용량으로 지금 크기를 본다. 에이전트가 직접 읽을 수 없으면 사람이 알려 준다.

**같은 가설로 두 번 실패.** 시도가 두 번 막히면 세 번째 우회를 찾지 말고 멈춰서 실측 사실과 선택지를 보고한다. 같은 가설이란 같은 원인 추정이다. 고친 곳이 달라도 "원인은 X 다"라는 추정이 같으면 같은 가설이다. 실패란 확인하려던 증상(같은 테스트 실패, 같은 오류)이 그대로 남은 것이다. 보고한 뒤 사람이 방향을 정하거나, 핸드오프에 버린 가설을 적고 새 세션에서 다시 본다.

**핸드오프의 사실과 가설 절.** 재시작 신호로 끝나는 세션은 핸드오프의 '사실과 가설' 절에 확인된 사실(무엇으로 확인했는지와 함께), 확인하지 못한 추정, 버린 가설(버린 이유와 함께)을 나눠 적는다(DEC-2026-10-31-11). 다음 세션은 이 절을 먼저 읽고 버린 가설을 다시 붙잡지 않는다. 원장으로 일하는 세션은 같은 세 칸을 재시작 엔트리에 적는다(agent-operations 5.3).

### 5.2 대화 토큰 예산과 압축 시점

| 창 크기 | 기본 자동 압축 | `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` 일 때 | 경고선 40만·한계선 60만과의 관계 |
|---|---|---|---|
| 20만 토큰 | 20만(창 한계) | 16만 | 압축이 먼저 온다. 이 창에서는 압축 발생 신호가 경고선 역할을 한다 |
| 100만 토큰 | 약 96만 7천 | 약 77만~80만 | 경고선과 한계선이 압축보다 먼저 온다 |

고정 비용은 하네스 시스템 프롬프트, 도구 정의, 지침, 시작 헤더, 메모리다. strata-kit 이 더하는 지침과 헤더는 약 8~12KB(대략 3천~5천 토큰)이고(`wizard verify`), 나머지는 하네스와 연결된 MCP 서버 수에 따라 다르므로 `/context` 로 본다.

기본 압축 시점은 Claude Code 문서(model-config)의 값이다. 압축 창(`autoCompactWindow` 설정, `/autocompact` 명령, `CLAUDE_CODE_AUTO_COMPACT_WINDOW` 환경 변수, 10만~100만)은 그만큼 차면 압축하는 값이고, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` 는 이 창에 곱하는 비율이라 압축을 앞당기기만 한다. 환경 변수에 `500k` 같은 단위 표기는 v2.1.304 이상에서만 읽는다. 큰 창에서는 압축이 경고선보다 한참 뒤에 오므로, 세션 정리는 압축이 아니라 경고선과 한계선이 맡는다. 압축 설정을 바꿀지는 사용자가 정한다.

## 6. /split-session 명령어 동작 흐름

사용자가 `/split-session`을 실행하면 Builder가 수행하는 절차:

```
1. 현재 요청의 범위를 분석
2. 분할 매트릭스 적용 (섹션 1 참조)
3. 분할 계획을 사용자에게 제안
4. 승인 시:
   a. 각 세션별 task-{id}.yaml 생성
   b. TASK_TRACKER.md 업데이트
   c. 의존성 순서 명시
   d. 첫 번째 세션 즉시 시작 또는 전체 계획만 저장
```
