# Agent Operations (에이전트 운영 축)

> 정본: strata-kit `core/docs/ko/methodology/agent-operations.md` (2026-10-29 strata `docs/04-agents/agent-operations.md` 에서 이관, DEC-2026-10-29-11).

> Strata의 **세 번째 직교 축**. Execution Mode(어떻게 작업하나) → Verification Tier(누가 검증하나) → **Agent Operations(언제·얼마·어떻게 소화하나)**.
> Verification Tier 정의는 `core/docs/ko/methodology/verification-tier.md`가 source of truth다.
> 다루는 것: 운영 시간대(야간 배치), 예산(budget envelope), 멀티세션 구조, 그리고 폭증하는 산출물을 사람이 소화하는 방식(Decision Inbox + 자기신고 검증 게이트).
> 상태: `draft` (설계 합의 완료. §1 packet·§5 ledger CLI(`kb ledger`) 구현. §2–4의 산출물 검증·Decision Inbox gate 는 자동화된 도구가 없다 — 예전 strata 의 agent-ops.py 는 2026-06 이후 쓰이지 않는다(DEC-2026-10-29-12). 실제 agent runner는 미구현)

## 0. 왜 필요한가

Execution Mode와 Verification Tier는 "한 작업을 어떻게 잘 하나"를 다룬다.
Agent Operations는 그 위 문제 — **에이전트를 여럿·오래 돌릴 때 사람이 병목·익사하지 않게 하는 운영 규율**을 다룬다.

핵심 전제 (이 축 전체를 관통):

> 에이전트를 많이 돌리는 것이 목적이 아니다. **전달 단위·역할·산출물·사람이 보는 표면적을 강하게 제한**하는 것이 목적이다.
> 산출량을 늘리는 모든 장치(멀티세션·야간배치)는 산출을 소화하는 장치(Decision Inbox·검증 게이트) 없이는 사람을 익사시킨다.

원칙 압축:

1. 릴레이는 전체 대화가 아니라 **구조화 packet**을 보낸다.
2. 멀티세션은 N:N 대화가 아니라 **Coordinator 중심(hub-and-spoke)** 으로 운영한다.
3. 야간 작업은 자율이 아니라 **budgeted batch**로 제한한다.
4. 사람은 raw output이 아니라 **Decision Inbox**만 본다.
5. 사람이 보는 라벨은 자기신고가 아니라 **교차검증으로 재판정된 것**이다.

이 문서는 runtime 계열의 방법론 primitive인 **Relay Packet, Decision Inbox, review_gate, Shared Session Ledger**의 source of truth다.
Quilt 허브 같은 adapter/runtime은 이 primitive를 재정의하지 않고 routing, projection, execution surface로 소비한다.

---

## 1. Relay Packet 계층 (토큰 절감 + 오류 최소화)

전체 대화 전송은 금지. 토큰량을 줄이는 것이 아니라 **토큰당 정보 밀도를 높이는** 것이 목표다.
(교차 검토 절차: `skills/strata.review/SKILL.md`, 전달은 Quilt 허브 `hub_send`)

```text
Level 0: 질문만
Level 1: 질문 + 현재 결론 + 쟁점            ← 기본값
Level 2: Level 1 + 근거 파일/라인 + diff 요약  ← 기본값
Level 3: 필요한 발췌 전문
Level 4: 전체 transcript (예외적으로만)
```

기본은 Level 1~2. 산문 대화를 그대로 던지면 상대가 무엇을 판단할지 흐려진다.
권장 packet 형태:

```yaml
intent: "review"
decision_so_far: "Verification Tier의 정본은 verification-tier.md로 분리됐다"
open_questions:
  - "Promotion Gate 흐름과 backlog 스키마 경계가 맞는가?"
evidence:
  - file: "core/docs/ko/methodology/verification-tier.md"
  - file: "core/docs/ko/methodology/task-spec-schema.md"
constraints:
  - "Core 문서에는 도구 이름을 넣지 않는다"
request:
  - "빈틈 1~2개만 지적"
```

- **앵커 동봉**: 여러 왕복 시 상대가 합의를 잊고 표류하지 않도록, 매번 `decision_so_far`(고정 요약)를 동봉한다.
- **빈약 packet 차단**: `evidence`/`request`가 비면 전송 전 경고한다 — 빈 packet이 전송되면 검증이 수행되지 않았는데 Cross-Verified처럼 보이는 위험이 있다. (실제 사례: 빈 packet을 받은 Reviewer가 "검토 불가"를 정확히 반환)

## 2. 멀티세션 (Model-A n · Model-B n)

가능하나 N:N으로 서로 대화하게 하면 토큰 폭발·중복 검토·책임 불명확으로 간다.
기본은 **hub-and-spoke**.

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

세션끼리 직접 말하게 하지 않는다. 모두 relay queue에 산출물을 내고 **Coordinator가 취합**한다.

금지 구조:
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (팬아웃은 쉽고 팬인이 어렵다)
```

역할 분리:

| 역할 | 책임 | 권한 경계 |
|------|------|----------|
| Primary | 작업 주도 | — |
| Reviewer | 결함 찾기 | 판정 아님, 지적만 |
| Contrarian | 반대 논리 찾기 | adversarial verify와 연결 |
| Summarizer | 산출물 압축 | 내용 변경 금지 |
| Archivist | decision/backlog 정리 | **`open→triaged`까지만. `accepted/rejected`는 사람** |

> **핵심**: 팬아웃(멀티세션)은 쉽고 팬인(종합)이 어렵다. 수렴 지점(Coordinator 또는 사람)이 없으면 §4 문제를 스스로 악화시킨다.

작업 트리(git worktree) 규칙 (DEC-2026-09-17-01): 병렬 Worker·병렬 세션이라도 작업 트리는 **사용자가 그 제안을 수락한 경우에만** 만든다. 자동 모드도 같다. 기본은 사용자가 보는 체크아웃의 단일 브랜치에서 순차 실행이며, 작업 트리가 정말 필요하면 필요성·브랜치 이름·정리 계획을 한 항목으로 제안하고 답을 기다린다. 끝나면 브랜치를 남기고 작업 트리를 정리해 보고한다. 정본 규칙은 `core/docs/ko/methodology/execution-modes.md` § 절대 규칙 7.

### 2.1 실행 산출물 스키마

멀티세션 자체를 실행하는 runner는 아직 없다. Coordinator가 받을 plan 산출물은 아래 스키마를 따르고, 검토 때 **N:N 링크 금지**, 역할 enum, Archivist 권한 경계를 확인한다(자동 검사 도구는 지금 없다).

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label, Core enum 아님
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist는 ["open->triaged"]만 허용
```

금지:
- `direct_peer_links`: 세션끼리 직접 대화하는 링크. 발견하면 반려한다.
- Archivist가 `accepted/rejected/applied`까지 판정하는 전환.

## 3. 야간 배치 프로토콜 (22:00–08:00)

자율 작업이 아니라 **budgeted batch**. "결정은 사람" 원칙을 깨지 않기 위해 **야간=생성, 주간=판정**으로 분리한다.

### 22시 전 — 사람이 준비
```text
1. 오늘 밤 처리할 work packet 3~5개 선정
2. 각 packet에 범위/금지사항/예산/완료조건 명시
3. 쓰기 허용 범위 제한 (write_scope)
4. 중단 조건 정의
```

### 야간 에이전트 규칙
```text
- 새 아키텍처 결정 금지
- 프로덕션 영향 작업 금지
- 커밋/배포/삭제 금지 (또는 별도 승인)
- 모호하면 중단하고 질문으로 남김
- 각 agent는 최종 1페이지 요약만 제출
- 산출물은 전부 needs_decision 대기 (cross_verified 전까지 채택 금지)
```

### budget envelope + 하드 리밋
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **안전장치 우선순위**: 하드 리밋(`max_turns`/`max_files`/`write_scope`)이 **1차**. 자기판단 중단(`stop_if: 모호하면`)은 **2차** — 에이전트가 모호함을 인식 못하면 안 멈추기 때문이다. 1차가 항상 작동해야 한다.

### 08시 — 사람이 보는 것
```text
- 결정 필요 항목 / 실제 변경 파일 / 테스트 결과 / 리스크 / 버릴 산출물 / 다음 지시 후보
```

토큰/시간은 정확한 숫자보다 **세션별 budget envelope + 시간당 페이싱**으로 관리한다 (한도를 새벽에 소진해 공백이 생기지 않게).

### 3.1 배치 산출물 스키마

야간 배치는 runner가 아니라 **batch spec**으로 먼저 고정한다. 시작 전에 packet 존재와
hard budget 필드를 확인한다(자동 검사 도구는 지금 없다). 실행 도구가 무엇이든 이 spec 없이는 야간 배치를 시작하지 않는다.

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

모든 야간 산출물은 §4 gate에서 `review_gate.required: true`로 취급한다.

## 4. Decision Inbox + 자기신고 검증 게이트 (이 축의 핵심)

사람의 병목은 "읽기"가 아니라 "**판정**"이다. 에이전트 출력을 정보가 아니라 **판정 가능한 단위**로 가공한다.
사람이 보는 표면은 **Decision Inbox 하나**. raw output은 저장만 한다.

### 4.1 출력 강제 형식 (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "무엇을 했는가"
  changed_files: []
  evidence: []          # pointer 필수 (decision 없는 장문 설명 금지)
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # raw output은 여기에 저장만
```

### 4.2 자기신고 검증 게이트 (Self-Report Validation Gate)

**문제**: 위 `status`/`risks`는 에이전트가 **스스로** 분류한다. 자기 위험을 과소평가하면(high→low) 사람이 Inbox만 보는 순간 잘못 분류된 항목이 묻혀 통과한다.
**실측 근거**: 자기신고는 못 믿는다 — 모델은 근거 없는 자기주장을 사실로 등재하지 않고, 근거+코드를 주면 검증 후 수용한다.

**해법**: Decision Inbox 진입 **전에**, 릴레이(교차검증)가 **triage 라벨만** 재판정한다.

```text
검증 대상:
  Raw output 전체 재검토 ❌          (이러면 §1 토큰절감이 무너짐)
  status / risk / decisions_needed / evidence pointer 재판정 ✅
```

흐름:
```text
Agent self-report
  → Relay reclassifies (라벨만)
  → agree    → Decision Inbox 진입
  → disagree → "needs_human_decision" 으로 승격 (사람에게)
```

무한 루프 방지:
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # Reviewer가 Reviewer를 다시 부르기 금지
  disagreement_policy: human_decision   # 불일치 = 바로 Inbox로 승격
```

### 4.3 위험 기반 분기 (전부 재판정하지 않는다)

전부 재판정은 비싸다. 위험 기반으로 나눈다.

**필수 재판정:**
```text
- status: completed 인데 파일 변경 있음
- risk: high 또는 unknown
- decisions_needed 존재
- architecture / schema / migration / deletion / security 관련
- 야간 배치 산출물 (전부)
- methodology_backlog / decisions 변경
```

**샘플링(또는 생략):**
```text
- low risk / 문서 요약 / 탐색 결과 / 테스트만 실행한 작업
```

### 4.4 재판정자 부재 폴백 (안전 기본값)

`reviewer: cross_verified`는 다른 모델 계열 재판정자를 전제한다.
**재판정자가 없으면**(예: 야간에 cross 세션 미가동) 검증을 못 한 것이므로,
해당 항목은 자동으로 **`needs_human_decision`** 으로 분류한다 — 검증 못 했으니 통과시키지 않고 사람에게 올린다.

### 4.5 사람이 매일 하는 것 (Agent Output Triage)
```text
1. 승인할 것  2. 반려할 것  3. 추가 질문할 것  4. 버릴 것
```
규칙: raw output은 저장만, 사람은 digest만, digest엔 evidence pointer 필수, decision 없는 장문 금지.

### 4.6 스키마 예시 (task completion 확장)
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "low로 분류됐지만 schema 변경 포함"
    max_review_rounds: 1
```

### 4.7 게이트 판정 규칙

자동 검증 도구는 지금 없다(예전 strata 의 agent-ops.py 는 2026-06 이후 쓰이지 않는다, DEC-2026-10-29-12). 아래 판정 규칙은 리뷰와 Decision Inbox 를 꾸릴 때 사람·Builder 가 적용한다.

Gate 판정:
- `completed` + changed files, `risk: high|unknown`, `decisions_needed`, architecture/schema/migration/security/decision 신호, 야간 배치 산출물은 `review_gate.required: true`.
- reviewer가 없으면 `result: no_reviewer`, `final_status: needs_decision`.
- `max_review_rounds`는 항상 1.
- `changed_files`가 있으면 `evidence` pointer가 필수다.

Decision Inbox item은 `approve | reject | question | discard` 중 하나의 action으로만 노출한다. raw output은
`discardable_notes_ref`에 저장하고 Inbox에는 pointer만 둔다.

---

## 5. Shared Session Ledger (공유 세션 원장)

> 세 작업자(**user / primary / reviewer**)가 하나의 요청 흐름을 공유하며 협업하기 위한 **단일 진실원(source of truth)**.
> 도구별 어댑터는 `primary`/`reviewer` 역할을 실제 도구 세션에 매핑한다. Core 스키마는 도구명을 enum으로 갖지 않는다.
> reviewer 세션의 기억이 아니라 이 파일이 맥락을 보유한다 — Strata 제1원칙("세션은 소모품, 문서가 영속")을 릴레이에 적용한 것.

### 5.1 왜 ledger인가 (reviewer 세션 관리의 상위 해법)

릴레이를 오래 굴리면 "reviewer 세션을 어떻게 유지하나"가 문제가 된다. 그런데 **진실의 단위를 reviewer 세션이 아니라 공유 ledger로 두면** 이 문제가 해소된다:

- reviewer 세션은 **휘발성이어도 된다** — 맥락은 reviewer의 기억이 아니라 ledger에 남는다.
- 다음 relay packet의 `decision_so_far` / `evidence` / `open_questions`는 reviewer 기억이 아니라 **ledger에서 생성**한다 (§1 packet).
- 사용자는 어느 도구로 시작하든, 같은 ledger를 읽고 이어간다 (도구·시작점 무관).

> **단, reviewer 리셋 규칙(§1 주변)은 폐기하지 않는다.** ledger는 *맥락 유지* 문제를 풀지만,
> reviewer가 packet에 없는 **오래된 합의를 자기 판단에 섞는 오염**은 별개다. 리셋은 "맥락 유지용"이 아니라
> **"오염 방지 hygiene"** 으로 격하해 유지한다 (목적이 다르므로 ledger가 생겨도 사라지지 않는다).

### 5.2 위치 · 포맷

```text
위치: $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
      (Core 밖, 영속·공유·색인 적합. .strata/local은 머신로컬 상태라 부적합)
포맷: Markdown 파일 + actor별 YAML block entry (사람 읽기 + 기계 색인 양립)
frontmatter 필수: session_id · project · status · actors · topic · created · next_session · nodes
      (nodes = 이 세션이 속한 주제 노드 — §5.7 커버리지 게이트가 변경 파일에서 유도·대조)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (예: claude | codex — Core enum 아님)
```

### 5.3 엔트리 스키마

각 엔트리는 `## [actor] {ISO8601 timestamp}` 헤더 + YAML 블록. append-only, 시간순.

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "Claude/Codex/User가 같은 요청 흐름을 공유하게 하자"
decision: null            # 사용자 결정/중단 판단 (있으면)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "shared ledger 제안"     # 무슨 문제를 받았나
action: "상위 프레임으로 분석"        # 어떻게 처리했나
to_reviewer:                        # reviewer에 보낸 packet 요약 (없으면 null)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "수용 | 반박 | 보류"         # reviewer 응답에 대한 처리 (있으면)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # 무엇을 검토했나
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "되돌려준 핵심 의견"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "재시작 신호 — 경고선 초과 | 같은 가설 두 번 실패"
confirmed: ["확인된 사실 (무엇으로 확인했는지)"]
assumed: ["확인하지 못한 추정"]
discarded: ["버린 가설 (버린 이유)"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # close 시 강제 (null 금지 — 체인 끊김 방지)
reason: "다음 흐름으로 넘기는 이유"
​```
```

위 예시의 `[primary] 2026-06-01T15:10` 엔트리는 재시작 엔트리다. 재시작 신호(session-splitting 5.1)로 일을 새 세션에 넘길 때, 핸드오프의 사실과 가설 절과 같은 세 칸(confirmed·assumed·discarded)을 적는다.

### 5.4 단일 writer + 파일 락 (B3 — 동시쓰기 오염 방지)

방금 실측한 세션 파일 오염(두 프로세스가 한 파일 동시 append)을 ledger에서 반복하지 않으려면:

- 도구별 에이전트 프로세스는 **ledger 파일을 직접 쓰지 않는다.** 단일 진입 CLI(`python3 "$STRATA_KIT/kb" ledger`)만 쓴다.
- **단일 CLI ≠ 단일 동시성**: CLI 내부에 **파일 락(flock)** 이 있어야 한다. 여러 어댑터가 거의 동시에 `append`를 호출해도 직렬화된다.
- ledger는 살아있는 TUI 세션 파일(`~/.claude/...`, `~/.codex/...`)과 **별개 파일**이다 — TUI 점유와 무관하므로 lsof 가드 대상이 아니다.

### 5.5 append 트리거 (B1 — 누가 언제 남기나)

엔트리는 자동이 아니라 **명시 트리거**에 남긴다:

```text
- 릴레이 전후: packet 전송 시 primary entry(to_reviewer), 응답 회수 시 reviewer entry(verdict)
- 사용자 결정: user가 채택/반려/중단을 판단할 때 user entry(decision)
- 작업 종료: close 시 next_session 포인터 작성 (§5.6)
```

### 5.6 세션 체이닝 (B2 — next_session 강제)

ledger를 닫을 때 `next_session.next`를 **반드시** 채운다. `null`로 닫지 않는다 —
끊기면 다음 작업자가 흐름을 못 잇는다 (핸드오프의 "pending엔 blocker 필수"와 동일 패턴).
이어갈 작업이 없으면 `next: "none"` + `reason`을 명시해 *의도적 종료*임을 남긴다.

### 5.7 커버리지 게이트 (세션 종료 시 — 코드는 바뀌었는데 형상은 안 바뀌었는가)

세션이 닫힐 때 세션 종료 게이트(handoff generator·ledger CLI의 validate/close)가 미커밋 decision 레코드 경고와 **같은 자리에서** 다음을 검사한다:

```text
입력: 이 세션이 변경한 코드 파일 목록 (태스크 completion.files_modified/created, 없으면 저장소 diff)
① 변경 파일마다 그 표면을 covers 로 소유한 명세를 찾는다 (커버리지 리졸버)
② 소유 명세의 nodes 를 모아 ledger·핸드오프 frontmatter 의 nodes 와 대조한다 — 누락이면 채우라고 경고
③ 소유 명세 중 이 세션에서 갱신되지 않은 것(updated 가 세션 시작 이전)이 있고,
   frontmatter 에 doc_change: none + doc_change_reason 이 없으면 → 경고 + 해당 노드의 부채로 기록
④ 소유 명세가 없는 변경 파일이 있으면 → "미소유 표면" 경고 (명세 생성 또는 covers 확장 필요)
```

- **경고이지 차단이 아니다.** 미커밋 레코드 경고와 같은 등급이다. 그러나 무시하면 노드 페이지의 "부채" 면에 남아 다음 사람이 본다.
- `doc_change: none`은 §5.6의 `next: "none"`과 같은 원칙이다 — 빈 값 금지, 명시적 none + 사유.
- 부채의 정본은 페이지가 아니라 "세션에 doc_change 선언이 없다"는 사실 자체다. 부채를 갚는 방법은 둘뿐이다: 명세를 갱신하거나(updated·sources 갱신), 그 세션 문서에 doc_change 사유를 소급 기재한다.
- 값 형식: `core/docs/ko/knowledge-base/document-format.md` "노드·커버리지 필드" 절. 리뷰 정책(90일)과는 별개의 신호다.

ledger frontmatter 필수 필드에 `nodes`가 포함된다 (§5.2). 값은 ②에서 리졸버가 유도하며, 코드 변경이 없는 세션만 사람이 직접 고른다.

---

## 6. 다른 축과의 관계

```text
②멀티세션(팬아웃) ┐
③야간배치(생성)   ├→ ④Decision Inbox + 검증게이트(팬인) ← 없으면 ①②③이 사람을 익사시킴
①릴레이(밀도↑)   ┘
⑤ledger ← ①~④의 모든 행위가 남는 공유 진실원 (도구·시작점 무관)
```

- **Execution Mode**: Agent Operations를 참조만. (모드 판정/전환은 `core/docs/ko/methodology/execution-modes.md`)
- **Verification Tier**: 검증 게이트의 `reviewer: cross_verified`가 `core/docs/ko/methodology/verification-tier.md`의 Cross-Verified Tier를 그대로 사용.
- **Methodology Feedback Loop**: Archivist의 `open→triaged` 경계는 `core/docs/ko/methodology/task-spec-schema.md` 의 Promotion Gate와 backlog lifecycle을 따른다. 판정(accepted)은 사람.
- **교차 검토**: §1 packet 은 `skills/strata.review/SKILL.md` 가 만들어 새 컨텍스트의 리뷰어에게 보낸다(Quilt `hub_send`). 예전 Claude↔Codex 릴레이 도구(strata bridge)는 과거 구현이고 쓰지 않는다.

## 7. 도입 우선순위

```text
①릴레이 packet 구조화  → 즉시 가능 (이득 명확, 위험 낮음)
④Decision Inbox + 게이트 → 마스터 키 (②③의 안전장치, 먼저 설계)
⑤Shared Session Ledger  → 릴레이를 여러 왕복 굴리기 전 (단일 writer+락이 전제)
②멀티세션 / ③야간배치  → ④⑤ 설계 후 (먼저 하면 사람이 병목/익사)
```

부품은 이미 있다: 교차 검토(strata.review, 교차검증 필터) + backlog lifecycle(판정 큐) + Verification Tier(신뢰도 게이트). fan-in guardrail(산출물 자동 검증)은 아직 없다 — 예전 agent-ops.py 는 쓰이지 않는다. 발명이 아니라 **조립**이다.

## 8. 미결 사항

- `review_gate` 재판정의 실제 토큰 비용 측정 (얇은 게이트 가정의 검증).
- Coordinator를 에이전트로 둘지 사람이 겸할지 (멀티세션 규모에 따라).
- 멀티세션 runner와 야간 batch runner는 미구현. 현재 구현은 plan/batch/self-report/Inbox 산출물 검증과 gate 정규화까지다.
- `discardable_notes_ref`(raw output) 보관 위치 — vault relays/ 재사용 가능성.
- `kb ledger`(구 session-ledger.py) 구현 완료 (append/read/close/validate + flock). 잔여 정련은 교차검증 큐 참조.
- §5.7 커버리지 게이트 구현됨 — handoff generator(생성 전 검사 + 유도 노드 prefill)와 ledger CLI validate/close(경고)에 배선, close·handoff 뒤 노드 페이지 재생성. ledger 필수 필드 `nodes`는 도입기라 **경고 등급**(오류 승격은 소급 뒤). 기존 문서 소급(nodes/covers)·프로젝트별 toc.yaml 은 미착수 (methodology-backlog MB-strata-2026-007).
- reviewer 리셋 트리거(topic_change / max_rounds 3~5 / decision_accepted / packet_drift / high_risk)를 ledger entry와 어떻게 연동할지.
