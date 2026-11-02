# Knowledge Base — 색인 프로토콜

> 정본: strata-kit `core/docs/ko/knowledge-base/indexing-protocol.md` (2026-10-29 strata `docs/07-knowledge-base/indexing-protocol.md` 에서 이관, DEC-2026-10-29-11).

> **2026-10-29 현행화**: 이 문서는 현행 엔진(`store.sqlite` 하나, `python3 "$STRATA_KIT/kb"`)을 기술한다.
> 예전 `.kb/kb.sqlite`·manifest 해시 증분 빌드·sqlite-vec 설계는 폐기됐다(DEC-2026-10-28-13).
> 저장소 스키마·백엔드·게이트의 정본은 `core/docs/ko/kb-engine.md` 이고, 이 문서는 색인 범위·검색 사용법·생성 뷰를 다룬다.

## 개요

vault KB 문서를 청크 단위로 `store.sqlite` 에 색인해 에이전트의 토큰 소비를 줄이고 정밀 검색을 가능하게 합니다.
색인은 언제든 원천(vault 문서·결정 레코드·코드 표면)에서 다시 만들 수 있는 캐시이고, 각 환경이 로컬에서 만듭니다.

## 문제 정의

| 문제 | 설명 |
|---|---|
| 전체 순회 강제 | 에이전트가 _index.md → 해당 파일 전체를 읽어야 원하는 section에 도달 |
| 토큰 교차 소비 | 17개 파일(68K chars)을 탐색하며 컨텍스트 윈도우 낭비 |
| 정렬 부재 | 페이지 간 논리적 순서가 없어 에이전트 네비게이션 판단 필요 |
| 의미 검색 불가 | 키워드 일치 없으면 관련 문서 발견 불가 (임베딩 검색으로 보완) |

## 단계 구분

| 단계 | 내용 | 상태 |
|---|---|---|
| **FTS** | 청크 단위 FTS5(bm25) + frontmatter `page_order` 정렬 | 적용 — 검색 진입 시 신선도 자동 확인 |
| **벡터·하이브리드** | BAAI/bge-m3 로컬 임베딩 + FTS 와 RRF 융합 | 구현됨 — 벡터는 `python3 "$STRATA_KIT/kb" embed` 를 돌려야 생긴다(DEC-2026-10-28-09). MCP `search_docs` 의 기본 mode 는 hybrid, `kb search` CLI 의 기본은 FTS(`--semantic`·`--hybrid` 로 전환) |

예전의 "Phase 1(FTS5 + manifest 해시) / Phase 2(sqlite-vec·`--with-vectors`, 구현됨·미적용)" 구분은 폐기됐다. 색인은 둘로 나뉘지 않고 store 하나이며, 벡터는 store 의 청크에 붙는다.

## 아키텍처

### 파일 배치

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — 유일한 색인 (로컬 빌드 결과물)
│   ├── manifest.json           # 추적 끔 — 색인 메타, 머신마다 만든다 (DEC-2026-10-29-04)
│   ├── link-baseline.json      # 링크 게이트 기준선 (줄어드는 방향으로만 갱신)
│   └── review-candidates.json  # .gitignore — 리뷰 후보 (생성물)
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # 색인 원본
```

`.kb/store.sqlite` 와 그 `-wal`·`-shm` 는 vault `.gitignore` 에 있다. 확인: `.gitignore` 의 "KB store" 절.
스키마는 파일이 아니라 코드(`kb/store.py`)가 정의한다. `schema.sql` 은 없다(DEC-2026-10-28-13).

### 빌드 엔진 배치

```
strata-kit/
└── kb/                         # git 추적 — 색인 엔진 (python3 "$STRATA_KIT/kb" build-index)
```

빌드 엔진은 strata-kit 레포에 위치합니다. 실행 시 `$STRATA_VAULT` 환경 변수로 vault 경로를 참조합니다.

### 데이터 흐름

```
MD 파일 편집 → git commit + push
                    ↓
다른 환경: git pull
                    ↓
검색 진입(kb search / MCP) 시 자동:               engine.ensure_fresh_store
  원천 mtime 과 store 의 built_at 비교 (해시 없음, 저비용)
    ├─ 신선 → 바로 조회
    ├─ stale → store 전체 재생성 (1~2초)
    └─ store 부재(새 머신) → 같은 경로로 자동 생성
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · 임베딩 캐시)
                    ↓
에이전트: kb search / MCP search_docs → chunk + file:line 반환
```

- 증분 재색인은 없다. store 는 매번 전체를 다시 만든다(1~2초). 변경분만 고르는 manifest 해시 비교는 폐기됐다.
- 수동 실행(`python3 "$STRATA_KIT/kb" build-index`)과 MCP `build_index` 는 가능하나 **일상 경로는 자동**이다.
- 신선도 검사·재생성 실패는 조회를 막지 않는다(경고 후 기존 store 사용). 탈출구: `KB_NO_REFRESH=1`.
- `build-index` 는 store 를 재생성한 뒤 생성 뷰(노드 페이지·Obsidian sortspec·리뷰 Inbox·`manifest.json`)와 taxonomy 검증 경고를 냅니다. block 위반이면 exit 2. 동작·역할은 `core/docs/ko/kb-engine.md`.
- 임베딩은 `build-index` 가 계산하지 않는다. `python3 "$STRATA_KIT/kb" embed` 가 빠진 청크만 계산해 store 에 넣고, 계산한 벡터는 `embeddings` 캐시에 남아 store 를 다시 만들어도 재사용된다.

### 색인 커버리지 (2026.08.19-06 B1)

- **Knowledge**: `projects/*/knowledge-base/` — 전문 색인 (기존). 2026-09-08부터 `patterns/`·`_index/glossary.md`(프로젝트값 `vault`)·`projects/*/overview.md`도 전문 색인 — vault-structure.md 3계층 표의 Knowledge 범위와 일치.
- **Archive**: `projects/*/sessions/`·`tasks/`의 `.md` — **메타(topic·orders·kb_updates·decisions_made·nodes·doc_change) +
  본문 요약부(첫 40줄)만** 색인. `nodes`가 빠지면 노드 페이지의 "작업이력" 면을 만들 수 없으므로 화이트리스트에 포함한다. category=`archive`, topic=`sessions|tasks` 파셋으로 구분·필터
  (MCP `category` 필터). "어느 세션에서 다뤘는가"를 검색으로 답하기 위함. **검색 기본값에서는 Archive·Planning 을 제외한다** (DEC-2026-09-30-03) —
  이력까지 보려면 `kb search --include-history`, MCP `search_docs(include_history=true)` 또는 `category` 를 명시한다. `--include-history` 는 결정·오더 레코드도 함께 검색한다.
- Archive에는 KB 검증(lifecycle 등)을 적용하지 않는다 — ledger status(open/closed)는 KB 계약 밖.
  **예외**: `node_id_check`(nodes 값이 toc.yaml에 있는가)는 Archive에도 적용한다. 노드 오탈자는 작업이력 면에서 세션을 사라지게 하기 때문이다.
- **Planning**: `projects/*/planning/{source}/` — 기획 원문 **전문 색인** + KB 검증(required_fields·lifecycle_override·node_id). category=`planning`, topic=`{source}` 파셋. 노드 페이지 "기획" 면의 원천. status 가 기획 상태(active 아님)라 리뷰 후보 정책 밖 (DEC-2026-09-09-01).
- **노드 페이지**(`projects/*/nodes/`)는 `indexed: metadata` — 각 면의 원문이 이미 색인되어 있으므로 요약부만.
- **DEC 노트**(`projects/*/decisions/`)는 문서로는 색인하지 않는다 (현행 유지). 결정은 결정 레코드 provider 가 store 의 결정 노드로 넣고, 결정의 노드 소속은 레코드 정본의 `nodes`를 노드 페이지 생성기가 읽는다.
- 심볼릭 링크(`latest.md`)·yaml은 색인하지 않는다.

## KB Result Contract — 폐기 (DEC-2026-08-19-06)

공통 결과 스키마 계약은 **폐기됐다**. 제정 후 어떤 소비자(kb-search, strata-mcp)도 구현하지 않았고
각자의 결과 형태로 안정 동작 중이며, 계약의 전제였던 다중 소비자(strata-kb-server, Hub)는 존재하지 않는다.

- **부활 조건**: 두 번째 소비 표면(Hub 등)이 실제로 등장하면, 그 시점의 실사용 필드에서 계약을 재설계한다.
- 노드 페이지 생성기는 vault 내부 생성물이라 "두 번째 소비 표면"이 아니다. 이 폐기 결정을 뒤집지 않는다.
- 폐기 전 계약 전문은 git 이력(이 파일, 2026-08-19 이전) 참조.

## 저장소 스키마

스키마(`nodes`·`edges`·`chunks`·`baselines`·`revisions`, FTS5 가상 테이블 `chunks_fts`, `embeddings` 캐시)의 정본은 `core/docs/ko/kb-engine.md` 의 "스키마" 절이다. 여기서는 검색에 필요한 것만 적는다.

- 검색 단위는 `chunks` 이다. 청크는 heading·text·title·tags 와 `meta_json`(heading_level·line_start·line_end·char_count)을 가진다. 문서·결정·오더가 FTS 테이블 하나, bm25 척도 하나를 쓴다.
- FTS5 는 heading·text·title·tags 네 열을 `unicode61` 로 색인한다.
- 문서의 taxonomy 파셋(category·topic·section_name·page_order 등)은 문서 노드의 payload 에 있고, `kb search` 의 필터와 `--toc` 정렬이 읽는다.
- 링크는 `links` 엣지, 문서 사이 관계(supersedes 등)와 `covers` 도 엣지다. 예전 `document_links` 테이블은 없다.

예전 스키마(`documents`·`chunks`·`chunks_fts`(doc_title·doc_tags 열)·`document_links`·`coverage` 테이블, `sha256`·`section_name` 컬럼, `chunks_vec`)는 legacy 색인(`.kb/kb.sqlite`)의 것이며 DEC-2026-10-28-13 으로 폐기됐다. SQL 로 직접 조회하던 방식도 같이 사라졌다. 질의는 `kb search`·MCP·`kb coverage` 로 한다.

### 주제 노드·커버리지

문서의 `stable_id`·`nodes`·`covers`·`doc_change` frontmatter 는 store 의 노드 payload 와 `covers` 엣지가 됩니다. 코드 표면 → 문서 역질의 규칙은 같다.

- "이 경로를 소유한 명세는 무엇인가": `python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- "이 노드의 최종형상은 어느 문서인가": `kb coverage node` (노드 페이지 생성기가 사용)
- "이 경로가 바뀐 뒤 소유 문서가 갱신됐는가": 세션 종료 게이트 `kb coverage-gate`
- 노드 트리 자체는 `_meta/toc.yaml`을 직접 읽는다. `endpoints`·`tables`는 파일 경로로 해석하지 않으며 노드 페이지 표시용이다.

빌드 시 검증(전부 warn): `node_id_check`(형식, toc.yaml 존재·등재 — Archive 에도 적용), `covers_path_check`(구조·상대경로·파일 단위 금지),
`supersedes_symmetry_check`(A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A), doc_change 값·사유. 리뷰 후보는 생성물(리뷰 Inbox)로 기록되고 전이는 명시 명령(`build-index --apply-review`).

## 변경 감지와 다중 환경 동기화

변경 감지는 manifest 해시가 아니라 원천 파일 mtime 과 store 의 `built_at` 비교다(`engine.ensure_fresh_store`). 그래서 환경 사이에 합의할 색인 상태가 없다. 공유하는 것은 vault 문서와 결정 레코드뿐이고, store 는 환경마다 로컬에서 만든다.

```
[환경 A — 문서 편집]
1. MD 파일 편집
2. git commit + push   (세션 종료 시 handoff 가 vault 동기화)

[환경 B — 동기화]
1. git pull
2. 검색 진입 시 store 가 자동 재생성 — 수동으로는 python3 "$STRATA_KIT/kb" build-index
```

**핵심 원리:** store 는 캐시라서 git 에 올리지 않는다(`.gitignore`). 바이너리 충돌이 없고, 어느 머신에서든 같은 원천에서 같은 결과를 다시 만든다.

생성물 중 추적하는 것과 쓰는 주체는 DEC-2026-10-29-04 가 정한다.

| 생성물 | 추적 | 쓰는 주체 |
|---|---|---|
| `.kb/store.sqlite` | 안 함 | 각 머신의 검색 진입·`build-index` |
| `.kb/manifest.json` | 안 함 (머신별 비교 기록) | 각 머신의 `build-index` |
| DEC 노트 (`projects/*/decisions/`) | 함 | 결정 CLI — 결정을 기록한 세션이 레코드와 함께 커밋 |
| 노드 페이지·`_index/review-needed.md` | 함 | librarian 하루 한 번 `kb views-publish` (build-index 후 이 파일들만 commit-push). 일반 세션의 `build-index` 는 로컬 색인만 갱신하고 이 파일들을 커밋하지 않는다 |
| `.kb/link-baseline.json` | 함 | 줄어드는 방향으로만 갱신 |

예전의 "`manifest.json` 을 git 으로 공유해 파일 상태를 합의하고 변경분만 색인" 방식은 legacy 설계였고 폐기됐다(DEC-2026-10-28-13, DEC-2026-10-29-04).

## 에이전트 검색 프로토콜

### 검색 우선순위

```
① FTS5 키워드 검색 (정확한 용어 알 때)
② FTS5 복합 검색 (AND/OR 조합, --category·--topic 필터)
③ 메타데이터 조회 (--toc 정렬된 목차, --doc 문서 내 청크)
④ 하이브리드·시맨틱 검색 (자연어 질의 — 벡터 필요)
```

에이전트는 SQL 이 아니라 `kb search` 또는 MCP `search_docs`(mode: hybrid 기본 · dense · fts)를 쓴다. 결과는 청크의 `file:L줄-줄` 위치와 문자 수를 반환한다.

### 사용 예시

**키워드 검색 — 관련 chunk 반환:**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**복합 검색 — AND + 필터:**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**정렬된 목차 조회:**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**정밀 위치 반환 — Read tool 연계:**
```
kb search "FormulaBaseStructure"
# 결과: domain/orders/payment-shipping.md  위치: L46-101
# → Read tool에 offset=46, limit=55 전달
```

## FTS5 검색 구문 참조

`kb search` 는 질의의 각 토큰을 따옴표로 감싸 FTS5 에 넘긴다. 그래서 아래 구문만 동작한다.

| 구문 | 예시 | 설명 |
|---|---|---|
| 단일 키워드 | `환불수수료` | 해당 토큰 포함 chunk |
| 공백 나열 | `Transactional Composite` | 두 토큰 모두 포함 (AND) |
| AND | `Transactional AND Composite` | 두 토큰 모두 포함 |
| OR | `Payment OR Shipping` | 하나 이상 포함 |
| NOT | `환불 NOT Coupon` | 제외 조건 |
| prefix | `Refund*` | Refund으로 시작하는 토큰 |

동작하지 않는 구문: 열 지정(`doc_tags:orders`·`tags:orders` — 결과 없음, 대신 `--category`·`--topic` 필터, 태그만 볼 때는 `--tags`), 구문 검색(`"REST Docs"` — 따옴표가 벗겨져 두 토큰의 AND 가 된다), `NEAR`. 이전 문서의 `doc_tags:`·`content:` 열 이름은 legacy 색인의 열이다(현행 열은 heading·text·title·tags).

## Frontmatter 확장 — page_order 필드

기존 document-format.md의 frontmatter에 정렬 필드를 추가합니다:

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain은 카테고리(디렉토리)이지 문서 타입이 아님
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ 신규 — 섹션 내 문서 순서
---
```

`--toc` 는 taxonomy 의 category·topic 순서를 먼저, 그 안에서 `page_order` 로 정렬한다(taxonomy 이전의 NN-prefix 디렉토리 문서는 `section_order` 를 쓴다).
`page_order`는 frontmatter에 명시하여 섹션 내 논리적 순서를 정의합니다.

## 토큰 절감 효과 (실측)

아래는 legacy FTS5 색인 시절(2026-04) 한 백엔드 프로젝트 vault 기준 실측이다(15 문서, 210 chunks, 68K chars). 청크 단위로 읽는다는 원리는 현행 store 도 같고, 수치를 현행 엔진으로 다시 잰 적은 없다.

| 검색 질의 | 기존 (전체 읽기) | FTS5 (chunk) | 절감율 |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3파일) | 6,758 chars | **52%** |

## 벡터 검색 (bge-m3 하이브리드)

정본: `core/docs/ko/kb-engine.md` 의 검색 절, DEC-2026-10-28-09.

### 요약

| 항목 | 현행 |
|---|---|
| 모델 | BAAI/bge-m3, 로컬 실행(sentence-transformers, Apple Silicon 은 MPS), 1024차원 정규화 벡터 |
| 저장 | store 의 `chunks.embedding` + 재생성에도 남는 `embeddings(model, text_hash, dim, vector)` 캐시 |
| 벡터 검색 | numpy 코사인 브루트포스 (청크 7천 개 규모에서 수 ms — ANN 불필요) |
| 하이브리드 | FTS(bm25) 와 벡터의 RRF(k=60) 융합 |
| 효과 판단 | `python3 "$STRATA_KIT/kb" search-eval` — vault `_meta/search-eval.yaml` 의 질의 세트로 recall@k (fts · dense · hybrid) |
| 임베딩 계산 | `python3 "$STRATA_KIT/kb" embed` (빠진 청크만. `--model` · `--batch` · `--max-seq` · `--max N`) |

### 대안과 채택하지 않은 이유

| 대안 | 판단 |
|---|---|
| sqlite-vec | 청크 10만 개를 넘으면 어댑터로 바꾼다(DEC-2026-10-28-09). 지금은 불필요 |
| LanceDB 등 외부 벡터 DB | 저장소 하나 계약(DEC-2026-10-28-04)과 어긋나고 이 규모에서 이득 없음 — 도입하지 않음 |
| khoj | 별도 호스트·UI·DB 를 가진 앱이라 도입하지 않음 |
| paraphrase-multilingual-MiniLM-L12-v2 (384차원) | legacy 설계의 모델. bge-m3 로 대체 |
| ONNX Runtime · 클라우드 임베딩 API | 채택하지 않음. 임베더 provider 는 교체 가능하나(kb-engine.md) 현재 구현은 bge-m3 로컬뿐 |

예전 `build-index --with-vectors`, `apsw`(sqlite-vec 로딩용), `chunks_vec` 가상 테이블은 legacy 설계였고 존재하지 않는다.

## 검색 도구 치트시트

### 빌드

```bash
# 일상: 필요 없음 — 검색 진입 시 store 가 stale 이면 자동 재생성

# store + 생성 뷰(노드 페이지·sortspec·리뷰 Inbox·manifest) 수동 빌드
python3 "$STRATA_KIT/kb" build-index

# 보고 범위만 한 프로젝트로 (store 는 항상 전체)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# store 만 재생성 / 통계
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# 빠진 청크 임베딩 계산 (시맨틱·하이브리드 검색 전에)
python3 "$STRATA_KIT/kb" embed

# 리뷰 후보를 status: review-needed 로 전이하고 다시 빌드
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` 는 호환용 플래그라 효과가 없다(store 는 매번 전체 재생성). `--with-vectors` 는 없다.

### 검색 (kb search)

> 아래 `kb search`는 `python3 "$STRATA_KIT/kb" search`의 약칭입니다.

```bash
# ─── FTS5 키워드 검색 ───
kb search "환불수수료"                          # 단일 키워드
kb search "Transactional AND Composite"       # AND 복합
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # 카테고리·토픽 필터 (열 지정 구문 대신)
kb search "환불수수료" --limit 10 --content      # 결과 수 + 내용 미리보기
kb search "jwt" --category architecture       # 카테고리 필터 (--topic, --status, --project 도 있다)
kb search "환불수수료" --include-history         # 세션·태스크·기획 원문과 결정·오더까지

# ─── 시맨틱·하이브리드 검색 (kb embed 로 벡터를 만든 뒤) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── 네비게이션 ───
kb search --toc                               # 전체 목차 (정렬)
kb search --toc --category domain             # 카테고리 필터
kb search --doc "domain/orders/payment-shipping.md"       # 문서 내 chunk 목차
kb search --tags orders                          # 태그 검색 (질의어 없이 태그만)
kb search --stats                             # 색인 통계
```

`--section` 은 taxonomy 이전 NN-section 디렉토리를 위한 호환 필터다. 새 문서는 `--category`·`--topic` 을 쓴다.

### FTS5 vs 시맨틱 — 언제 무엇을 쓸 것인가

| 상황 | 추천 | 이유 |
|------|------|------|
| 정확한 클래스명/함수명 알 때 | FTS5 | `FormulaBaseStructure` → 정확 매칭, 즉시 |
| 특정 용어 검색 | FTS5 | `환불수수료`, `TransactionalExecutor` → BM25 rank |
| 자연어 질문 | **시맨틱·하이브리드** | "환불 금액을 계산하는 흐름?" → 키워드 불일치 극복 |
| FTS5 결과 없음 | **시맨틱** | "인증 토큰 만료 처리" → FTS5 0건, 시맨틱 반환 |
| 카테고리/토픽으로 범위 축소 후 | FTS5 | `--category domain --topic orders` 필터 |
| 어디서부터 읽어야 할지 모를 때 | `--toc` | 정렬된 목차 → 문서 구조 파악 |

## FTS5 키워드 분할 가이드

FTS5의 `unicode61` 토크나이저는 **공백과 구두점 기준으로만 토큰을 분리**합니다.
한국어 형태소 분석을 수행하지 않으므로, 검색 시 키워드 분할 전략이 중요합니다.

### 문제: 왜 키워드 분할이 필요한가

```
문서 원문:  "환불수수료 변경 시 재계산 처리"
              ↓ unicode61 토크나이징
토큰:       ["환불수수료", "변경", "시", "재계산", "처리"]
```

| 검색 쿼리 | 매칭 여부 | 이유 |
|-----------|----------|------|
| `환불수수료` | ✅ | 정확한 토큰 일치 |
| `환불수수료변경` | ❌ | "환불수수료변경"이라는 토큰은 존재하지 않음 |
| `환불수수료 AND 변경` | ✅ | 두 토큰 각각 존재 |
| `환불` | ❌ | "환불수수료"의 부분문자열은 매칭 안 됨 |
| `환불*` | ✅ | prefix 검색으로 "환불수수료" 매칭 |

### 분할 규칙

**1. 복합 한국어 용어는 띄어쓰기로 분리하여 AND 검색**

```bash
# ❌ 붙여쓰면 미매칭
kb search "환불수수료변경"

# ✅ 분리 + AND
kb search "환불수수료 AND 변경"
```

**2. 부분 매칭이 필요하면 prefix(*) 사용**

```bash
# ❌ "환불"만으로는 "환불수수료"를 못 찾음
kb search "환불"

# ✅ prefix로 "환불수수료", "환불금액", "환불요청" 모두 매칭
kb search "환불*"
```

**3. 영어 클래스명은 대소문자 무관, CamelCase 분리 없음**

```bash
# ✅ unicode61은 대소문자 정규화함
kb search "formulabasestructure"      # FormulaBaseStructure 매칭

# ❌ CamelCase 내부 분리는 안 됨
kb search "Formula AND Base"          # 두 단어가 각각 있어야 함

# ✅ prefix로 우회
kb search "Formula*"
```

**4. 한국어+영어 혼합 질의**

```bash
# ✅ 각 언어 토큰을 AND로 연결
kb search "Payment AND 정산식"

# ✅ 카테고리·토픽 필터 + 내용 검색 조합
kb search "Payment" --category domain --topic orders
```

**5. 키워드 분할로도 안 되면 → 시맨틱·하이브리드 검색으로 전환**

```bash
# FTS5로 찾기 어려운 자연어 질의
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

한국어 조사·합성어로 FTS 가 놓치는 구간(평가 세트 기준 4~8%)은 벡터가 맡고, 평가 뒤 FTS5 trigram 테이블이나 bge-m3 sparse 로 보강하기로 했다(DEC-2026-10-28-09).

### 에이전트 검색 의사결정 트리

```
질문 수신
  │
  ├─ 정확한 용어/클래스명 알고 있음?
  │   └─ YES → FTS5: kb search "용어"
  │
  ├─ 한국어 복합 용어?
  │   └─ YES → FTS5: 띄어쓰기 + AND 분할
  │            예: "환불수수료 AND 변경 AND 재계산"
  │
  ├─ 부분 매칭 필요?
  │   └─ YES → FTS5: prefix(*)
  │            예: "Refund*", "환불*"
  │
  ├─ 자연어 질문?
  │   └─ YES → 하이브리드/시맨틱: kb search "질문" --hybrid
  │
  └─ FTS5 결과 0건?
      └─ 시맨틱으로 재시도
```

## 핵심 설계 결정

| 결정 | 근거 |
|------|------|
| `store.sqlite` 하나가 유일한 색인, git 에 올리지 않음 | 바이너리 merge conflict 제거, 색인 둘이 낳던 스키마·신선도 가드 이중화 제거 (DEC-2026-10-28-13) |
| 신선도는 원천 mtime 비교, store 는 매번 전체 재생성 | 1~2초라 증분이 불필요. 부분 빌드가 store 를 자르면 다른 프로젝트 뷰를 잃음 (DEC-2026-10-28-13) |
| `manifest.json` 은 추적하지 않음 | 읽는 사람이 없는 머신별 비교 기록 (DEC-2026-10-29-04) |
| 빌드 엔진은 strata-kit 레포에 위치 | 방법론 자체의 도구로 관리, 프로젝트 독립 |
| frontmatter이 single source of truth | Obsidian + FTS5 + Dataview 양쪽이 동일 데이터 참조 |
| 청크에 heading·title·tags·meta 를 함께 둠 | FTS 한 테이블·bm25 한 척도로 문서·결정·오더를 순위화, 위치 출력 (DEC-2026-10-28-08) |
| bge-m3 임베딩 + numpy 브루트포스 + FTS 와 RRF | 한·영 혼용에 강하고 8192 토큰이라 긴 청크를 자르지 않음. 이 규모에 ANN 불필요 (DEC-2026-10-28-09) |
| 벡터 효과는 평가 세트 recall@k 로 판단 | `kb search-eval` |

폐기된 legacy 결정: manifest.json git 추적·kb.sqlite `.gitignore`, SHA256 해시 기반 증분 빌드, `paraphrase-multilingual-MiniLM-L12-v2`, `apsw`·sqlite-vec, cosine distance 0~1 해석(MiniLM 용). 모두 DEC-2026-10-28-13 으로 legacy 색인과 함께 사라졌거나 DEC-2026-10-28-09 로 대체됐다.

## 의존성 요약

| 패키지 | 용도 | 필요한 때 |
|--------|------|-----------|
| Python 3 | `kb` 실행 | 항상 |
| SQLite 3 (FTS5 포함) | store | 항상 (OS 기본) |
| PyYAML | frontmatter·taxonomy 파싱 | 항상 |
| sentence-transformers (PyTorch 포함, ~500MB) | bge-m3 임베딩 계산 | `kb embed` 를 쓸 때만 |
| numpy | 벡터 코사인 | 시맨틱·하이브리드 검색 시 |

sqlite-vec·apsw 는 더 이상 쓰지 않는다. 임베딩 없이도 FTS 검색과 모든 생성 뷰가 동작한다. 정확한 의존 목록은 `kb/` 의 import 를 기준으로 한다.

### 실행 환경

- 상주 프로세스 없음. GPU 불필요(Apple Silicon 에서는 MPS 로 임베딩이 빠르다).
- store 재생성 1~2초(문서 760·청크 약 7천 규모, DEC-2026-10-28-13·09 실측).
- 임베딩 계산은 처음 한 번 오래 걸리고, 이후는 `embeddings` 캐시 덕에 바뀐 청크만 계산한다.

## 한계점

| 한계 | 설명 | 대응 |
|---|---|---|
| 한국어 형태소 (FTS5) | unicode61은 공백 분리만 — "환불수수료변경" 미매칭 | 키워드 분할 가이드 준수, 시맨틱 병행 |
| CamelCase 미분리 (FTS5) | FormulaBaseStructure → 단일 토큰 | prefix(*) 검색 또는 전체 입력 |
| 열 지정·구문·NEAR 미지원 | 질의 토큰이 모두 따옴표로 감싸져 FTS5 고급 구문이 동작하지 않음 | `--category`·`--topic` 필터, AND 로 대체 |
| 시맨틱 검색 사전 준비 | `kb embed` 로 벡터를 먼저 만들어야 하고, 모델 로드로 첫 질의가 느리다 | FTS5를 1차로, 시맨틱은 fallback |
| BM25 rank만 (FTS) | 문서 구조/중요도 가중치 없음 | page_order 로 목차 정렬, 하이브리드 병행 |
| Obsidian 비실행 시 | Dataview 쿼리 불가 | FTS5/시맨틱은 Obsidian 독립 동작 |
