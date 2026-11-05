# Knowledge Base — 문서 포맷

> 정본: strata-kit `core/docs/ko/knowledge-base/document-format.md` (2026-10-29 strata `docs/07-knowledge-base/document-format.md` 에서 이관, DEC-2026-10-29-11).

## 개요

vault 내 모든 `.md` 파일은 YAML frontmatter를 포함해야 합니다.
Obsidian과 MCP 서버(Phase 3) 모두에서 파싱 가능한 형식을 사용합니다.

## Frontmatter 스키마

```yaml
---
# === 필수 필드 ===
title: "문서 제목"
id: "{접두}-{project}-{slug}"  # 안정 ID — 이동·개명 불변 (접두 체계: core/docs/ko/knowledge-base/vault-structure.md 안정 ID 절)
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === 조건부 필수 ===
project: {project-name}       # 특정 프로젝트 문서일 때 (횡단 문서는 id의 project 자리에 vault)
status: draft | active | review-needed | superseded | archived
sources: ["[[출처 세션/태스크]]"]  # Knowledge 계층 문서(KB·pattern) 갱신 시 필수 — 근거 Archive 링크 (DEC-2026-08-19-03)
nodes: ["{node-id}"]          # 주제 노드 소속 — decision·session·specification·concept·constraint 필수 ("노드·커버리지 필드" 절)

# === 선택 필드 ===
tags: [namespace/value, ...]  # 네임스페이스 태그 권장
updated: YYYY-MM-DD           # 마지막 수정일
updated_by: {git user}@{machine}  # 마지막 갱신자 — 쓰기 훅이 git identity 와 머신 alias 로 스탬프 (DEC-2026-09-09-05)
page_order: 1                 # 카테고리 내 문서 순서 (KB 색인용)
author: builder | worker | manual  # 작성 주체
machine: {alias}              # 작성 머신 — 이 기계의 별칭(STRATA_ENV, env-config.yaml). 다른 기계를 적은 세션 기록은 vault-git 이 거부
superseded_by: "[[새 문서]]"   # status: superseded 일 때 (대체된 쪽 → 대체한 쪽)
supersedes: ["[[이전 결정]]"]   # decision — 이 결정이 대체하는 이전 결정 (superseded_by의 반대 방향)
covers: {paths, symbols, endpoints, tables}  # specification·concept — 이 문서가 정본인 코드 표면
doc_change: none              # session·task — 코드는 바꿨으나 형상을 갱신하지 않음을 선언 (doc_change_reason 필수)
aliases: ["옛 파일명"]         # 이동·개명 시 원 식별자 보존
related: ["[[관련문서1]]"]     # Obsidian wikilink — 언급 관계 (소유 관계는 covers)
---
```

## type별 필수 필드

| type | 추가 필수 필드 | 설명 |
|---|---|---|
| `overview` | `project` | 프로젝트 또는 카테고리 개요 |
| `decision` | `project`, `status`, `nodes` | ADR. 결정의 맥락과 근거 포함. 선택 `supersedes` |
| `session` | `project`, `machine`, `nodes` | 세션 핸드오프·ledger. **메타+요약부만 색인** (Archive — 2026.08.19-06). 선택 `doc_change` |
| `pattern` | — | 프로젝트 횡단 재사용 패턴 |
| `reference` | — | 외부 문서, 표준, 규격 요약 참조 |
| `glossary` | — | 도메인 또는 기술 용어 정의 |
| `concept` | `nodes` | 도메인 개념, 비즈니스 규칙, 원리 설명. 선택 `covers` |
| `specification` | `status`, `nodes` | 기능 명세, 요구사항, 제약조건, 인수 기준. 노드의 최종형상. 권장 `covers` |
| `flow` | — | 비즈니스 프로세스, 데이터 흐름, 시퀀스 |
| `guide` | — | 절차적 안내, How-to 문서 |
| `runbook` | `status` | 운영/장애 대응 절차서 |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | ADR에서 추출된 단일 실행 가능 제약 |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | PRD 기능 단위. constraint 링크 필수 |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | 외부 기획 도구에서 들여온 기획 원문(PRD·정책·Epic/Story). 원문 불변 + `## 구현 검토` 절. `implementation.status`가 검토 결과 분류. status 는 기획 상태(lifecycle_override) |
| `moc` | — | 목차(Map of Content). `_index/`와 각 `_index.md`, 생성형 정적 인덱스. **생성 전용** |
| `node` | `project`, `node` | 주제 노드 페이지. 최종형상·정책·결정·기획·작업이력·부채를 조인. **생성 전용** |

`moc`와 `node`는 Index 계층이다. 손으로 쓰지 않고 정본(frontmatter·레코드·toc.yaml)에서 재생성한다.

## 노드·커버리지 필드

주제 노드(node)는 사람이 읽는 목차의 단위다. 하나의 노드가 최종형상(명세), 정책(제약), 결정, 작업이력을 한 화면에 모으는 열쇠가 된다. 노드 트리의 정본은 프로젝트 `_meta/toc.yaml`이고, 문서는 아래 네 필드로 노드와 코드에 자신을 연결한다. **이 절이 값 형식의 정본이다.** taxonomy는 필수 여부만 정한다.

### `nodes` — 이 문서가 속한 주제 노드

```yaml
nodes: ["orders.checkout-v2.coupon"]   # toc.yaml에 정의된 노드 id, 복수 허용
```

- 노드 id는 문서 id(`{접두}-{project}-{slug}`)와 **다른 네임스페이스**다. 조상부터 점(.)으로 이은 경로이며 각 조각은 kebab-case다.
- decision·session·specification·concept·constraint에 필수. 태스크 명세도 같은 필드를 쓴다(`core/docs/ko/methodology/task-spec-schema.md` 참조).
- 세션과 태스크의 노드는 커버리지 리졸버(변경 파일 → 그 파일을 소유한 명세 → 그 명세의 노드)가 유도한다. 사람이 고르는 경우는 코드 변경이 없는 세션뿐이다.
- 빈 배열은 허용하되 검증이 경고한다. 노드 없음이 의도라면 본문에 사유를 남긴다.

### `covers` — 이 문서가 정본인 코드 표면

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # 저장소 상대경로, 부분 문자열 매칭
  symbols: ["RefundCalculationService"]                              # 클래스·함수 이름
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + 경로 접두
  tables: ["refund_items"]                                      # 테이블 이름
```

- specification·concept에서만 쓴다. 세션·결정·제약은 `covers`를 갖지 않는다. 그들은 `nodes`로 노드를 가리킬 뿐이다.
- 파일 단위 경로는 쓰지 않는다. 모듈·패키지·컨트롤러·라우트 접두처럼 이동에 안정적인 식별자만 쓴다. 매칭 규칙은 layer-map의 경로 매칭과 같다(부분 문자열, 위에서부터).
- 한 표면은 정확히 하나의 문서가 소유한다. 겹치면 검증이 경고한다. 상위 개념 문서는 `up`으로 연결한다.
- `covers`는 **소유** 관계이지 언급이 아니다. 언급은 `related`에 둔다. 이 구분이 흐려지면 한 파일을 다섯 문서가 소유하게 되고 커버리지 게이트가 소음이 되어 무시된다.
- 코드 경로 포인터는 vault에 소스 코드를 두지 않는다는 원칙과 충돌하지 않는다. 코드가 아니라 저장소 상대경로만 기록한다(`core/docs/ko/knowledge-base/vault-structure.md` "절대 포함하지 않는 것").

### `doc_change` — 코드는 바꿨으나 형상을 갱신하지 않을 때

```yaml
doc_change: none
doc_change_reason: "리팩터링만 수행 — 외부 계약·정책 변화 없음"
```

- session·task에서 쓴다. `covers` 경로가 변경됐는데 그 표면을 소유한 문서가 갱신되지 않았고 이 필드도 없으면, 세션 종료 게이트가 해당 노드의 **부채**로 기록하고 경고한다.
- 빈 값은 금지다. `none`이면 반드시 사유를 붙인다. ledger가 `next: "none"`에 reason을 요구하는 것과 같은 원칙이다.

### `supersedes` — 이 결정이 대체하는 이전 결정

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- decision에서 쓴다. **대체된 쪽의 상태는 저장하지 않고 유도한다** (DEC-2026-09-30-03): 어떤 레코드의 `supersedes` 에 등장한 결정은 인덱스와 DEC 노트에서 `status: superseded` 와 `superseded_by` 를 자동으로 갖는다. 대체된 쪽 레코드 파일은 고치지 않는다.
- 이미 기록된 결정에 대체 관계를 뒤늦게 추가할 때는 `python3 "$STRATA_KIT/kb" decision supersede --id 새 --target 옛`, 대체 결정 없이 거둘 때는 `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...` 을 쓴다. 본문에 "대체"·"철회" 라고만 적는 것은 상태로 인식되지 않는다.
- KB 문서(decision 외)는 여전히 대체된 쪽에 `status: superseded` 와 `superseded_by` 를 직접 적는다.
- `superseded_by`는 반대 방향(대체된 쪽 → 대체한 쪽)의 기존 필드다. 둘은 같은 사실의 양끝이다.
- 노드 페이지의 "결정" 면은 이 사슬의 끝을 현행 결정으로, 나머지를 이력으로 보여 준다.

## 문서 라이프사이클

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| 상태 | 의미 | 전이 가능 |
|------|------|-----------|
| `draft` | 작성 중, 검토 전 | active, archived |
| `active` | 유효한 현행 문서 | review-needed, superseded, archived |
| `review-needed` | 갱신 필요 (90일 경과 시 자동 플래깅) | active, superseded, archived |
| `superseded` | 새 문서로 대체. `superseded_by` 필드 필수. 대체한 결정이 `supersedes`를 선언하면 대칭 검증 대상 | archived |
| `archived` | 유효하지 않음. 검색 가중치 감소 | — |

**타입별 예외**: `constraint`는 전용 라이프사이클을 사용한다 —
`active → superseded → retired` (taxonomy.yaml `lifecycle_override`).
제약은 draft 상태 없이 ADR accepted 시점에 active로 생성되며, 폐기는 `retired`로 표기한다.

## 본문 규칙

### 일반 규칙

- 마크다운 형식 (CommonMark + Obsidian 확장)
- 제목은 `##`부터 시작 (`#`은 frontmatter title과 중복 방지)
- 한 문서는 하나의 주제에 집중 (MECE 원칙)
- 최대 길이: 개요/패턴/개념 500줄, ADR 200줄, 세션 요약 100줄, 명세 1000줄, 목차·노드 페이지 300줄
- 본문 섹션 제목의 정본은 taxonomy `document_types.{type}.body_sections`다. 아래 구조 블록은 그 렌더이며, 생성기는 taxonomy에서 제목을 만든다

### 가독성 규칙 (필수)

- **자기완결적 용어**: 문서는 그 문서만 읽어서 이해할 수 있어야 한다. 외부 기술 배경 없이는 뜻을 알 수 없는 용어 — 영어 전문용어, 구현체 내부 개념, 글쓴이가 임의로 만든 합성어 — 를 그대로 쓰지 않는다. 꼭 필요하면 **처음 나올 때 한 줄로 풀어 정의**한다. (예: "materialize", "resolve", "single-flight", "degraded" 같은 단어 대신 "처음 요청할 때 만들어 둔다", "조회해서 구성한다"처럼 **동작을 풀어** 쓴다.)
- **본문 ↔ 마무리 흐름 일치**: 문서 끝의 "미결/확인 필요/요청 답변" 항목은 본문에서 실제로 정의하고 전개한 내용에서만 끌어낸다. 본문에 없는 새 개념을 마무리 섹션에서 처음 꺼내지 않는다. 독자가 각 미결 항목이 본문의 어느 부분과 연결되는지 1:1로 찾을 수 있어야 한다.
- **판정 기준**: "이 문서를 처음 보는 같은 팀 동료가, 외부 검색 없이, 본문만 읽고 모든 용어와 미결 항목을 이해할 수 있는가?" 아니라면 풀어 쓰거나 본문에 근거를 추가한다.

### 사람이 읽는 문서 규칙 (필수 — DEC-2026-09-10-01)

독자는 사람이다. 에이전트가 파싱하기 좋은 형태로 쓰지 않는다. KB 문서·세션 핸드오프·결정 레코드·채팅 보고에 같이 적용한다.

- **인지 가능한 정리만 쓴다.** 한 번 읽어서 뜻을 알 수 없는 문단·표는 쓰지 않는다. 코드 심볼·경로·결정 ID 를 나열해 설명을 대신하지 않는다. 표는 한 칸에 한 사실만 담고, 표 안에 표를 넣지 않는다.
- **중복·장황을 금지하고 한 맥락으로 쓴다.** 같은 사실을 여러 절에 반복하지 않는다. 절이 바뀔 때 관점이 바뀌지 않게 한 흐름으로 이어 간다.
- **요약이 먼저, 근거는 뒤.** 서술이 길어지면 맨 앞에 결론 요약을 두고, 코드 위치·실측값·인용은 뒤의 근거 절에 붙인다. 요약만 읽어도 판단할 수 있어야 한다.
- **코드형 순서 라벨을 쓰지 않는다.** `A1·A2·B3` 처럼 문자와 숫자를 조합한 코드로 태스크·문서 순서·항목을 분류하지 않는다. 순서와 항목은 의미가 드러나는 짧은 문장으로 쓴다. ("A3 hub 프루닝" 이 아니라 "hub 에서 쓰지 않는 화면 삭제"). 이미 라벨이 붙은 기존 문서를 인용할 때만 원문 라벨을 괄호로 덧붙인다.

### Decision (ADR) 본문 구조

```markdown
## 맥락
{결정이 필요했던 배경}

## 결정
{선택한 방향과 이유}

## 대안
{검토했으나 선택하지 않은 방향과 이유}

## 결과
{이 결정으로 인한 영향, 트레이드오프}
```

`supersedes`를 선언한 결정은 `## 결과`에 무엇을 왜 대체하는지 한 줄을 남긴다. 노드 페이지가 결정 사슬을 보여 줄 때 그 줄이 설명이 된다.

### Session 요약 본문 구조

```markdown
## 완료
- {완료된 항목}

## 진행 중
- {미완료 항목과 현재 상태}

## 결정 사항
- {이 세션에서 내린 결정}

## 주의 사항
- {다음 세션에서 알아야 할 경고/이슈}
```

- 위 네 섹션은 핸드오프 **요약부**의 구조다. ledger의 actor 엔트리와 `next_session` 블록 형식은 `core/docs/ko/methodology/agent-operations.md` §5.3이 정본이며 이 구조와 공존한다.
- 코드를 바꿨는데 최종형상을 갱신하지 않았다면 frontmatter `doc_change: none`과 사유를 선언하고, `## 주의 사항`에 같은 사유를 적는다.

### Pattern 본문 구조

```markdown
## 문제
{이 패턴이 해결하는 문제}

## 해결
{패턴 설명}

## 적용 예시
{코드 스니펫 또는 구조 예시}

## 적용 프로젝트
- [[project-a]] — {어떻게 적용했는지}
```

### Constraint Card 본문 구조

ADR에서 추출된 단일 실행 가능 제약. 50줄 이내로 간결하게 작성.

```yaml
---
title: "{제약 제목 — 1줄 명사형}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{도메인}]     # 이 제약이 적용되는 비즈니스 도메인
  layers: [{레이어}]      # 이 제약이 적용되는 Strata 레이어
rule: "{1줄 실행 가능 규칙 — MUST/MUST NOT 문장}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # 고유 ID (ADR 번호-순번)
---
```

```markdown
## 근거
{ADR의 어느 섹션에서 도출되었는지, 왜 이 제약이 필요한지 1-3줄}

## 위반 시 영향
{이 제약이 깨지면 어떤 문제가 발생하는지 1-3줄}

## 검증 방법
{코드 리뷰, 테스트, 정적 분석 등 구체적 확인 방법}
```

**Constraint Card 작성 규칙:**
- ADR accepted 전환 시 같은 세션 내에 추출 (Builder 의무)
- 1 ADR → N개 Card (통상 3-10개)
- severity는 ADR 원문의 언어에서 결정: "반드시/필수/MUST" → must, "금지/NEVER" → must-not, "권장/SHOULD" → should
- scope는 이 제약이 적용되는 도메인과 레이어의 범위
- constraint-registry.yaml에 1줄 요약 동시 등록

### Epic 본문 구조

PRD 기능 단위. constraints 필드로 ADR 제약과 연결.

```yaml
---
title: "{기능 단위 제목}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ 필수 — 이 Epic이 준수해야 할 Constraint Card
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{도메인}]
layers: [{영향 레이어}]
personas: [{대상 페르소나}]  # 프로젝트에서 정의한 페르소나 ID
tags: [epic, domain/{domain}]
---
```

```markdown
## 목표
{이 Epic이 해결하는 사용자 문제 1-3줄}

## 인수 기준
- {검증 가능한 완료 조건}

## 제약 요약
{constraints 필드의 각 Constraint Card가 이 Epic에 어떻게 적용되는지 요약}
```

**Epic 작성 규칙:**
- constraints 필드는 필수. 빈 배열은 리뷰 신호 (의도적 비움 vs 누락 판별 필요)
- 태스크 분할 시 Builder가 Epic의 constraints를 각 태스크의 scope.constraints에 분배

### Planning 본문 구조

외부 기획 도구(Notion 등)에서 들여온 기획 원문. 대부분 요청이 끝났거나 결정이 반영된 문서이므로 "요청"이 아니라 **기획**으로 본다 (DEC-2026-09-09-01).
원문은 as-intended, Knowledge 명세는 as-built다. 둘을 한 문서에 섞지 않는다 — 원문 절은 고치지 않고, 문서 끝의 `## 구현 검토` 절만 갱신한다.

```yaml
---
title: "{원제목}"
id: plan-{project}-{원천 id}          # 재임포트에 불변
type: planning
project: {project-name}
status: realized                      # 기획 상태 — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # Inbox 승인 후 기록 (임포터는 후보만 낸다)
source: "notion:{32hex}"              # 원천 식별자 (필수)
source_name: notion-orders-intake        # planning/ 하위 디렉토리
source_path: "{원천 내보내기 상대경로}"  # 판본 추적
up: "[[plan-{project}-{상위 id}]]"    # Epic/Story 처럼 상위 문서가 있을 때
topic: "분류: … · 과업 그룹화: … · 스프린트: …"   # 원천 속성 한 줄 — 노드 백필 플래너의 검색 대상
owner: "{이름}"                       # 선택 — 기획 소유자. 기획 누락 판정을 이 사람에게 묻는다(없으면 사용자, DEC-2026-10-31-35)
implementation:                       # ★ 필수 — 구현 검토 결과의 분류
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # unreviewed 면 생략
  spec: "[[kb-…]]"                    # 증류된 최종형상 문서 (있으면)
created: YYYY-MM-DD
---
```

```markdown
# {원제목}
{원문 — 고치지 않는다}

## 구현 검토

| 항목 | 기획 | 구현 | 차이 | 근거 |
|---|---|---|---|---|
| {정책 항목} | {기획이 말한 것} | {코드가 하는 것} | {없음 · 다름 · 미구현} | {코드 경로·심볼·명세 링크} |
```

**Planning 작성 규칙:**
- `## 구현 검토`는 항목(정책 문장·체크박스·Story) 단위로 쓴다. 문서 한 줄 요약은 `implementation.status`가 담당한다 — diverged·partial 이면 표에 차이 행이 있어야 한다.
- 검토가 명세 갱신으로 이어지면 그 명세의 `sources:`에 이 문서를 넣고 `implementation.spec`으로 되가리킨다.
- `status`(기획 상태)와 `implementation.status`(구현 검토)는 다른 축이다. "배포완료"인 기획이 코드와 다를 수 있다 — 그것이 diverged 다.
- 노드 페이지의 "기획" 면은 이 타입만 조인하며 배지(미검토·구현됨·일부 구현·기획과 다름·미구현·대체됨)로 보여 준다. unreviewed 건수와 diverged·partial 문서는 부채로 잡힌다.
- 기획과 구현이 어긋나면 `## 구현 검토` 의 차이 줄로 끝내지 않고 판정 요청으로 남긴다(`python3 -m kb divergence add`, 게이트의 재대조 행은 `kb coverage-gate --divergence-inbox`). 판정은 사람만 하며 넷 중 하나다: 정합(차이 아님), 문서가 낡음(기획·명세를 구현에 맞춤), 기획 누락(`owner` 에게 보완 요청), 구현 결함(버그 태스크). 판정을 기록하면(`kb divergence judge`) `implementation.reviewed` 가 그날로 바뀌어 같은 변경으로 다시 재대조를 요구받지 않는다. `implementation.status` 는 판정에 따라 고친다(DEC-2026-10-31-35).

### 기획 묶음 (strata.planning)

바깥의 기획 원천을 정리할 때는 원문 한 장 대신 묶음을 쓴다(DEC-2026-11-01-04·05). `planning/<묶음>/` 에 `audit/` 폴더가 있으면 묶음이다. 묶음 밖의 기획 문서(위 형식)는 그대로 원문으로 다룬다.

| 자리 | 담는 것 | 주입·공유 |
|---|---|---|
| `source/` (또는 `category: source`) | 원천 원문, 고치지 않는다 | 안 됨 — 근거 |
| `audit/facts*.md` | 사실 목록 `# \| 원천 위치 \| 유형 \| 내용 \| 역할 \| 축 \| 하위 주제` | 안 됨 — 근거 |
| `audit/coverage*.md` | 대조표 `# \| 원천 위치 \| 행선지 \| 비고` — 행선지 일곱 가지 | 안 됨 — 근거 |
| `audit/defects*.md`, `audit/isolated*.md` | 결함(`# \| 종류 \| 내용 \| 처리`), 격리된 규칙 | 안 됨 — 근거 |
| 묶음 바로 아래 `*.md` | 정리본: `planning_doc: prd \| tech-spec \| terms \| tree` | 됨 |

- 정리본에는 코드·아키텍처(테이블·컬럼·스키마, 클래스·모듈·서비스명, API 경로·HTTP 코드, 프레임워크·라이브러리·벤더명)를 쓰지 않는다. 그런 사실은 대조표의 `코드` 행선지로 간다.
- 표는 열 순서로 읽으므로 머리글 언어는 자유다. 행선지 표기는 한국어(`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`)나 영어(`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`)이고, 그 밖의 값은 `<정리본> R<n>` 으로 읽는다.
- 지식 검색은 정리본만 찾는다. `python3 -m kb planning check <묶음>` 이 대조표와 정리본을, `python3 -m kb planning boundary [--list]` 가 주입 경계를 보인다.

## 태그 네임스페이스

모든 태그는 `namespace/value` 형식을 권장합니다. taxonomy.yaml에 정의된 네임스페이스:

| 네임스페이스 | 패턴 | 설명 | 값 제한 |
|-------------|------|------|---------|
| `project` | `project/{name}` | 프로젝트 스코프 | 자유 |
| `layer` | `layer/{name}` | Strata 아키텍처 레이어 | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | 비즈니스 도메인 | 자유 |
| `tech` | `tech/{technology}` | 기술 또는 프레임워크 | 자유 |
| `audience` | `audience/{role}` | 대상 독자 | developer, planner, devops, all |

예시: `tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

네임스페이스 없는 태그도 허용되나, 빌드 시 경고가 발생합니다.
상세 검증 규칙: `core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
