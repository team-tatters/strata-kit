# Knowledge Base — Vault 구조

> 정본: strata-kit `core/docs/ko/knowledge-base/vault-structure.md` (2026-10-29 strata `docs/07-knowledge-base/vault-structure.md` 에서 이관, DEC-2026-10-29-11).

## 개요

Vault는 모든 프로젝트가 공유하는 Obsidian 호환 지식베이스입니다.
독립 Git 저장소로 관리되며, 프로젝트 코드와 분리됩니다.

## 3계층 모델 (Archive / Knowledge / Index)

vault의 모든 콘텐츠는 세 계층 중 하나에 속하며, 계층마다 유지 규율이 다르다 (DEC-2026-08-19-04):

| 계층 | 디렉토리 | 규율 |
|---|---|---|
| **Archive** | `projects/*/sessions/`, `projects/*/tasks/`, `projects/*/relays/` | append-only. write-once가 **정상** — 개정·링크 의무 없음. KB가 아니라 증거 저장소 |
| **Planning** (Archive 변형) | `projects/*/planning/{source}/` | 외부 기획 도구(Notion 등)에서 들여온 기획 원문(`type: planning`). **원문 절은 불변**(Archive 규율), 문서 끝의 `## 구현 검토` 절만 갱신 — 정책 항목별 구현 여부·기획 대비 차이·근거를 표로 기록하고 frontmatter `implementation.status`로 분류. 실체 있는 정책은 Knowledge 명세로 증류하고 그 명세의 `sources:`가 원문을 가리킨다 (DEC-2026-09-09-01) |
| **Knowledge** | `projects/*/knowledge-base/`, `patterns/`, `_index/glossary.md` | **update-in-place 의무** — 갱신 시 `updated:` 필수, 근거 Archive 문서로의 출처 링크(`sources:` frontmatter) 필수 |
| **Index** | `_index/`, 각 `_index.md`, `projects/*/decisions/` DEC 노트, `projects/*/nodes/` 노드 페이지 | **생성 전용 — 손편집 금지.** 정본(레코드·frontmatter·toc.yaml)에서 재생성 (DEC projection generator, 노드 페이지 생성기 — 구현 매핑: `python3 -m kb --help` · `core/docs/ko/kb-engine.md`) |

지식 승격(Archive → Knowledge)은 증류 세션이 수행하고 Decision Inbox 게이트를 거친다.
신규 문서 생성보다 기존 Knowledge 문서 갱신을 우선한다 (리빙 도큐먼트 원칙).

### 문서 세 가지의 역할과 위치 (DEC-2026-09-30-03)

| 문서 | 무엇을 담는가 | 어디에 두는가 | 기본 검색 |
|---|---|---|---|
| 스펙 (결정) | 코드·구현 요구사항에 대해 구현 시점에 내린 결정과 이유, 대상 코드 심볼, 현행인지 대체됐는지 | decision 레코드 (Tier P) → DEC 노트 미러 | 색인 전 — 인덱스(`decisions.yaml`)·DEC 노트를 직접 읽는다 (색인 포함은 후속) |
| KB (Knowledge) | 서비스와 도메인을 사람이 이해할 수 있는 목차와 흐름으로 설명한 최종 형상 | `knowledge-base/`, 목차는 `_meta/toc.yaml` | 포함 |
| 작업 이력 (Archive·Planning) | 세션 기록, 태스크 명세, 날짜가 붙은 진단·보고, 외부 기획 원문 | `sessions/`, `tasks/`, `relays/`, `planning/` | 제외 (명시 요청 시만) |

- **목차 한 자리에 KB 문서 하나.** 같은 주제의 새 문서를 만들지 않고 기존 문서를 고쳐 쓴다. 불가피하게 새 문서로 대체하면 옛 문서는 `status: superseded` + `superseded_by` 로 닫는다.
- **날짜가 붙은 보고서·진단·스냅샷은 KB 가 아니다.** 파일명이나 제목에 날짜가 들어가는 문서(`*-2026-09-16.md` 등)는 그 날의 사실을 기록한 것이므로 작업 이력(`tasks/{date}/` 또는 `sessions/`)에 둔다. KB 에는 그 결과로 바뀐 최종 형상만 반영하고 `sources:` 로 보고서를 가리킨다.
- **기본 검색은 KB 만 본다.** 작업 이력은 검색 도구에 명시적으로 요청할 때만 포함한다 (`search_docs(include_history=true)` 또는 `category` 지정, CLI `--include-history`). 이력이 정본을 검색 결과에서 밀어내지 않게 하려는 것이다.

세 계층을 가로지르는 열쇠가 **주제 노드**다. 노드는 사람이 읽는 목차의 단위이며, 정본은 프로젝트 `_meta/toc.yaml`이다.
문서는 frontmatter `nodes:`로 소속을 선언하고, 노드 페이지는 그 노드를 가리키는 Knowledge(최종형상·정책), 결정, Archive(작업이력)를 **조인**해 생성한다.
노드 페이지는 승격이 아니다. 아무것도 새로 쓰지 않고 이미 있는 것을 한 화면에 모을 뿐이며, 구멍이 있으면 구멍이 보이게 둔다. 그 구멍이 누락의 가시화다.

## 디렉토리 구조

```
vault/
├── .obsidian/           Obsidian 앱 설정 (공유, git 추적)
│   └── plugins/         Custom Sort, Dataview 등 플러그인 설정
├── .kb/                 ★ KB 색인 관리
│   ├── manifest.json    파일별 SHA256 해시 (git 추적)
│   ├── schema.sql       DB 스키마 정의 (git 추적)
│   └── store.sqlite     KB store (strata-kit kb, .gitignore — legacy kb.sqlite 는 DEC-2026-10-28-13 으로 제거)
├── .local/              머신별 설정 (.gitignore)
│   └── resolved-paths.yaml
├── .gitignore
├── env-config.yaml      등록된 머신 alias 목록 (경로 없음)
│
├── _index/              MOC (Map of Content)
│   ├── projects.md      프로젝트 목록 + 링크
│   ├── decisions.md     크로스 프로젝트 ADR 인덱스
│   ├── patterns.md      패턴/레슨 인덱스
│   └── glossary.md      도메인 용어 사전
│
├── _meta/               ★ 글로벌 설정
│   └── taxonomy.yaml    분류 체계 정의 (카테고리, 타입, 태그)
│
├── projects/            프로젝트별 지식
│   └── {project-name}/
│       ├── overview.md          기술스택, 목적, 현재 상태
│       ├── _meta/               프로젝트 설정
│       │   ├── taxonomy.yaml    프로젝트 확장 taxonomy (글로벌 상속) — 디렉토리 축
│       │   └── toc.yaml         ★ 주제 노드 트리 (사람이 읽는 목차의 정본) — 주제 축
│       ├── knowledge-base/      ★ 프로젝트 KB (색인 대상)
│       │   ├── _index.md        MOC (Dataview 동적 목차)
│       │   ├── domain/          도메인 지식 (카테고리 1)
│       │   │   ├── _index.md    카테고리 MOC
│       │   │   ├── epics/       에픽별 도메인 지식
│       │   │   └── {topic}/     토픽 디렉토리 (프로젝트 taxonomy에서 정의)
│       │   │       ├── _index.md
│       │   │       └── *.md     KB 문서
│       │   ├── architecture/    기술 아키텍처 (카테고리 2)
│       │   │   ├── _index.md
│       │   │   ├── decisions/   ADR
│       │   │   ├── constraints/ Constraint Card
│       │   │   ├── api-contracts/
│       │   │   ├── data-models/
│       │   │   ├── infrastructure/
│       │   │   └── *.md
│       │   ├── guides/          가이드 (카테고리 3)
│       │   │   ├── _index.md
│       │   │   ├── onboarding/
│       │   │   ├── conventions/
│       │   │   ├── troubleshooting/
│       │   │   └── *.md
│       │   └── references/      레퍼런스 (카테고리 4)
│       │       ├── _index.md
│       │       └── *.md
│       ├── tasks/               ★ 태스크 명세 (Builder→Worker)
│       │   └── {yyyy.mm.dd}/    날짜별 그룹
│       │       └── {nn}-{title}/  Work Order 폴더
│       │           ├── _order.yaml    작업지시서
│       │           └── task-{nn}-*.yaml  Worker 실행 명세
│       ├── strata/              ★ detached profile의 Tier P 정본 (core/docs/ko/environment/data-placement.md §1.5)
│       │   ├── profile.yaml     placement profile manifest (새 PC bootstrap 앵커)
│       │   ├── decisions/       decision 레코드 (DEC-*.yaml, 1결정=1파일)
│       │   ├── decisions.yaml   생성형 인덱스 (손편집 금지)
│       │   ├── constraint-registry.yaml
│       │   └── layer-map.yaml
│       ├── decisions/           DEC 노트 — 생성 전용 (DEC projection generator, 손편집 금지)
│       │   └── DEC-YYYY-MM-DD-NN.md
│       ├── nodes/               노드 페이지 — 생성 전용 (노드 페이지 생성기, 손편집 금지)
│       │   └── {node-id}.md     예) orders.checkout-v2.coupon.md
│       ├── planning/            ★ 기획 문서 (type planning) — 기획 문서 임포터가 생성, 원문 불변 + 구현 검토 절
│       │   └── {source-name}/   원천별 (예: notion-orders-intake). 파일명 {원제목-slug}--{원천 id 앞 8자}.md — 원제목 언어 유지
│       └── sessions/            세션 핸드오프·ledger (Archive)
│           └── session-YYYY-MM-DD-{slug}.md
│
├── patterns/            프로젝트 횡단 패턴
│   └── {pattern-name}.md
│
├── strata-feedback/     방법론 피드백 기록
│   └── {topic}.md       적용/미적용 피드백
│
├── references/          외부 참조, API 요약
│   └── {reference-name}.md
└── assets/              바이너리 자산 (이미지·엑셀 등 — vault 루트 배치 금지)
```

## 네이밍 규칙

| 대상 | 형식 | 예시 |
|---|---|---|
| 프로젝트 디렉토리 | kebab-case | `my-api-server` |
| 문서 파일명 | kebab-case.md | `auth-strategy.md` |
| DEC 노트 (생성) | DEC-YYYY-MM-DD-NN.md | `DEC-2026-08-19-01.md` |
| 노드 페이지 (생성) | {node-id}.md — 노드 id 그대로, 점(.) 포함 | `orders.checkout-v2.coupon.md` |
| 세션 문서 | session-YYYY-MM-DD-{slug}.md | `session-2026-08-19-vault-restructure.md` |
| MOC 파일 | 단수형 명사 | `projects.md`, `glossary.md` |

세션 파일명은 위 단일 규격만 사용한다 — `handoff-*` 접두사, 무접두사 날짜 파일명, `.yaml` 세션 파일은 폐지 (legacy는 마이그레이션 대상). 시퀀스(NN) 대신 slug가 실식별자다.

## 안정 ID (frontmatter `id:`)

모든 vault 문서는 frontmatter에 이동·개명에 불변하는 안정 ID를 갖는다:

```yaml
id: "kb-shop-api-order-concepts"   # {접두}-{project}-{slug} — 생성 후 불변
aliases: ["옛 파일명"]                  # 이동·개명 시 원 식별자 보존 (Obsidian unlinked mentions 흡수)
```

접두사는 문서 클래스 전체를 커버한다 (cross-review 2026-08-19 반영):

| 접두 | 대상 | 예시 |
|---|---|---|
| `kb` | knowledge-base/, patterns/ 문서 | `kb-shop-api-order-concepts` |
| `session` | sessions/ (핸드오프·ledger) | `session-strata-2026-08-19-vault-restructure` |
| `order` | 작업지시서 `_order.md` | `order-strata-2026.08.19-01` |
| `task` | 태스크 명세 문서 | `task-strata-2026.08.19-01-task-03` |
| `dec` | DEC 노트 (생성) | `dec-strata-2026-08-19-01` |
| `relay` | relays/ packet·feedback | `relay-strata-2026-08-19-task01-core-spec-review` |
| `moc` | `_index/` 및 각 `_index.md` MOC | `moc-shop-api-knowledge-base` |
| `node` | `nodes/` 노드 페이지 (생성) | `node-shop-api-orders.checkout-v2.coupon` |
| `plan` | `planning/` 기획 문서 (임포트) | `plan-shop-api-0123456789abcdef0123456789abcdef` — slug 는 원천(Notion) id, 재임포트에 불변 |
| `doc` | 위에 속하지 않는 기타 문서 | `doc-vault-env-config` |

- **{project} 값**: `projects/{name}/` 하위는 그 프로젝트명. **프로젝트 횡단 문서**(`patterns/`, `references/`, `_index/`, vault 루트)는 `vault`를 쓴다 (예: `kb-vault-{slug}`, `moc-vault-decisions`).
- 경로는 탐색 수단일 뿐 장기 정체성이 아니다. 링크·참조의 정체성은 `id:`가 담당한다.
- 마이그레이션(이동·개명) 시 `id:`는 유지하고 옛 파일명을 `aliases:`에 추가한다.
- **노드 id는 문서 id와 다른 네임스페이스다.** `orders.checkout-v2.coupon`처럼 조상부터 점(.)으로 이은 경로이며 위 접두 체계를 따르지 않는다. 문서는 `nodes:` 필드에 노드 id를 적고, 노드 페이지의 **문서** id만 `node-{project}-{node-id}`로 접두 체계에 편입된다. `node` 접두에서만 slug에 점이 허용된다.

## KB 카테고리 체계

taxonomy.yaml에서 정의하며, 4개 카테고리로 구성:

| 카테고리 | 목적 | depth 제한 | 주요 타입 |
|----------|------|:---:|-----------|
| `domain` | 비즈니스 도메인 지식 | 3 | concept, specification, flow |
| `architecture` | 설계 결정, API, 인프라, 제약 | 2 | specification, decision, overview, constraint |
| `guides` | 온보딩, 컨벤션, 트러블슈팅 | 2 | guide, pattern, runbook |
| `references` | 외부 표준, 규격 참조 | 2 | reference, glossary |

- NN 접두사 없음 — 정렬은 taxonomy의 `order` 필드 기준
- 카테고리는 디렉토리에서 유도 (frontmatter에 기록하지 않음)
- `domain` 카테고리의 children은 프로젝트 taxonomy에서 정의
- 상세 규칙: `templates/vault/_meta/taxonomy.yaml`

카테고리는 **디렉토리 축**(문서가 어디에 놓이는가)이고, 주제 노드는 **주제 축**(문서가 무엇에 관한 것인가)이다. 둘은 별개다.
카테고리를 frontmatter에 적지 않는 이유는 경로와 중복되기 때문인데, `nodes:`는 경로에서 유도할 수 없는 정보라 중복이 아니다. 한 문서가 여러 노드에 속할 수 있고, 노드는 디렉토리를 만들지 않는다.
노드 트리의 정본과 규칙: 프로젝트 `_meta/toc.yaml`, 형식 규칙은 글로벌 taxonomy `topic_nodes` 절.

## 프로젝트 온보딩 절차

새 프로젝트를 vault에 등록할 때:

1. `vault/projects/{project-name}/` 디렉토리 생성
2. `overview.md` 작성 (필수 frontmatter 포함, document-format.md 참조)
3. `_index/projects.md` 갱신 (Index 계층 — 생성형 전환 후에는 재생성으로 대체)
4. `_meta/taxonomy.yaml` 생성 (프로젝트 도메인 토픽 정의)
5. `_meta/toc.yaml` 생성 (주제 노드 트리 — 첫 노드 하나면 충분하다. 문서가 `nodes:`를 갖기 시작하는 시점이 출발점)
6. `knowledge-base/` 하위에 카테고리 디렉토리 생성 (`domain/`, `architecture/`, `guides/`, `references/`)
7. `sessions/`, `tasks/` 디렉토리 생성. detached profile 프로젝트면 `strata/`(Tier P) 포함 — `profile.yaml` manifest 필수 (core/docs/ko/environment/data-placement.md §1.5). `decisions/`와 `nodes/`는 생성기가 만든다

### overview.md 최소 내용

```markdown
---
title: "{프로젝트명}"
type: overview
project: {project-name}
tags: [{기술스택 태그}]
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
status: active
---

## 목적
{프로젝트 목적 1-2문장}

## 기술 스택
- 언어: {language}
- 프레임워크: {framework}
- DB: {database}

## Strata 레이어 매핑
{이 프로젝트의 디렉토리 → Strata 레이어 매핑}
```

## 절대 포함하지 않는 것

- 소스 코드 (코드 스니펫은 예외적으로 허용)
- 빌드 아티팩트
- 환경별 절대 경로
- 시크릿, 키, 토큰
- 날것의 핸드오프 YAML (요약만 저장)

예외: frontmatter `covers:`의 저장소 **상대경로·심볼·엔드포인트·테이블 이름**은 코드가 아니라 포인터이므로 허용한다. 절대경로와 코드 본문은 여전히 금지다.
