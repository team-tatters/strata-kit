# Knowledge Base — Indexing Protocol

> Canonical: strata-kit `core/docs/en/knowledge-base/indexing-protocol.md` (migrated 2026-10-29 from strata `docs/07-knowledge-base/indexing-protocol.md`, DEC-2026-10-29-11).

> **Updated 2026-10-29**: This document describes the current engine (a single `store.sqlite`, `python3 "$STRATA_KIT/kb"`).
> The old `.kb/kb.sqlite`, manifest-hash incremental build and sqlite-vec design were retired (DEC-2026-10-28-13).
> The canonical source for the storage schema, backends and gates is `core/docs/en/kb-engine.md`; this document covers indexing scope, how to search, and generated views.

## Overview

Vault KB documents are indexed into `store.sqlite` chunk by chunk, which reduces the agent's token consumption and enables precise search.
The index is a cache that can be rebuilt at any time from its sources (vault documents, decision records, code surface), and each environment builds it locally.

## Problem definition

| Problem | Description |
|---|---|
| Forced full traversal | To reach the section it wants, an agent has to read _index.md and then the whole of each relevant file |
| Cross-file token consumption | Browsing 17 files (68K chars) wastes the context window |
| No ordering | Pages have no logical order between them, so the agent has to decide how to navigate |
| No semantic search | Without a keyword match, related documents cannot be found (complemented by embedding search) |

## Phases

| Phase | Content | Status |
|---|---|---|
| **FTS** | Chunk-level FTS5 (bm25) + ordering by frontmatter `page_order` | Applied — freshness is checked automatically on search entry |
| **Vector / hybrid** | Local BAAI/bge-m3 embeddings + RRF fusion with FTS | Implemented — vectors exist only after you run `python3 "$STRATA_KIT/kb" embed` (DEC-2026-10-28-09). The default mode of MCP `search_docs` is hybrid; the default of the `kb search` CLI is FTS (switch with `--semantic` or `--hybrid`) |

The old split into "Phase 1 (FTS5 + manifest hash) / Phase 2 (sqlite-vec, `--with-vectors`, implemented but not applied)" was retired. The index is not split in two; there is one store, and vectors attach to the store's chunks.

## Architecture

### File layout

```
vault/
├── .kb/
│   ├── store.sqlite            # .gitignore — the only index (locally built artifact)
│   ├── manifest.json           # untracked — index metadata, built per machine (DEC-2026-10-29-04)
│   ├── link-baseline.json      # link gate baseline (updated only in the shrinking direction)
│   └── review-candidates.json  # .gitignore — review candidates (generated)
│
├── .gitignore
└── projects/{name}/knowledge-base/
    └── *.md                    # index sources
```

`.kb/store.sqlite` and its `-wal` and `-shm` files are in the vault `.gitignore`. To check, see the "KB store" section of `.gitignore`.
The schema is defined by code (`kb/store.py`), not by a file. There is no `schema.sql` (DEC-2026-10-28-13).

### Build engine layout

```
strata-kit/
└── kb/                         # git-tracked — index engine (python3 "$STRATA_KIT/kb" build-index)
```

The build engine lives in the strata-kit repository. At run time it finds the vault through the `$STRATA_VAULT` environment variable.

### Data flow

```
Edit MD file → git commit + push
                    ↓
Other environment: git pull
                    ↓
On search entry (kb search / MCP), automatically:  engine.ensure_fresh_store
  compare source mtime with the store's built_at (no hash, low cost)
    ├─ fresh → query directly
    ├─ stale → rebuild the whole store (1-2 s)
    └─ store missing (new machine) → generated automatically through the same path
                    ↓
store.sqlite (nodes · edges · chunks + FTS5 · embedding cache)
                    ↓
Agent: kb search / MCP search_docs → returns chunk + file:line
```

- There is no incremental re-indexing. The store is rebuilt in full every time (1-2 s). The manifest hash comparison that picked only the changed files was retired.
- Manual runs (`python3 "$STRATA_KIT/kb" build-index`) and MCP `build_index` are possible, but **the everyday path is automatic**.
- A failed freshness check or rebuild does not block queries (it warns and uses the existing store). Escape hatch: `KB_NO_REFRESH=1`.
- After rebuilding the store, `build-index` emits the generated views (node pages, Obsidian sortspec, review Inbox, `manifest.json`) and taxonomy validation warnings. It exits with code 2 on a block violation. For behavior and roles, see `core/docs/en/kb-engine.md`.
- `build-index` does not compute embeddings. `python3 "$STRATA_KIT/kb" embed` computes only the missing chunks and puts them in the store; the computed vectors stay in the `embeddings` cache and are reused even when the store is rebuilt.

### Index coverage (2026.08.19-06 B1)

- **Knowledge**: `projects/*/knowledge-base/` — full-text indexed (existing). Since 2026-09-08, `patterns/`, `_index/glossary.md` (project value `vault`) and `projects/*/overview.md` are also full-text indexed — matching the Knowledge scope in the three-layer table of vault-structure.md.
- **Archive**: `.md` files under `projects/*/sessions/` and `tasks/` — only **metadata (topic · orders · kb_updates · decisions_made · nodes · doc_change) +
  the body summary part (first 40 lines)** are indexed. `nodes` is on the whitelist because without it the "work history" face of a node page cannot be built. They are distinguished and filtered by the facets category=`archive`, topic=`sessions|tasks`
  (MCP `category` filter). The purpose is to answer "which session dealt with this?" through search. **Archive and Planning are excluded from the search defaults** (DEC-2026-09-30-03) —
  to include history, use `kb search --include-history`, MCP `search_docs(include_history=true)`, or specify `category` explicitly. `--include-history` also searches decision and order records.
- KB validation (lifecycle and so on) is not applied to Archive — ledger status (open/closed) is outside the KB contract.
  **Exception**: `node_id_check` (is the value of nodes in toc.yaml?) also applies to Archive, because a typo in a node makes the session vanish from the work history face.
- **Planning**: `projects/*/planning/{source}/` — **full-text index** of the original planning text + KB validation (required_fields · lifecycle_override · node_id). Facets category=`planning`, topic=`{source}`. It is the source of the node page's "planning" face. Its status is a planning status (not active), so it is outside the review-candidate policy (DEC-2026-09-09-01).
- **Node pages** (`projects/*/nodes/`) are `indexed: metadata` — only the summary part, since the original text of each face is already indexed.
- **DEC notes** (`projects/*/decisions/`) are not indexed as documents (unchanged). The decision-record provider puts decisions into the store as decision nodes, and the node page generator reads `nodes` from the canonical record to determine which node a decision belongs to.
- Symbolic links (`latest.md`) and yaml are not indexed.

## KB Result Contract — retired (DEC-2026-08-19-06)

The common result-schema contract has been **retired**. Since it was established, no consumer (kb-search, strata-mcp) implemented it,
each runs stably with its own result shape, and the multiple consumers the contract presupposed (strata-kb-server, Hub) do not exist.

- **Condition for revival**: if a second consuming surface (such as Hub) actually appears, redesign the contract from the fields in real use at that time.
- The node page generator produces output inside the vault, so it is not a "second consuming surface". This retirement decision is not reversed.
- For the full text of the contract before retirement, see git history (this file, before 2026-08-19).

## Storage schema

The canonical source for the schema (`nodes`, `edges`, `chunks`, `baselines`, `revisions`, the FTS5 virtual table `chunks_fts`, and the `embeddings` cache) is the "Schema" section of `core/docs/en/kb-engine.md`. Only what search needs is written here.

- The unit of search is `chunks`. A chunk has heading, text, title, tags and `meta_json` (heading_level · line_start · line_end · char_count). Documents, decisions and orders share one FTS table and one bm25 scale.
- FTS5 indexes the four columns heading, text, title and tags with `unicode61`.
- A document's taxonomy facets (category · topic · section_name · page_order and so on) live in the document node's payload and are read by the `kb search` filters and the `--toc` ordering.
- Links are `links` edges; relations between documents (supersedes and so on) and `covers` are also edges. The old `document_links` table does not exist.

The old schema (the `documents`, `chunks`, `chunks_fts` (doc_title and doc_tags columns), `document_links` and `coverage` tables, the `sha256` and `section_name` columns, and `chunks_vec`) belongs to the legacy index (`.kb/kb.sqlite`) and was retired by DEC-2026-10-28-13. Querying directly with SQL went away with it. Query through `kb search`, MCP and `kb coverage`.

### Subject nodes and coverage

A document's `stable_id`, `nodes`, `covers` and `doc_change` frontmatter become the store's node payload and `covers` edges. The rules for reverse lookup from code surface to document are unchanged.

- "Which spec owns this path?": `python3 "$STRATA_KIT/kb" coverage resolve|nodes|unowned|docs-to-update`
- "Which document is the final shape of this node?": `kb coverage node` (used by the node page generator)
- "Was the owning document updated after this path changed?": the session-end gate `kb coverage-gate`
- The node tree itself reads `_meta/toc.yaml` directly. `endpoints` and `tables` are not resolved as file paths; they are for display on node pages.

Build-time validations (all warn): `node_id_check` (format, existence and listing in toc.yaml — also applied to Archive), `covers_path_check` (structure · relative paths · file-level entries forbidden),
`supersedes_symmetry_check` (A.supersedes=B ⇔ B.status=superseded ∧ B.superseded_by=A), and doc_change values and reasons. Review candidates are recorded as a generated artifact (the review Inbox), and the transition happens only through an explicit command (`build-index --apply-review`).

## Change detection and multi-environment sync

Change detection compares source file mtime with the store's `built_at` (`engine.ensure_fresh_store`), not a manifest hash. So there is no index state for the environments to agree on. What is shared is only vault documents and decision records; each environment builds the store locally.

```
[Environment A — editing documents]
1. Edit MD files
2. git commit + push   (at session end, handoff syncs the vault)

[Environment B — sync]
1. git pull
2. The store is rebuilt automatically on search entry — manually: python3 "$STRATA_KIT/kb" build-index
```

**Key principle:** The store is a cache, so it is not put in git (`.gitignore`). There are no binary conflicts, and any machine rebuilds the same result from the same sources.

DEC-2026-10-29-04 decides which generated artifacts are tracked and who writes them.

| Artifact | Tracked | Written by |
|---|---|---|
| `.kb/store.sqlite` | No | Each machine's search entry and `build-index` |
| `.kb/manifest.json` | No (per-machine comparison record) | Each machine's `build-index` |
| DEC notes (`projects/*/decisions/`) | Yes | The decision CLI — the session that recorded the decision commits them together with the record |
| Node pages and `_index/review-needed.md` | Yes | The librarian, once a day, with `kb views-publish` (commit-push only these files after build-index). A regular session's `build-index` updates only the local index and does not commit these files |
| `.kb/link-baseline.json` | Yes | Updated only in the shrinking direction |

The old approach of "sharing `manifest.json` through git to agree on file state and index only the changes" was a legacy design and was retired (DEC-2026-10-28-13, DEC-2026-10-29-04).

## Agent search protocol

### Search priority

```
① FTS5 keyword search (when you know the exact term)
② FTS5 compound search (AND/OR combinations, --category and --topic filters)
③ Metadata lookup (--toc ordered table of contents, --doc chunks within a document)
④ Hybrid / semantic search (natural-language queries — requires vectors)
```

Agents use `kb search` or MCP `search_docs` (mode: hybrid by default · dense · fts), not SQL. Results return the chunk's `file:Lline-line` location and character count.

### Usage examples

**Keyword search — returns the relevant chunks:**
```bash
python3 "$STRATA_KIT/kb" search "환불수수료" --limit 5
```

**Compound search — AND + filters:**
```bash
python3 "$STRATA_KIT/kb" search "정산식 AND Payment" --category domain
python3 "$STRATA_KIT/kb" search "정산식" --category domain --topic orders
```

**Ordered table-of-contents lookup:**
```bash
python3 "$STRATA_KIT/kb" search --toc --category domain
```

**Precise location return — hand-off to the Read tool:**
```
kb search "FormulaBaseStructure"
# Result: domain/orders/payment-shipping.md  location: L46-101
# → pass offset=46, limit=55 to the Read tool
```

## FTS5 search syntax reference

`kb search` wraps each token of the query in quotes before passing it to FTS5. So only the syntax below works.

| Syntax | Example | Description |
|---|---|---|
| Single keyword | `환불수수료` | Chunks containing that token |
| Space-separated | `Transactional Composite` | Contains both tokens (AND) |
| AND | `Transactional AND Composite` | Contains both tokens |
| OR | `Payment OR Shipping` | Contains at least one |
| NOT | `환불 NOT Coupon` | Exclusion condition |
| prefix | `Refund*` | Tokens that start with Refund |

Syntax that does not work: column specifiers (`doc_tags:orders`, `tags:orders` — no results; use the `--category` and `--topic` filters instead, and `--tags` to look at tags only), phrase search (`"REST Docs"` — the quotes are stripped and it becomes an AND of two tokens), and `NEAR`. The `doc_tags:` and `content:` column names in older documents are columns of the legacy index (the current columns are heading, text, title and tags).

## Frontmatter extension — the page_order field

Add an ordering field to the frontmatter of the existing document-format.md:

```yaml
---
title: "Order Payment & Shipping"
type: concept        # domain is a category (directory), not a document type
project: shop-api
tags: [orders, payment, shipping]
created: 2026-04-07
updated: 2026-04-07
page_order: 3              # ★ new — document order within a section
---
```

`--toc` sorts by the taxonomy's category and topic order first, and by `page_order` within that (pre-taxonomy NN-prefix directory documents use `section_order`).
`page_order` is stated explicitly in the frontmatter to define the logical order within a section.

## Token savings (measured)

The figures below were measured on a backend project's vault in the legacy FTS5 index era (2026-04) (15 documents, 210 chunks, 68K chars). The principle of reading by chunk is the same in the current store, but the figures have never been re-measured with the current engine.

| Search query | Before (read everything) | FTS5 (chunk) | Savings |
|-----------|-----------------|-------------|--------|
| "환불수수료" | 68,242 chars | 3,473 chars | **95%** |
| "TransactionalExecutor" | 68,242 chars | 1,181 chars | **99%** |
| "정산식 AND Payment" | 13,939 chars (3 files) | 6,758 chars | **52%** |

## Vector search (bge-m3 hybrid)

Canonical source: the search section of `core/docs/en/kb-engine.md`, DEC-2026-10-28-09.

### Summary

| Item | Current |
|---|---|
| Model | BAAI/bge-m3, run locally (sentence-transformers; MPS on Apple Silicon), 1024-dimensional normalized vectors |
| Storage | `chunks.embedding` in the store + the `embeddings(model, text_hash, dim, vector)` cache that survives rebuilds |
| Vector search | numpy cosine brute force (a few ms at about 7,000 chunks — no ANN needed) |
| Hybrid | RRF (k=60) fusion of FTS (bm25) and vectors |
| Judging effectiveness | `python3 "$STRATA_KIT/kb" search-eval` — recall@k (fts · dense · hybrid) over the query set in the vault's `_meta/search-eval.yaml` |
| Computing embeddings | `python3 "$STRATA_KIT/kb" embed` (only missing chunks. `--model` · `--batch` · `--max-seq` · `--max N`) |

### Alternatives and why they were not adopted

| Alternative | Decision |
|---|---|
| sqlite-vec | Switch via an adapter once chunks exceed 100,000 (DEC-2026-10-28-09). Not needed now |
| External vector DBs such as LanceDB | Conflicts with the one-store contract (DEC-2026-10-28-04) and brings no gain at this scale — not adopted |
| khoj | An app with its own host, UI and DB — not adopted |
| paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions) | The model of the legacy design. Replaced by bge-m3 |
| ONNX Runtime · cloud embedding APIs | Not adopted. The embedder provider is replaceable (kb-engine.md), but the current implementation is only local bge-m3 |

The old `build-index --with-vectors`, `apsw` (for loading sqlite-vec) and the `chunks_vec` virtual table were a legacy design and do not exist.

## Search tool cheat sheet

### Build

```bash
# Everyday: not needed — the store is rebuilt automatically on search entry if it is stale

# Manual build of the store + generated views (node pages · sortspec · review Inbox · manifest)
python3 "$STRATA_KIT/kb" build-index

# Limit only the reporting scope to one project (the store is always whole)
python3 "$STRATA_KIT/kb" build-index --project shop-api

# Rebuild only the store / statistics
python3 "$STRATA_KIT/kb" build-store
python3 "$STRATA_KIT/kb" store-stats

# Compute embeddings for missing chunks (before semantic / hybrid search)
python3 "$STRATA_KIT/kb" embed

# Move review candidates to status: review-needed and build again
python3 "$STRATA_KIT/kb" build-index --apply-review
```

`--force` is a compatibility flag and has no effect (the store is rebuilt in full every time). There is no `--with-vectors`.

### Search (kb search)

> `kb search` below is shorthand for `python3 "$STRATA_KIT/kb" search`.

```bash
# ─── FTS5 keyword search ───
kb search "환불수수료"                          # single keyword
kb search "Transactional AND Composite"       # AND compound
kb search "Payment OR Shipping"                  # OR
kb search "Refund*"                         # prefix
kb search "정산식" --category domain --topic orders   # category and topic filters (instead of column-specifier syntax)
kb search "환불수수료" --limit 10 --content      # number of results + content preview
kb search "jwt" --category architecture       # category filter (--topic, --status and --project also exist)
kb search "환불수수료" --include-history         # include session, task and planning text, plus decisions and orders

# ─── Semantic / hybrid search (after building vectors with kb embed) ───
kb search "환불 금액을 계산하는 흐름?" --semantic
kb search "인증 토큰 만료 시 처리" --hybrid --content

# ─── Navigation ───
kb search --toc                               # whole table of contents (ordered)
kb search --toc --category domain             # category filter
kb search --doc "domain/orders/payment-shipping.md"       # chunk table of contents within a document
kb search --tags orders                          # tag search (tags only, no query term)
kb search --stats                             # index statistics
```

`--section` is a compatibility filter for the pre-taxonomy NN-section directories. For new documents, use `--category` and `--topic`.

### FTS5 vs semantic — when to use which

| Situation | Recommended | Reason |
|------|------|------|
| You know the exact class or function name | FTS5 | `FormulaBaseStructure` → exact match, instant |
| Searching a specific term | FTS5 | `환불수수료`, `TransactionalExecutor` → BM25 rank |
| Natural-language question | **Semantic / hybrid** | "환불 금액을 계산하는 흐름?" → overcomes keyword mismatch |
| FTS5 returns nothing | **Semantic** | "인증 토큰 만료 처리" → 0 hits in FTS5, semantic returns results |
| After narrowing scope by category/topic | FTS5 | `--category domain --topic orders` filter |
| You do not know where to start reading | `--toc` | Ordered table of contents → grasp the document structure |

## FTS5 keyword splitting guide

The `unicode61` tokenizer of FTS5 **splits tokens only on whitespace and punctuation**.
It performs no Korean morphological analysis, so the strategy for splitting keywords matters when searching.

### Problem: why keyword splitting is needed

```
Original text:  "환불수수료 변경 시 재계산 처리"
              ↓ unicode61 tokenizing
Tokens:       ["환불수수료", "변경", "시", "재계산", "처리"]
```

| Search query | Match | Reason |
|-----------|----------|------|
| `환불수수료` | ✅ | Exact token match |
| `환불수수료변경` | ❌ | No token "환불수수료변경" exists |
| `환불수수료 AND 변경` | ✅ | Both tokens exist |
| `환불` | ❌ | A substring of "환불수수료" does not match |
| `환불*` | ✅ | Prefix search matches "환불수수료" |

### Splitting rules

**1. Split compound Korean terms with spaces and search with AND**

```bash
# ❌ Joined together: no match
kb search "환불수수료변경"

# ✅ Split + AND
kb search "환불수수료 AND 변경"
```

**2. Use prefix (*) when you need partial matching**

```bash
# ❌ "환불" alone cannot find "환불수수료"
kb search "환불"

# ✅ The prefix matches "환불수수료", "환불금액" and "환불요청"
kb search "환불*"
```

**3. English class names are case-insensitive, with no CamelCase splitting**

```bash
# ✅ unicode61 normalizes case
kb search "formulabasestructure"      # matches FormulaBaseStructure

# ❌ Splitting inside CamelCase does not work
kb search "Formula AND Base"          # both words must exist separately

# ✅ Work around it with a prefix
kb search "Formula*"
```

**4. Mixed Korean and English queries**

```bash
# ✅ Join the tokens of each language with AND
kb search "Payment AND 정산식"

# ✅ Combine category and topic filters with content search
kb search "Payment" --category domain --topic orders
```

**5. If keyword splitting still fails → switch to semantic / hybrid search**

```bash
# Natural-language query that is hard to find with FTS5
kb search "인증 토큰이 만료되면 어떻게 처리하나요?" --hybrid
```

The range FTS misses because of Korean particles and compound words (4-8% on the evaluation set) is left to vectors, and it was decided to reinforce it after evaluation with an FTS5 trigram table or bge-m3 sparse (DEC-2026-10-28-09).

### Agent search decision tree

```
Question received
  │
  ├─ Do you know the exact term/class name?
  │   └─ YES → FTS5: kb search "term"
  │
  ├─ Compound Korean term?
  │   └─ YES → FTS5: split on spaces + AND
  │            e.g. "환불수수료 AND 변경 AND 재계산"
  │
  ├─ Partial matching needed?
  │   └─ YES → FTS5: prefix(*)
  │            e.g. "Refund*", "환불*"
  │
  ├─ Natural-language question?
  │   └─ YES → hybrid/semantic: kb search "question" --hybrid
  │
  └─ FTS5 returned 0 results?
      └─ Retry with semantic
```

## Key design decisions

| Decision | Rationale |
|------|------|
| A single `store.sqlite` is the only index and is not put in git | Removes binary merge conflicts, and the duplicated schema and freshness guards that two indexes produced (DEC-2026-10-28-13) |
| Freshness is a source mtime comparison, and the store is rebuilt in full every time | At 1-2 s incremental is unnecessary. A partial build that cuts the store would lose other projects' views (DEC-2026-10-28-13) |
| `manifest.json` is not tracked | A per-machine comparison record that nobody reads (DEC-2026-10-29-04) |
| The build engine lives in the strata-kit repository | Managed as a tool of the methodology itself, independent of any project |
| Frontmatter is the single source of truth | Obsidian, FTS5 and Dataview all refer to the same data |
| Chunks carry heading, title, tags and meta together | One FTS table and one bm25 scale rank documents, decisions and orders, and output the location (DEC-2026-10-28-08) |
| bge-m3 embeddings + numpy brute force + RRF with FTS | Strong on mixed Korean and English, and its 8192 tokens mean long chunks are not truncated. No ANN needed at this scale (DEC-2026-10-28-09) |
| The effect of vectors is judged by recall@k on an evaluation set | `kb search-eval` |

Retired legacy decisions: git-tracking manifest.json and `.gitignore` for kb.sqlite, SHA256-hash-based incremental builds, `paraphrase-multilingual-MiniLM-L12-v2`, `apsw` and sqlite-vec, and the cosine distance 0-1 interpretation (for MiniLM). All disappeared together with the legacy index through DEC-2026-10-28-13 or were replaced by DEC-2026-10-28-09.

## Dependency summary

| Package | Purpose | When needed |
|--------|------|-----------|
| Python 3 | Running `kb` | Always |
| SQLite 3 (with FTS5) | store | Always (OS default) |
| PyYAML | Parsing frontmatter and taxonomy | Always |
| sentence-transformers (with PyTorch, ~500MB) | Computing bge-m3 embeddings | Only when using `kb embed` |
| numpy | Vector cosine | For semantic / hybrid search |

sqlite-vec and apsw are no longer used. FTS search and all generated views work without embeddings. The exact list of dependencies is based on the imports in `kb/`.

### Runtime environment

- No resident process. No GPU needed (on Apple Silicon, embeddings are fast with MPS).
- Store rebuild takes 1-2 s (about 760 documents and 7,000 chunks, measured in DEC-2026-10-28-13 and 09).
- Computing embeddings takes a long time the first time; afterwards only changed chunks are computed, thanks to the `embeddings` cache.

## Limitations

| Limitation | Description | Response |
|---|---|---|
| Korean morphology (FTS5) | unicode61 splits on whitespace only — "환불수수료변경" does not match | Follow the keyword splitting guide, use semantic search alongside |
| No CamelCase splitting (FTS5) | FormulaBaseStructure → a single token | Prefix (*) search or enter the whole name |
| No column specifier, phrase or NEAR support | All query tokens are wrapped in quotes, so FTS5 advanced syntax does not work | Use the `--category` and `--topic` filters and AND instead |
| Semantic search needs preparation | Vectors must be built first with `kb embed`, and the first query is slow because of model loading | FTS5 first, semantic as fallback |
| BM25 rank only (FTS) | No weighting by document structure or importance | Order the table of contents with page_order, use hybrid alongside |
| When Obsidian is not running | Dataview queries are impossible | FTS5/semantic work independently of Obsidian |
