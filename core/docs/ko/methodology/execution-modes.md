# 실행 모드 (Execution Modes)

> 정본: strata-kit `core/docs/ko/methodology/execution-modes.md` (2026-10-29 strata `docs/04-agents/execution-modes.md` 에서 이관, DEC-2026-10-29-11).

> Strata 방법론의 이중 실행 모드를 정의합니다.
> 모든 세션은 시작 시 실행 모드를 명시적으로 선언해야 합니다.

## 원칙

- **기본값은 Task Mode** — 선언하지 않으면 Task Mode로 간주
- **Verbal Mode는 의도적 예외** — 명시적으로 선택해야 사용 가능
- **모드 전환은 단방향** — Verbal → Task 전환 가능, Task → Verbal 전환 금지

> **작업 모드와의 대응 (2026-10-29, DEC-2026-10-29-15·19)**: 진입 스킬(using-strata 4단계)의 네 작업 모드가 이 두 모드를 나눈 것이다. Verbal = 읽기 전용(조사·질문·리뷰) + 태스크 파일 없이 끝나는 단일 세션 변경, Task = 여러 세션(오더가 있는 작업) + 오케스트레이션(여러 세션·역할 병렬). 세션이 지는 의무(활성 파일·핸드오프·오더)는 작업 모드가 정하고, 아래 정량 기준은 Verbal 로 끝낼 수 있는지 판단하는 데 쓴다.
- **상태 변경 전 요약·확인** — 파일 수정, 세션 주입, 외부 CLI 호출, 커밋/배포처럼 되돌리기 어렵거나 관찰 상태를 바꾸는 작업은 진행 내용 요약본을 먼저 제시하고 사용자 확인 후 실행

## 모드 정의

### Task Mode (기본)

Builder가 `_order.yaml` + `task-{nn}.yaml` 명세를 작성하고, Worker가 명세를 기반으로 실행하는 모드.

**적용 시점:**
- 스프린트 단위 실행 계획
- 멀티세션 기능 구현
- 3개 이상 파일 변경
- 2개 이상 레이어 영향
- 새로운 아키텍처 패턴 수립

**의무 사항:**
- `_order.yaml` 작성 (작업지시서)
- 개별 `task-{nn}.yaml` 작성 (Worker 실행 명세)
- TASK_TRACKER.md 갱신
- 핸드오프 문서 작성
- 아키텍처 결정 시 KB 환류

### Verbal Mode (예외)

Builder가 직접 실행하거나, 구두 지시로 빠르게 처리하는 모드.

**적용 지점:**
- 아이디에이션, 탐색, 설계 리뷰
- 단일 파일 수정
- 버그 핫픽스 (긴급)
- 문서 수정, 설정 변경
- 10턴 이내 완료 가능한 작업

**의무 사항:**
- 태스크 명세 불필요
- TASK_TRACKER 갱신 불필요
- 핸드오프 선택적 (결정사항 있으면 기록)
- **결정 발생 시 decision 레코드 기록(decision writer CLI)은 면제 불가** (모드 무관 절대 규칙 — `decisions.yaml`은 생성 인덱스, 손편집 금지)

## 모드 선택 기준 (정량적)

```
IF (수정 파일 ≤ 3) AND (영향 레이어 ≤ 1) AND (예상 턴 ≤ 10)
   AND (새 도메인 = 0) AND (탐색 단계 ≤ 1):
    → Verbal Mode 허용
ELSE:
    → Task Mode 강제
```

| 지표     | Verbal 허용 | Task 강제 |
| ------ | --------- | ------- |
| 수정 파일  | ≤ 3       | 4+      |
| 영향 레이어 | 1         | 2+      |
| 예상 턴   | ≤ 10      | 11+     |
| 새 도메인  | 0         | 1+      |
| 탐색 단계  | ≤ 1       | 2+      |

**모든 조건이 Verbal 범위일 때만 Verbal 허용. 하나라도 초과하면 Task 강제.**

## 모드 선언

세션 시작 시 이 세션의 파일 `.strata/local/active/{session}.yaml`에 모드를 기록하고, 하네스 세션 ID(Claude Code 는 `CLAUDE_CODE_SESSION_ID`)를 `harness_session_id` 에 적는다 — 시작 헤더와 컴팩션 복원은 이 필드나 파일 이름으로 이 세션의 파일을 찾는다:

```yaml
harness_session_id: "9496c8b3-…"   # CLAUDE_CODE_SESSION_ID
session:
  date: "2026-04-23"
  mode: "verbal"              # verbal | task
  declared_scope: "디바운스 설계 검토 및 브리핑"
  escalation_threshold: 3     # 이 파일 수 초과 시 task mode 전환
  order_ref: null              # task mode일 때 _order.yaml 경로
```

## 모드 전환 (Verbal → Task)

Verbal로 시작했으나 스코프가 커진 경우:

1. Builder의 5턴 자기진단에서 감지 (파일 수, 레이어 수 체크)
2. 사용자에게 "Task Mode 전환 필요" 보고
3. `_order.yaml` 작성 — `escalated_from: "verbal"` 필드 포함
4. 이미 완료한 작업은 `_order.yaml`의 `completed_before_spec` 섹션에 기록
5. 이후 작업은 태스크 명세 기반으로 진행

```yaml
# _order.yaml (전환 시)
order:
  id: "2026.04.23-01"
  title: "디바운스 MongoDB 동기화"
  escalated_from: "verbal"
  completed_before_spec:
    - "CacheGenericOperator SET 연산 추가 (verbal 단계에서 완료)"
  tasks:
    - id: "task-01"
      title: "DirtyMarkService 구현"
      # ... 이후 태스크는 정상 명세
```

## 모델 할당 전략

Worker 태스크에 실행 **추론 등급(reasoning tier)**을 명시합니다. 구체 모델명이 아니라 등급을 쓰며, 등급→모델 매핑은 도구 어댑터가 담당합니다 (도구중립).

### 추론 등급별 할당 기준

| 등급 | 할당 기준 | 상대 비용 | 대표 작업 |
|------|----------|----------|----------|
| **deep** (고추론) | 신규 패턴 수립, 크로스레이어 추론, 복잡한 리팩토링 | 높음 | 아키텍처 설계+구현, 신규 시스템 |
| **standard** (표준) | 기존 패턴 답습, 단일 레이어 CRUD, 테스트, 문서화 | 낮음 | REST Docs, QueryService 추가, KB 문서 |
| **light** (경량) | 문서 검색, 규칙 조회, 단순 요약 | 최저 | KB 검색, 핸드오프 요약 |

> **등급→모델 매핑은 Core가 아니라 도구 어댑터의 책임이다.** (어댑터 예시 — Claude: `deep→Opus`, `standard→Sonnet`, `light→Haiku`. 이 매핑은 어댑터 맥락이며 Core 규칙이 아니다.)

### 모델 선택 의사결정 트리

```
태스크가 기존 패턴을 답습하는가?
  ├─ YES → 참조 구현이 명확한가?
  │         ├─ YES → standard
  │         └─ NO  → deep (패턴 해석 필요)
  └─ NO  → 신규 아키텍처 판단이 필요한가?
            ├─ YES → deep
            └─ NO  → standard (단순 신규 코드)
```

### 태스크 명세 내 등급 표기

```yaml
execution:
  model_tier: "standard"
  model_reason: "기존 REST Docs 패턴 답습, 신규 판단 불필요"
```

`model_reason`은 필수. Builder가 모델 선택 근거를 명시해야 다음 세션에서도 동일 기준을 적용할 수 있습니다.

## 에이전트별 기본 추론 등급

| 에이전트 | 기본 등급 | 변경 가능 |
|---------|----------|----------|
| Builder | deep | 불가 (오케스트레이션은 항상 고수준 추론 필요) |
| Worker | 태스크별 지정 | 가능 (deep 또는 standard) |
| Supporter | light/standard | 가능 (검색은 light, 요약은 standard) |

> 구체 모델은 도구 어댑터가 등급에 매핑한다 (위 "등급→모델 매핑" 주석 참조). Core는 등급만 규정한다.

## 검증 축 (Verification Tier)

검증 축은 실행 모드와 직교한다. 실행 모드가 *어떻게 작업하는가*라면, 검증 축은 *결과를 누가 검증하는가*를 다룬다.
enum 값은 `solo | self_verified | cross_verified`다.
정의, 기본값, Core SoT 변경 시 `cross_verified` 필수 범위는 `core/docs/ko/methodology/verification-tier.md`가 source of truth다.
Cross-Verified 검토는 `skills/strata.review/SKILL.md`(리뷰 패킷을 새 컨텍스트의 리뷰어에게 한 번 보낸다)로 한다.

## 방법론 피드백 루프 (Methodology Feedback Loop)

Worker/Reviewer가 발견한 방법론 빈틈은 `methodology_signals`로 보고하고, Builder가 backlog에 적재·승격한다.
흐름과 Promotion Gate는 `core/docs/ko/methodology/task-spec-schema.md` 의 "Promotion Gate" 절이 source of truth다.
`methodology_signals`와 `methodology-backlog.yaml` 필드 스키마는 `core/docs/ko/methodology/task-spec-schema.md`가 정의한다.

## 운영 축 (Agent Operations)

실행 모드·검증 축 위에, 에이전트를 **여럿·오래** 돌릴 때의 운영 규율은 별도 축으로 다룬다:
멀티세션(hub-and-spoke), 야간 배치(budgeted batch), Decision Inbox, 자기신고 검증 게이트.
→ `core/docs/ko/methodology/agent-operations.md` (이 문서는 참조만, 규칙 정의는 거기)

## 절대 규칙 (모드 무관)

> **정본은 이 절이 아니다** (DEC-2026-10-29-19). 어떤 규칙이 이 프로젝트에 적용되는지는 헌법(`core/constitution/constitution.yaml`의 조항)과 프로젝트가 채택한 카드(마법사가 쓴 `.strata/kit/registry.yaml`의 `must_cards`)가 정하고, 생성 지침(AGENTS.md)이 그 집합을 싣는다. 규칙 문구의 정본은 `core/cards/`의 카드다.
> 이 절은 그 카드들이 나온 원문과 근거(사고·이유)를 남겨 둔 것이다. 헌법 1.2.0 부터 5·7 은 조항이 아니라 프로젝트가 채택할 때만 적용되는 채택형 must 다. 규칙을 바꿀 때는 카드와 헌법을 고치고(결정 레코드), 이 절은 고치지 않는다.

원문(2026-09-30, DEC-2026-09-30-02 당시 모든 세션에 적용하던 목록):

1. **상태 변경 전 진행 내용 요약본 제시 + 사용자 확인**
   - 대상: 파일 수정, 세션 파일/릴레이 주입, 외부 CLI 호출, 커밋/배포/삭제, 장기 실행 작업, 비용·권한·데이터에 영향을 주는 작업
   - 요약본에는 목적, 실행할 작업, 변경/영향 범위, 검증 방법, 되돌림/중단 조건을 포함한다
   - 단순 조회·검색·파일 읽기처럼 상태를 바꾸지 않는 조사는 예외로 허용한다
   - **semantic vs mechanical**: 의미·규칙·계약을 바꾸는 semantic 변경은 승인 필수. 의미불변의 mechanical 변경(오탈자·링크·포맷)은 **static하게 증명 가능할 때만** 자동 허용 후보다. 애매하면 승인 쪽으로 둔다. LLM의 자기 "mechanical" 판단을 자동허용 근거로 쓰지 않는다
2. **아키텍처 결정 발생 시 decision 레코드 즉시 기록** (decision writer CLI — 인덱스·vault DEC 노트 자동 재생성)
3. **레이어 위반 금지** — 하네스가 막는 강도는 프로젝트의 집행 등급이 정한다(DEC-2026-10-29-17). 에이전트는 등급과 무관하게 새 위반을 쓰지 않는다
4. **네이밍 컨벤션 준수** — Hook이 경고
5. **Soft Delete만 사용** — 채택형(헌법 1.2.0, DEC-2026-10-29-14): 저장소가 있는 프로젝트가 채택할 때 적용
6. **세션 상태·진행 중 작업·핸드오프는 대화 컨텍스트가 아니라 파일에 남긴다** — 상태를 바꾸는 세션에 적용, 읽기 전용 세션은 남길 상태가 없다(DEC-2026-10-29-15) — 세션 중단 시 이 세션의 `.strata/local/active/{session}.yaml`(단일 파일 `active-task.yaml` 은 세션별 파일이 없을 때만 읽는 이전 형식)에 현재 상태를 기록하고, 핸드오프·작업 이력은 vault 에 둔다
7. **작업 트리(git worktree)는 사용자 동의가 있을 때만 만든다** (DEC-2026-09-17-01) — 채택형(헌법 1.2.0): 사용자 기본 채택 목록이나 프로젝트가 채택할 때 적용
   - 자동 모드에서도 같다. 도구 어댑터의 작업 트리 격리(예: Claude Code Agent 도구 `isolation: "worktree"`, `EnterWorktree`)와 `git worktree add` 가 모두 해당한다
   - 기본은 사용자가 보는 체크아웃의 단일 브랜치에서 순차로 작업한다. Worker 를 여럿 쓰더라도 같은 체크아웃에서 순서대로 실행한다
   - 병렬 세션·병렬 Worker 로 작업 트리가 정말 필요할 때만 필요성, 브랜치 이름, 정리 계획을 한 항목으로 제안하고 수락한 경우에만 만든다. 한 번의 수락은 그 제안에만 유효하다
   - 동의를 받아 만든 작업 트리는 태스크가 끝나면 브랜치를 남기고 정리하며, 위치와 브랜치를 보고한다
   - 이유: 작업 트리로 분리하면 에이전트가 쓴 내용의 리뷰·검토가 정상 동작하지 않고, 사용자가 변경과 작업 내역을 직접 확인할 수 없으며 형상 추적이 어렵다
8. **추정을 확인하기 위한 배포는 배포로만 재현할 수 있는 환경에 한정한다** (DEC-2026-09-18-01, strata)
   - 코드 읽기·로그·단위 테스트·로컬 실행으로 확인할 수 있는 추정은 배포로 확인하지 않는다. 공유 환경(dev·stage)에 올리는 것은 그 환경에서만 재현되는 현상(인프라·라우팅·다른 서비스와의 연동·실데이터)을 확인할 때뿐이다
   - 배포 전에 무엇을 확인하려는지, 확정된 사실과 추정을 나눠 적고, 되돌리는 방법(revert 커밋·이전 이미지)을 함께 보고한다
   - 인증·라우팅·세션처럼 다른 라인이나 다른 사용자에게 영향이 가는 변경은 그 라인의 사용자 흐름(예: 2.0 로그인과 3.0 로그인 모두)으로 실측한 뒤에만 올린다
   - 이유: 2026-09-18 stage 에서 추정만으로 게이트웨이 라우트를 승격했다가 2.0 로그인이 깨졌고, 추정을 고쳐 다시 올리는 배포가 하루에 여러 번 반복됐다. 배포는 되돌리는 데도 시간이 들고 다른 사람의 작업을 막는다
9. **핸드오프의 미결(pending) 항목에는 막힌 이유(blocker)와 풀리는 조건(unblocked_by)을 함께 적는다**
   - "대기" 만 적는 것은 금지한다. 다음 세션이 무엇을 기다리는지 모르면 미결이 이월만 된다
