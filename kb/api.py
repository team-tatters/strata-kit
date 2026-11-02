"""Query API over the store for programmatic consumers (the knowledge-base MCP server, kb/mcp.py). The result shapes
are the MCP tools' contract (DEC-2026-10-28-08)."""
from __future__ import annotations

import json
from typing import Any

from kb.store import Node, SqliteStore, fts_query, has_operators

HISTORY_CATEGORIES = ("archive", "planning")


def short_path(file_path: str) -> str:
    if "knowledge-base/" in file_path:
        return file_path.split("knowledge-base/", 1)[1]
    if "projects/" in file_path:
        return file_path.split("projects/", 1)[1]
    return file_path


def project_name(file_path: str) -> str:
    if "projects/" in file_path:
        parts = file_path.split("projects/", 1)[1].split("/")
        return parts[0] if parts else ""
    return ""


def documents(store: SqliteStore) -> list[Node]:
    """Indexed documents in the legacy index's insertion order (doc_seq)."""
    out = []
    for kind in ("doc", "session", "task"):
        out.extend(n for n in store.query(kind=kind) if n.id.startswith("doc:") and n.payload.get("indexed"))
    return sorted(out, key=lambda n: n.payload.get("doc_seq", 1 << 30))


def role_of(n: Node) -> str:
    """knowledge · planning · session · task · order · decision — what kind of source a hit is."""
    if n.kind in ("decision", "order", "task", "session"):
        return n.kind
    cat = n.payload.get("category")
    if cat == "planning":
        return "planning"
    if cat == "archive":
        return "session" if "/sessions/" in n.path else "task"
    return "knowledge"


def role_label(n: Node) -> str:
    r = role_of(n)
    return {"knowledge": f"지식·{n.payload.get('type') or '?'}", "planning": "기획", "session": "세션", "task": "태스크",
            "order": "오더", "decision": "결정"}.get(r, r)


def leads_to(store: SqliteStore, n: Node) -> list[dict[str, str]]:
    """For a non-knowledge hit: the documents it leads to, flat and labeled (DEC-2026-10-28-10)."""
    if role_of(n) == "knowledge":
        return []
    out = []
    links = store.leads_to(n.id)
    for m in links["documents"]:
        out.append({"via": "kb_updates", "role": role_of(m), "path": m.path, "title": m.title})
    for m in links["state_docs"]:
        out.append({"via": "topic", "role": role_of(m), "path": m.path, "title": m.title})
    for m in links["decisions"]:
        out.append({"via": "decision", "role": "decision", "path": m.payload.get("mirror") or m.path, "title": f"{m.id.split(':')[-1]} {m.title}".strip()})
    for m in links["orders"]:
        out.append({"via": "order", "role": "order", "path": m.path, "title": m.title})
    for m in links["mirror"]:
        out.append({"via": "mirror", "role": "decision", "path": m.path, "title": m.title})
    return out


def _match(n: Node, *, category=None, topic=None, status=None, project=None) -> bool:
    p = n.payload
    if category and p.get("category") != category:
        return False
    if topic and p.get("topic") != topic:
        return False
    if status and n.status != status:
        return False
    if project and not n.path.startswith(f"projects/{project}/"):
        return False
    return True


def fts_rows(store: SqliteStore, query: str, any_terms: bool = False) -> list[dict]:
    """All FTS matches ordered by bm25 rank (ties in rowid order), joined with their document node.
    any_terms=True: tokens joined with OR (for sentence-shaped questions)."""
    q = fts_query(query, any_terms) or '""'
    rows = store.conn.execute(
        "SELECT c.node_id, c.seq, c.heading, c.text, c.meta_json, bm25(chunks_fts) AS rank"
        " FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid WHERE chunks_fts MATCH ? ORDER BY rank, c.id", (q,)).fetchall()
    nodes: dict[str, Node] = {}
    out = []
    for r in rows:
        n = nodes.get(r["node_id"])
        if n is None:
            n = store.get(r["node_id"])
            nodes[r["node_id"]] = n
        if n is None or (n.id.startswith("doc:") and not n.payload.get("indexed")):
            continue
        out.append({"node": n, "seq": r["seq"], "heading": r["heading"], "content": r["text"],
                    "meta": json.loads(r["meta_json"] or "{}"), "rank": r["rank"]})
    return out


def search_fts(store: SqliteStore, query: str, *, category: str | None = None, topic: str | None = None,
               status: str | None = None, project: str | None = None, limit: int = 10,
               include_content: bool = False, include_history: bool = False, any_terms: bool = False) -> list[dict[str, Any]]:
    results, seen_records = [], set()
    for r in fts_rows(store, query, any_terms):
        n = r["node"]
        if not _in_scope(n, include_history, category):
            continue
        if not _match(n, category=category, topic=topic, status=status, project=project):
            continue
        if role_of(n) != "knowledge":          # one entry per session · decision · order · task, not per chunk
            if n.id in seen_records:
                continue
            seen_records.add(n.id)
        results.append(_entry(store, n, r["heading"], r["rank"], r["content"] if include_content else None))
        if len(results) >= limit:
            break
    return results


def _in_scope(n: Node, include_history: bool, category: str | None) -> bool:
    """Default scope is knowledge documents (+ an explicit category); include_history adds sessions · tasks ·
    planning and the decision · order · task records."""
    if n.kind in ("decision", "order", "task") and not n.id.startswith("doc:"):
        return bool(include_history)
    if not include_history and not category and n.payload.get("category") in HISTORY_CATEGORIES:
        return n.payload.get("category") == "planning" and n.payload.get("planning_layer") == "refined"   # DEC-2026-11-01-04
    return True


def _entry(store: SqliteStore, n: Node, heading: str, rank: float, content: str | None, mode: str | None = None) -> dict[str, Any]:
    e = {"file_path": n.path, "short_path": short_path(n.path), "title": n.title, "type": n.payload.get("type", ""),
         "tags": list(n.payload.get("tags") or []), "heading": heading, "rank": round(rank, 4), "role": role_of(n)}
    if mode:
        e["mode"] = mode
    if content is not None:
        e["content"] = content
    lt = leads_to(store, n)
    if lt:
        e["leads_to"] = lt
    return e


_embedders: dict[str, Any] = {}


def _embedder(store: SqliteStore):
    """One loaded model per process (the MCP server is long-lived; loading bge-m3 takes seconds)."""
    from kb.embed import Embedder
    name = store.embedding_model() or "BAAI/bge-m3"
    if name not in _embedders:
        _embedders[name] = Embedder(name)
    return _embedders[name]


def search(store: SqliteStore, query: str, *, mode: str = "fts", category: str | None = None, topic: str | None = None,
           status: str | None = None, project: str | None = None, limit: int = 10, include_content: bool = False,
           include_history: bool = False) -> list[dict[str, Any]]:
    """mode: fts (bm25) · dense (bge-m3 cosine) · hybrid (RRF of both). Same result shape as search_fts plus
    'mode'; dense/hybrid fall back to fts when the store has no embeddings yet."""
    if mode == "fts":
        kw = dict(category=category, topic=topic, status=status, project=project, limit=limit, include_content=include_content)
        out = search_fts(store, query, include_history=include_history, **kw)
        note = None
        if not out and len(query.split()) > 1 and not has_operators(query):
            out = search_fts(store, query, include_history=include_history, any_terms=True, **kw)
            note = "fts-any (no chunk had every word)"
        if not out and not include_history and not category:
            # the term may live only in sessions · decisions · orders: show those hits with the documents they lead to
            out = search_fts(store, query, include_history=True, any_terms=len(query.split()) > 1 and not has_operators(query), **kw)
            note = "fts+history (nothing in knowledge documents — history hits with the documents they lead to)"
        for e in out if note else []:
            e["mode"] = note
        return out
    from kb.store import VectorsUnavailable
    pool = max(limit * 6, 30)
    knowledge_only = not include_history and not category

    def fallback(reason: str):
        out = search(store, query, mode="fts", category=category, topic=topic, status=status, project=project, limit=limit,
                     include_content=include_content, include_history=include_history)
        for e in out:
            e["mode"] = f"fts ({reason})"
        return out

    if store.embedding_coverage()[0] == 0:
        return fallback("no embeddings yet — run: python3 -m kb embed")
    try:
        qvec = _embedder(store).encode_query(query)
    except ImportError as e:                      # sentence-transformers/torch not installed in this environment
        return fallback(f"embedding model unavailable: {e.name or e}")
    try:
        hits = (store.search_vector(qvec, limit=pool, knowledge_only=knowledge_only) if mode == "dense"
                else store.search_hybrid(query, qvec, limit=pool, knowledge_only=knowledge_only))
    except VectorsUnavailable as e:
        return fallback(str(e))
    results, seen_records = [], set()
    for h in hits:
        n = h.node
        if n.id.startswith("doc:") and not n.payload.get("indexed"):
            continue
        if not _in_scope(n, include_history, category):
            continue
        if not _match(n, category=category, topic=topic, status=status, project=project):
            continue
        if role_of(n) != "knowledge":
            if n.id in seen_records:
                continue
            seen_records.add(n.id)
        c = store.chunk(n.id, h.seq)
        results.append(_entry(store, n, c.heading if c else "", h.rank, (c.text if c else "") if include_content else None, mode))
        if len(results) >= limit:
            break
    return results


def document_record(n: Node) -> dict[str, Any]:
    """The legacy `documents` row for a node (minus the autoincrement id)."""
    p = n.payload
    covers = p.get("covers") or {}
    return {"file_path": n.path, "title": n.title, "type": p.get("type", ""), "tags": list(p.get("tags") or []),
            "section_name": p.get("section_name", ""), "section_order": p.get("section_order", 0), "page_order": p.get("page_order", 99),
            "category": p.get("category", ""), "topic": p.get("topic", ""), "subtopic": p.get("subtopic", ""),
            "category_order": p.get("category_order", 99), "topic_order": p.get("topic_order", 99), "status": n.status,
            "sha256": n.revision, "created": p.get("created", ""), "updated": p.get("updated_fm", ""), "stable_id": p.get("stable_id", ""),
            "nodes": json.dumps(p.get("nodes") or [], ensure_ascii=False),
            "covers": json.dumps(covers, ensure_ascii=False) if covers else "", "doc_change": p.get("doc_change", "")}


def get_document(store: SqliteStore, path: str) -> dict[str, Any] | None:
    hits = [n for n in documents(store) if path in n.path]
    if not hits:
        return None
    n = hits[0]
    doc = document_record(n)
    doc["chunks"] = [{"heading": c.heading, "heading_level": c.meta.get("heading_level"), "char_count": c.meta.get("char_count"),
                      "chunk_order": c.seq} for c in store.chunks_of(n.id)]
    doc["links"] = [{"target_path": t, "link_text": None} for t in (n.payload.get("links_raw") or [])]
    return doc


def list_documents(store: SqliteStore, *, category: str | None = None, topic: str | None = None,
                   status: str | None = None, project: str | None = None) -> list[dict[str, Any]]:
    docs = [n for n in documents(store) if _match(n, category=category, topic=topic, status=status, project=project)]
    docs.sort(key=lambda n: (n.payload.get("category_order", 99), n.payload.get("topic_order", 99), n.payload.get("page_order", 99)))
    return [{"file_path": n.path, "short_path": short_path(n.path), "title": n.title, "type": n.payload.get("type", ""),
             "tags": list(n.payload.get("tags") or []), "category": n.payload.get("category", ""),
             "topic": n.payload.get("topic", ""), "status": n.status} for n in docs]


def get_stats(store: SqliteStore, project: str | None = None) -> dict[str, Any]:
    docs = [n for n in documents(store) if not project or n.path.startswith(f"projects/{project}/")]
    ids = {n.id for n in docs}
    rows = store.conn.execute("SELECT node_id, meta_json FROM chunks").fetchall()
    chunk_count, total_chars = 0, 0
    for r in rows:
        if r["node_id"] in ids:
            chunk_count += 1
            total_chars += int((json.loads(r["meta_json"] or "{}")).get("char_count") or 0)
    link_count = sum(len(n.payload.get("links_raw") or []) for n in docs)
    stats: dict[str, Any] = {"documents": len(docs), "chunks": chunk_count, "total_chars": total_chars,
                             "estimated_tokens": total_chars // 4, "links": link_count}
    cats: dict[str, int] = {}
    for n in sorted(docs, key=lambda n: n.payload.get("category_order", 99)):
        cats[n.payload.get("category", "")] = cats.get(n.payload.get("category", ""), 0) + 1
    stats["categories"] = cats
    statuses: dict[str, int] = {}
    for n in docs:
        statuses[n.status] = statuses.get(n.status, 0) + 1
    stats["statuses"] = statuses
    return stats
