# 태스크 명세 스키마 (Task Specification Schema)

> 정본: strata-kit `core/docs/ko/methodology/task-spec-schema.md` (2026-10-29 strata `docs/04-agents/task-spec-schema.md` 에서 이관, DEC-2026-10-29-11).

> Builder가 생성하고 Worker가 소비하는 태스크 명세의 구조를 정의합니다.
> 태스크 명세는 **자기완결적** — Worker가 명세만으로 코드를 완성할 수 있어야 합니다.

## 저장 위치

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # Work Order 폴더
      _order.yaml                   # 작업지시서 (Builder 생성)
      task-{nn}-{title}.yaml        # Worker 실행 명세
```

### 위치 선택 근거

- `$STRATA_VAULT` — 프로젝트 저장소에 영향 없음 (별도 레포)
- `tasks/` — KB 문서(knowledge-base/)와 분리, 검색 인덱스 대상 아님
- `{yyyy.mm.dd}/` — 시간 흐름 기반 추적, 인지 부하 최소화
- `{nn}-{title}/` — 같은 날 복수 작업지시 구분, 시퀀스 + 제목으로 식별

### 네이밍 규칙

| 요소            | 형식                             | 예시                              |
| ------------- | ------------------------------ | ------------------------------- |
| 날짜 폴더         | `yyyy.mm.dd`                   | `2026.04.23`                    |
| Work Order 폴더 | `{nn}-{kebab-title}`           | `01-debounce-mongo-sync`        |
| 작업지시서         | `_order.yaml`                  | 항상 고정 (언더스코어 = 최상단)             |
| 태스크 파일        | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### 시퀀스 번호 규칙

- 해당 날짜 폴더의 기존 항목 수 + 1
- 멀티머신 동시 작업 시 번호 충돌 가능 → **title이 실제 식별자** 역할
- 번호 충돌은 정렬에만 영향, 기능적 문제 없음

---

## _order.yaml — 작업지시서

Builder가 태스크 분할 후 생성하는 매니페스트.

### 필수 필드

```yaml
order:
  id: "2026.04.23-01"                # {날짜}-{시퀀스}
  title: "Redis Debounce 기반 MongoDB 동기화 최적화"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    작업의 목적과 배경을 기술.
    왜 이 작업이 필요한지, 완료 시 어떤 상태가 되어야 하는지.

  context:
    prior_session: "session-2026-04-22-01"    # 이전 핸드오프 참조
    prior_decisions:                           # 이 작업에 영향을 주는 기존 결정
      - "PostProcessJob은 polling 방식 (@Scheduled fixedDelay=5000)"
    blocker_resolved: "PostProcessJob 시스템 구현 완료 (4/21)"
    kb_references:                             # 관련 KB 문서
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "CacheGenericOperator에 SET 연산 추가"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "DirtyMarkService 구현"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "DataUpsertListener debounce 전환"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "기존 즉시 처리 플로우 → dirty mark 플로우 전환 완료"
    - "단위 테스트 전체 통과"
    - "레이어 위반 0건"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # 완료된 task id 목록
```

### 선택 필드

```yaml
  escalated_from: "verbal"             # verbal → task 전환 시
  completed_before_spec:               # 전환 전 verbal로 완료한 항목
    - "CacheGenericOperator SET 연산 추가"
  
  estimated_sessions: 1                # 예상 세션 수
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # 절대 날짜

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (enum 값)
                                      #   생략 시 verbal=solo. Task Mode는 명시 권장.
                                      #   상세: core/docs/ko/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — 산출물(Spec·Design·Impl) 진입점.
                                      #   순서를 고정하지 않는다. 정합 검사가 게이트. 상세: core/docs/ko/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — 디자인 정합 검증 독립성 (core/docs/ko/methodology/verification-tier.md).
                                      #   UI 작업이 아니면 none.
  methodology_feedback:               # 방법론 피드백 루프 (선택)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **단, Core source-of-truth 변경 작업**(layer-rules / naming-convention / task-spec-schema / agent-roles)
> 에서는 `verification_tier: cross_verified`가 **필수**다 (`core/docs/ko/methodology/verification-tier.md`).
> 이 경우에 한해 verification_tier는 선택이 아니라 필수 필드로 취급한다.

### status 라이프사이클

```
drafting → open → in_progress → completed
                              → cancelled
```

| 상태 | 의미 | 전환 조건 |
|------|------|----------|
| `drafting` | Builder가 태스크 분할 중 | Builder가 _order.yaml 작성 시작 |
| `open` | 작업지시 확정, Worker 실행 가능 | 모든 태스크 명세 작성 완료 |
| `in_progress` | 일부 태스크 실행 중 | 첫 번째 Worker 실행 시작 |
| `completed` | 전체 태스크 완료 | 모든 acceptance 충족 |
| `cancelled` | 취소 | 명시적 취소 결정 |

`drafting` 상태의 작업지시는 다음 세션에서 Builder가 이어서 완성하거나 폐기합니다.

---

## _order.md — 작업지시서 신규 형식 (2026-08-19, DEC-2026-08-19-03)

신규 order는 `_order.md`로 작성한다 — **YAML frontmatter가 order 본체**(스키마는 위 `_order.yaml`과 동일)이고,
본문은 Obsidian 링크 그래프 편입을 위한 최소 마크다운이다.

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (_order.yaml 스키마 그대로)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- 기계 파싱 대상은 frontmatter뿐 — order 소비 스크립트는 `_order.yaml`과 `_order.md`(frontmatter)를 모두 지원한다.
- 본문에는 design 문서와 관련 DEC의 `[[wikilink]]`를 필수로 남긴다 (스파인 엣지 — session→order→design+DEC).
- 기존 `_order.yaml`은 소급 변환하지 않는다. `task-{nn}.yaml`은 yaml 유지 (그래프 편입은 order 노트가 담당).

---

## task-{nn}.yaml — Worker 실행 명세

Worker가 수신하는 자기완결적 태스크 문서.

### 전체 스키마

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "CacheGenericOperator에 SET 연산 추가"
  order_ref: "_order.yaml"             # 상위 작업지시서 참조

execution:
  model_tier: "standard"               # deep | standard | light (모델명은 도구 어댑터가 매핑)
  model_reason: "기존 CacheGenericOperator 패턴 답습"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # 이 태스크가 속한 주제 노드 — 커버리지 리졸버가 directories에서 유도
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # ADR에서 추출된 도메인 제약
    - id: "CC-NNN-NN"
      rule: "{해당 scope에 적용되는 constraint 1줄 규칙}"
  docs_to_update:                                 # directories·module 을 covers 로 소유한 명세 — 커버리지 리졸버가 주입
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths 일치 — SET 연산 추가는 명세의 연산 목록 변경"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "기존 패턴 참조 — ReactiveRedisOperations 사용법"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "레이어 규칙 확인"

  requirements: |
    구현해야 할 내용의 상세 명세.
    - 메서드 시그니처
    - 동작 설명
    - 제약 조건

  conventions: |
    적용할 컨벤션 요약 (Worker가 별도 파일을 읽지 않아도 되게).
    - PAL 마커 필수 (@pal-port, @pal-layer, @pal-domain, @Comment)
    - 네이밍: {Domain}{ServiceType}

  design_ref:                          # UI 를 만드는 태스크면 필수. 디자인 산출물 포인터 (core/docs/ko/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # 파일·노드·스토리 id·캔버스 URL
    version: "2026-04-23"              # 도구 버전 또는 스냅샷 일자 — 정합 검사 기준점
    reason: null                       # kind: none 이면 필수 (예: "텍스트 전용 관리 화면")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "SET 연산 4개 메서드 추가"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "SET 연산 단위 테스트"

acceptance_criteria:
  - "addToSet, popFromSet, getSetSize, getSetMembers 구현"
  - "기존 메서드 시그니처 변경 없음"
  - "단위 테스트 통과"
  - "레이어 위반 없음"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # Worker가 완료 시 채움 (아래 참조)
```

**`scope.nodes`와 `scope.docs_to_update`** — 태스크가 바꾸는 코드 표면을 소유한 명세(frontmatter `covers`)와 그 명세의 주제 노드를 Builder가 주입한다. `scope.constraints`와 같은 원리다. Worker는 리졸버를 돌리지 않고 주입된 값만 본다.
- 소유 명세가 없는 표면(신규 기능)이면 명세 생성을 `deliverables.files`에 포함하거나, `docs_to_update: []`와 함께 `inputs.requirements`에 의도적 비움 사유를 적는다. 사유 없는 빈 배열은 검증이 경고한다.
- 값 형식의 정본은 core/docs/ko/knowledge-base/document-format.md "노드·커버리지 필드" 절이다.

### completion 섹션 (Worker가 채움 — 단, `triage.review_gate`는 예외)

`completion.self_report`와 산출물 목록은 Worker가 채우지만, **`triage.review_gate`는
독립 재판정자(reviewer/relay)가 채운다** — 자기신고 검증 게이트의 전제(에이전트 ≠ 재판정자,
`core/docs/ko/methodology/agent-operations.md` §4)상 Worker가 스스로 채우면 게이트가 무력화된다.

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # scope.constraints 각 항목의 준수 결과
    - id: "CC-NNN-NN"
      met: true
      note: "{준수 근거 또는 특이사항}"
  design_sync: "aligned"                # aligned | stale | waived | none — Impl↔Design 정합 (inputs.design_ref 가 있으면 필수)
  design_sync_reason: ""                # waived 면 필수: 사유 + until YYYY-MM-DD. stale 이면 완료 선언 불가
  doc_change: "updated"                 # updated | none — scope.docs_to_update 처리 결과 (세션 frontmatter와 같은 키)
  doc_change_reason: ""                 # none 이면 필수 (예: "리팩터링만 — 외부 계약·정책 변화 없음")
  docs_updated:                         # updated 이면 갱신한 문서 (updated 스탬프·sources 에 이 태스크 추가)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "특이사항 없음"
  methodology_signals:                  # 선택 — 방법론 개선 신호 (리스트, 없으면 [] 또는 생략)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift: alias 밖 값·계약(축·상태) 불일치 발견 → 토큰/디자인 계약 개선 후보
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # scope:methodology이면 1개 이상 필수
        - "core/docs/ko/methodology/task-spec-schema.md"
      summary: "태스크 명세에 테스트 명령 필드가 없어 완료 검증 기준이 흔들림"
  triage:                               # 선택 — Agent Operations 출력 분류 (Decision Inbox용)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # 자기신고 검증 게이트 (필수 재판정 대상일 때)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # 재판정 후 확정 status
      max_review_rounds: 1
```

`methodology_signals`는 Worker가 작업 중 발견한 **방법론 자체의 빈틈**을 보고하는 채널이다.
한 completion에서 여러 빈틈(예: incomplete_spec + rule_gap)이 동시에 나올 수 있으므로 **리스트**다.
Builder는 각 항목을 개별 분류한다.
일반 `scope_issue`(현재 태스크의 막힘)와 달리, 규칙/스키마/컨벤션 개선 후보를 가리킨다.
Builder는 handoff 시 이를 backlog로 적재하고 승격 판정한다
(→ 아래 "Promotion Gate" 절).

`triage`는 출력을 사람이 보는 Decision Inbox로 보내기 전의 분류다. `self_report`는 에이전트가 채우고,
`review_gate`는 교차검증이 그 라벨을 재판정한다 (자기신고는 못 믿으므로). 규칙·위험기반 분기·재판정자
부재 폴백은 → `core/docs/ko/methodology/agent-operations.md` "Decision Inbox + 자기신고 검증 게이트".

---

## methodology-backlog.yaml — 개선 후보 누적

방법론 개선 후보를 쌓는 별도 파일. decisions.yaml(결정 기록)과 분리한다 —
backlog는 *후보*이고 lifecycle(검토→채택/기각)이 다르기 때문이다.
이 섹션은 backlog **필드 스키마와 lifecycle enum**의 source of truth다.
신호 흐름과 Promotion Gate도 이 섹션이 정의한다(아래 "Promotion Gate" 절, DEC-2026-10-29-12).

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # Strata Core 개선 후보
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # {project} 접두사로 중앙 승격 시 충돌 방지
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # scope:methodology이면 1개 이상 필수
      - "core/docs/ko/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "Worker가 테스트 명령 누락으로 완료 검증 불가 판정"
    proposed_action: "task schema에 verification.commands 필드 추가"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # 승격 시 "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### lifecycle

```
open → triaged → accepted → applied
              → rejected
```

| 상태 | 의미 |
|------|------|
| `open` | 신호 적재됨, 미검토 |
| `triaged` | Builder가 scope/중복/affected_core 확인 완료 |
| `accepted` | Core 개선 대상으로 채택 (승격됨) |
| `rejected` | 개선 불필요로 판정 (사유 기록) |
| `applied` | Strata Core 반영 완료, 템플릿/어댑터 재생성됨 |

---

### Promotion Gate

backlog 항목은 `scope`로 처리 경로가 갈린다.

- `scope: project` — 그 프로젝트의 규칙·layer-map·AGENTS.md·KB·결정 개선 후보로 처리한다.
- `scope: methodology` — core backlog(`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`)로 승격한다.

Builder는 `scope: methodology` 항목에 대해 다음을 한다.

1. 중복 여부를 확인한다.
2. `affected_core`가 1개 이상인지 확인한다.
3. core backlog에 승격 항목을 추가한다.
4. 원 프로젝트 항목에 `promoted_to`를 기록한다.
5. kit에 반영되기 전까지 status는 `triaged` 또는 `accepted`로 둔다. 반영되면 `applied`와 `applied_in`(커밋·DEC)을 적는다.

판정(`accepted`·`rejected`)은 사람이 한다. 이전의 strata 중앙 backlog(`strata/methodology-backlog.yaml`)는 kit backlog로 옮겨졌다(DEC-2026-10-29-12).

## 자기완결성 체크리스트

Builder가 태스크 명세 작성 후, Worker에게 전달하기 전 검증:

```
□ scope.layer가 단일 레이어인가?
□ scope.can_reference가 layer-rules.yaml과 일치하는가?
□ scope.constraints가 해당 도메인/레이어의 적용 가능한 제약을 포함하는가?
□ scope.nodes가 있고, scope.docs_to_update가 커버리지 리졸버 결과와 일치하는가?
  (소유 명세가 없으면 명세 생성이 deliverables에 있거나 의도적 비움 사유가 있는가?)
□ inputs.reference_files에 Worker가 필요한 모든 파일이 명시되어 있는가?
□ inputs.requirements가 구두 설명 없이도 이해 가능한가?
□ inputs.conventions에 해당 레이어의 컨벤션이 요약되어 있는가?
□ deliverables.files에 생성/수정할 모든 파일이 나열되어 있는가?
□ acceptance_criteria가 검증 가능한 형태인가? (테스트 통과, 위반 0건 등)
□ acceptance_criteria에 constraint 준수 검증이 포함되어 있는가?
□ acceptance_criteria에 docs_to_update 처리(명세 갱신 또는 doc_change: none + 사유)가 포함되어 있는가?
□ context_budget.max_reference_files ≤ 5인가?
```

**하나라도 미충족 시 Worker에게 전달하지 않음.**

Worker가 태스크 수령 시 검증:

```
□ scope.layer가 명시되어 있는가?
□ scope.docs_to_update가 비어 있으면 의도적 비움 사유가 명시되어 있는가?
□ inputs.reference_files의 파일이 실제 존재하는가?
□ inputs.requirements가 비어있지 않은가?
□ deliverables.files가 비어있지 않은가?
□ acceptance_criteria가 1개 이상인가?
```

**미충족 항목 발견 시 즉시 Builder에게 반려 (scope_issue 보고).**

---

## 태스크 정리 정책

| 시점 | 행동 |
|------|------|
| 태스크 완료 | `status: completed` + completion 섹션 채움 |
| 작업지시 전체 완료 | `_order.yaml`의 `status: completed` |
| 스프린트 종료 | 완료된 날짜 폴더는 보관 (삭제하지 않음) |
| 90일 경과 | 완료된 작업지시 폴더 아카이브 가능 |

완료된 태스크의 핵심 결정사항은 핸드오프와 KB에 이미 환류되어 있으므로,
태스크 파일 자체는 **감사 추적(audit trail)** 용도로만 보관합니다.
