"""Search evaluation — recall@k of fts · dense · hybrid against a golden query set.

Query set (YAML, lives in the vault because it names vault documents):
  queries:
    - q: "협업자 초대 메일을 다시 보내는 API"
      expect: ["collaborator-management-api.md"]        # path substrings; any expected doc found counts
      note: "optional"
recall@k = |expected docs among the first k distinct documents| / |expected docs|, averaged over queries.
History documents (sessions·tasks·planning) are excluded like the default search.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from kb import api, vault_root
from kb.store import SqliteStore, VectorsUnavailable

HISTORY = ("archive", "planning")


def _docs_from_hits(store: SqliteStore, hits, k: int, include_history: bool, expand: bool = False) -> list[str]:
    """First k distinct documents; with expand, a history/record hit also contributes the documents it leads to
    (DEC-2026-10-28-10) — they count toward the same k."""
    from kb import api
    out: list[str] = []
    for h in hits:
        n = h.node if hasattr(h, "node") else h
        if n is None:
            continue
        if n.id.startswith("doc:") and not n.payload.get("indexed"):
            continue
        if not api._in_scope(n, include_history, None):
            continue
        paths = [n.path] if api.role_of(n) == "knowledge" else ([n.path] if not expand else [])
        if expand and api.role_of(n) != "knowledge":
            paths += [lt["path"] for lt in api.leads_to(store, n)]
        for p in paths:
            if p not in out:
                out.append(p)
            if len(out) >= k:
                return out
    return out


def run(store: SqliteStore, queries: list[dict], ks=(5, 10), modes=("fts", "fts-any", "dense", "hybrid"), embedder=None,
        include_history: bool = False, expand: bool = False) -> dict:
    pool = max(ks) * 6
    results = {m: {k: [] for k in ks} for m in modes}
    per_query = []
    for q in queries:
        text, expect = str(q["q"]), [str(e) for e in q.get("expect") or []]
        qvec = embedder.encode_query(text) if embedder is not None and ("dense" in modes or "hybrid" in modes) else None
        row = {"q": text}
        for mode in modes:
            try:
                if mode == "fts":
                    hits = [type("H", (), {"node": r["node"]}) for r in api.fts_rows(store, text)[:pool]]
                elif mode == "fts-any":
                    hits = [type("H", (), {"node": r["node"]}) for r in api.fts_rows(store, text, any_terms=True)[:pool]]
                elif mode == "dense":
                    hits = store.search_vector(qvec, limit=pool, knowledge_only=not include_history) if qvec is not None else []
                else:
                    hits = store.search_hybrid(text, qvec, limit=pool, knowledge_only=not include_history) if qvec is not None else []
            except VectorsUnavailable:
                hits = []
            for k in ks:
                docs = _docs_from_hits(store, hits, k, include_history, expand)
                found = [e for e in expect if any(e in d for d in docs)]
                recall = len(found) / len(expect) if expect else 0.0
                results[mode][k].append(recall)
                row[f"{mode}@{k}"] = recall
            row[f"{mode}_top"] = (_docs_from_hits(store, hits, 1, include_history, expand) or [""])[0]
        per_query.append(row)
    summary = {m: {k: (sum(v) / len(v) if v else 0.0) for k, v in ks_.items()} for m, ks_ in results.items()}
    return {"summary": summary, "per_query": per_query, "n": len(queries)}


def format_report(res: dict, ks=(5, 10)) -> str:
    L = [f"search-eval — {res['n']} queries", "  mode     " + "  ".join(f"recall@{k:<3}" for k in ks)]
    for m, kv in res["summary"].items():
        L.append(f"  {m:8s} " + "  ".join(f"{kv[k]:.2f}      " for k in ks))
    L.append("")
    L.append("  misses (recall@5 < 1 in any mode):")
    for row in res["per_query"]:
        if any(row.get(f"{m}@5", 1.0) < 1.0 for m in res["summary"]):
            L.append("   " + row["q"][:48].ljust(50) + "  " + "  ".join(f"{m}:{row.get(f'{m}@5', 0):.1f}" for m in res["summary"]))
    return "\n".join(L)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb search-eval")
    ap.add_argument("--queries", default=None, help="default $STRATA_VAULT/_meta/search-eval.yaml")
    ap.add_argument("--store", default=None)
    ap.add_argument("--vault", default=None)
    ap.add_argument("--model", default=None, help="embedding model (default: the store's)")
    ap.add_argument("--modes", default="fts,fts-any,dense,hybrid")
    ap.add_argument("--k", default="5,10")
    ap.add_argument("--include-history", action="store_true", help="세션·태스크·기획·결정·오더 적중도 결과로")
    ap.add_argument("--expand", action="store_true", help="이력·레코드 적중이 이끄는 정본 문서도 찾은 것으로 센다")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    vault = Path(args.vault) if args.vault else vault_root()
    qpath = Path(args.queries) if args.queries else vault / "_meta" / "search-eval.yaml"
    queries = (yaml.safe_load(qpath.read_text(encoding="utf-8")) or {}).get("queries") or []
    from kb.engine import ensure_fresh_store
    store = ensure_fresh_store(Path(args.store) if args.store else None, vault)
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    ks = tuple(int(k) for k in args.k.split(","))
    embedder = None
    if "dense" in modes or "hybrid" in modes:
        from kb.embed import Embedder
        embedder = Embedder(args.model or store.embedding_model() or "BAAI/bge-m3")
    res = run(store, queries, ks, modes, embedder, args.include_history, args.expand)
    if args.json:
        import json
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print(format_report(res, ks))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
