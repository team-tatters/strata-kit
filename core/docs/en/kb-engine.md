# KB engine: storage contract

The knowledge base is a graph of documents, code surfaces, decisions, sessions and cards, held in one file-based store next to the vault. Everything in the store is generated from sources (rec.kb.generated-views); the store is a cache that can always be rebuilt.

## Why one store

Today the vault has an FTS5 index, node pages, decision-note mirrors, coverage mappings and link baselines, each produced by its own script and kept in its own file. The code-graph decision (strata DEC-2026-10-28-05) adds code symbols and impact edges. Embeddings add vectors. If each keeps its own file, the questions that matter (which document owns this changed function; which decision superseded the rule this session relied on; which sessions touched this node) need joins across tools. One store with one schema answers them in one query, and the backend can change without the schema changing.

## Schema

```text
nodes(id, kind, project, path, title, status, updated, revision, payload_json)
  kind ∈ {doc, code, decision, session, order, task, card, node, profile}
edges(src, dst, kind, confidence, source_ref, created)
  kind ∈ {covers, supersedes, kb_updates, orders, decisions_made, relay, calls, imports, tests, member_of, links, implementation}
  confidence ∈ {declared, extracted, inferred}
chunks(node_id, seq, heading, text, title, tags, locale, embedding?, meta_json)
  full-text and vector search units; heading·title·tags sit next to the text so the FTS index (unicode61, four columns) ranks like the legacy index; meta_json holds heading_level·line_start·line_end·char_count (part·own_chars too for a split section). A chunk is one H2–H4 section; only a section whose embedded input (title·heading·text) exceeds the encoder's 2,048-token window is cut, at paragraph, then line, then character boundaries, into pieces of about 1,500 tokens (heading repeated per piece, 150 characters of overlap, `kb/chunking.py`). Tokens are counted with the bge-m3 tokenizer from the local cache, otherwise with a conservative character estimate (chars × 0.75), which splits more sections, never fewer. Documents, decisions and orders share one FTS table and one bm25 scale; parity with the legacy index's ranking is not a goal (DEC-2026-10-28-08)
baselines(gate, project, key, recorded)                link and coverage baselines
revisions(store_rev, kit_rev, built_at, sources_hash)  provenance of the whole store
```

Declared edges come from frontmatter (covers, supersedes, orders, kb_updates, decisions_made) and from decision records. Extracted and inferred edges come from the graph provider (imports, calls, tests) and keep the provider's confidence label. Nothing in the store is authored by hand.

## Backends

| Backend | Role | Status |
|---|---|---|
| SQLite (FTS5 + sqlite-vec) | baseline: one file per vault, no server, embedded in the MCP process | current (FTS5), vec pending |
| DuckDB | analytics over the same tables (coverage reports, freshness, cross-project queries), parquet export for sharing | adapter pending |
| RocksDB | key-value for high-write session streams from an orchestrator (relay packets, approvals) before they are folded into nodes/edges | adapter pending |

All backends implement the same contract: `put_nodes`, `put_edges`, `query(sql-like)`, `search_text`, `search_vector`, `rebuild(sources)`. The engine never depends on a backend-specific feature outside its adapter.

## Providers

| Provider | Produces | Contract |
|---|---|---|
| vault scanner | doc nodes (every markdown file; indexed ones get chunks, generated mirrors are flagged), declared edges, body `links` edges | frontmatter + taxonomy |
| decision records | decision nodes, supersedes edges | decision writer output |
| code graph — the kit's own provider (`kb/providers/code_graph.py`) | per repo: directory · file · type-symbol code nodes (git-tracked files only; Kotlin · Java · TS/JS · Python), `member_of` (extracted), `imports` (extracted; wildcard and package imports are inferred and point at the directory), `tests` (inferred). Resolves the vault's covers targets (`code:<p>:paths:<dir>/`, `code:<p>:symbols:<Name>`) | strata DEC-2026-10-28-05. `python3 -m kb code deps · impact · tests-for · symbol · owner-gate`; flow(request) stays with an optional external adapter |
| orchestrator stream (Quilt) | relay and approval edges between session nodes | rec.decision.orchestrator-decisions-flow-to-records |
| embedder (local or opt-in cloud) | chunk vectors | locale-aware; never required for the engine to work |

## Gates that read the store

- coverage gate: changed code nodes → covers edges → owning doc; a changed node with no owner and no doc_change declaration is a new violation (rec.kb.covers-owner).
- link gate: body wikilinks and markdown links are `links` edges (source_ref records how the target resolved: file · id · alias · none · md). Broken, id-only and alias-only links and knowledge documents pointing at superseded targets are violations beyond the baseline (rec.kb.link-currency). The baseline of record stays in `.kb/link-baseline.json`; the store's baselines table mirrors it. Non-markdown link targets and `--code-root` checks are confirmed on the filesystem and in git (DEC-2026-10-28-07).
- freshness: doc nodes whose covered code revision is newer than their updated field.
- search: one FTS table (bm25) over heading·text·title·tags; dense vectors from the embedder provider (BAAI/bge-m3, local) are cached in `embeddings(model, text_hash, dim, vector)` and attached to chunks, cosine by brute force (no ANN needed at this scale); hybrid = reciprocal-rank fusion of both. `python3 -m kb search-eval` measures recall@k against the vault's query set (DEC-2026-10-28-09). Cross-encoder rerank (BAAI/bge-reranker-v2-m3, `kb/rerank.py`) is off by default; turn it on with `kb search --rerank`, MCP `search_docs(rerank=true)` or `api.search(rerank=True)`. It rescores the first 30 candidates against the query (up to 384 tokens per pair), reorders them and then cuts to the limit. Measured on the vault query set on 2026-11-05: hybrid recall@5/@10 went from .887/.897 to .917/.926, at a median +1.25 s per query, +1.1–2.2 GB GPU memory and a 3–4 s cold start. Without the model or sentence-transformers the order stays as it was and the result's mode says the rerank was skipped. `search-eval --rerank` adds a hybrid+rerank mode to compare on the same query set.
- convergence: desired spec node vs as-built doc node for the same subject (rec.spec.desired-vs-as-built).

## Migration from strata/scripts

The engine landed in `strata-kit/kb/` with the shuttle approach (strata-kit DEC-2026-10-28-01 of this repo): each `strata/scripts/<name>.py` is a thin call into `strata-kit/kb`, hooks keep working, and the shuttles are removed when every caller points at the kit.

The first milestone, parity, passed; the next one retired the legacy FTS index (`.kb/kb.sqlite`, DEC-2026-10-28-13). The vault now holds one store.

- `python3 -m kb build-index` is the session-end build: it rebuilds the whole store, then derives node pages (`kb.views.node_pages`), Obsidian sortspecs, the review inbox (`.kb/review-candidates.json`, `_index/review-needed.md`), `manifest.json` and the taxonomy validation warnings (a block violation exits 2) from the store. `--project` narrows the report only; the store is always whole.
- The document rules (discovery, frontmatter, chunks, taxonomy merge, validation) live in one place, `kb/docrules.py`. The scanner puts `discovered` (the discovery set) and `diagnostics` (validation results) into each document node's payload, so the build reports warnings without an index.
- Freshness is `engine.ensure_fresh_store` (source mtimes). The old `kb_freshness.py` and the manifest-hash incremental build are gone.
- Evidence: on 2026-10-28 the original builder (strata@b4b0c86) and `kb build-index` produced the same node pages, sortspecs, review inbox, manifest files, warning lines and exit code on two copies of the real vault (760 documents, 66 node pages). The comparison scripts were removed once the legacy index was retired (order 2026.10.29-11).
