# 검증 티어 (Verification Tier)

> 정본: strata-kit `core/docs/ko/methodology/verification-tier.md` (2026-10-29 strata `docs/04-agents/verification-tier.md` 에서 이관, DEC-2026-10-29-11).

> 실행 모드(Verbal/Task)와 직교하는 검증 독립성 축.
> 실행 모드가 *어떻게 작업하는가*라면, 검증 티어는 *결과를 누가 검증하는가*를 정의한다.
> `verification_tier` enum의 source of truth는 이 문서다.

## Tier 정의

| Tier | enum 값 | 정의 | 검증 독립성 |
|------|---------|------|------------|
| **Solo** | `solo` | 실행 주체가 자체 체크리스트로 검증 | 없음 |
| **Self-Verified** | `self_verified` | 같은 실행 환경/도구군 내 독립 Reviewer가 검증 | 중간 |
| **Cross-Verified** | `cross_verified` | 다른 실행 환경·도구군·모델 계열의 Reviewer가 검증 | 높음 |

- 도구 이름은 Core에 적지 않는다. "X 실행 → Y 검증" 같은 매핑은 도구별 어댑터(AGENTS.md, settings)에 둔다.
- Reviewer는 전체 대화가 아니라 **요청 + diff + 규칙 + 테스트 결과 + 체크리스트**만 본다.
- 표시명은 `Cross-Verified`, `_order.yaml`에 쓰는 enum 값은 `cross_verified`다.

## 기본값과 필수 범위

```text
Verbal Mode: verification_tier 생략 시 → solo
Task Mode:   _order.yaml에 verification_tier 명시 권장
Core source-of-truth 변경 (layer-rules / naming-convention / task-spec-schema / agent-roles):
             → cross_verified 필수
그 외 Core 문서·어댑터 변경 (core/docs/, core/templates/ 등):
             → cross_verified 권장
```

작은 수정마다 Tier를 선언하게 하지 않는다. 선언 비용이 검증 이득보다 커지면 Strata가 무거워진다.

## 구현 패턴

TDD Writer/Reviewer(`core/docs/ko/methodology/session-splitting.md` §2.4)는 Self/Cross-Verified Tier의 구현 패턴 중 하나다.
세션을 어떻게 나눌지는 session-splitting 문서가 다루고, 검증 독립성의 의미와 enum은 이 문서가 갖는다.

Cross-Verified의 구체 도구 구현은 `skills/strata.review/SKILL.md`가 다룬다.
그 스킬이 이 문서의 `cross_verified`를 실제로 수행하는 절차이며, 이 문서는 그 절차를 정의하지 않는다.

## 다른 축과의 관계

- **Execution Mode**: Verbal/Task 선택과 전환은 `core/docs/ko/methodology/execution-modes.md`가 정의한다.
- **Agent Operations**: Decision Inbox의 `reviewer: cross_verified`는 이 Tier를 사용한다. 운영 규율은 `core/docs/ko/methodology/agent-operations.md`가 정의한다.
- **Methodology Feedback Loop**: Reviewer가 발견한 방법론 빈틈은 `core/docs/ko/methodology/task-spec-schema.md` 의 Promotion Gate 흐름으로 backlog에 적재·승격한다.

## 디자인 검증 축 (design_verified)

실행 모드·검증 티어와 직교하는 세 번째 축. **디자인 산출물과 구현의 정합**(`core/docs/ko/architecture/frontend-design-contract.md` §디자인 산출물과 정합)을 누가 확인했는가를 정의한다.
`_order.yaml`의 `design_verified` enum은 이 문서가 source of truth다.

| 값 | 정의 |
|---|---|
| `none` | UI 산출물 없음 (`design_ref.kind: none`) 또는 미검증 |
| `self` | 구현자가 정합 정의(이름·축·alias·상태 축)로 자체 대조 |
| `designer` | 디자인 산출물 소유자(디자이너 또는 디자인 도구 담당)가 확인 |
| `cross` | 다른 실행 환경·모델의 Reviewer가 스토리 렌더/프레임 대조로 확인 |

기본값과 필수 범위:

```text
design_ref 없음 또는 kind: none → none
Primitive UI · Semantic Component 신규/변경 (공유 UI 패키지) → designer 이상 권장
Feature Block · Route Surface → self 이상
```

`completion.design_sync`가 `stale`이면 이 축의 값과 무관하게 완료가 아니다. `waived`는 사유와 만료일을 가진다.

