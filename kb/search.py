"""kb-search — the agent-facing search CLI, reading the store (strata/scripts/kb-search.py is a shuttle here).

Same commands, filters and output as the legacy script: FTS search, --toc, --tags, --doc, --stats.
--semantic (dense, bge-m3) and --hybrid (FTS + dense, RRF) use the store's cached embeddings (python3 -m kb embed).
--rerank (opt-in) rescores the first 30 candidates with the bge-reranker-v2-m3 cross-encoder (kb/rerank.py).
"""
from __future__ import annotations

import argparse
import json
import sys

from kb import api
from kb.store import SqliteStore, has_operators


def get_store(db: str | None = None) -> SqliteStore:
    from kb.gates.coverage import get_store as _get
    return _get(db)


def _short_path(file_path: str) -> str:
    marker = "/knowledge-base/"
    idx = file_path.find(marker)
    if idx != -1:
        return file_path[idx + len(marker):]
    idx2 = file_path.find("projects/")
    if idx2 != -1:
        return file_path[idx2:]
    return file_path


def _project_name(file_path: str) -> str:
    parts = file_path.split("/")
    try:
        idx = parts.index("projects")
        return parts[idx + 1] if idx + 1 < len(parts) else ""
    except ValueError:
        return ""


def _passes(n, args) -> bool:
    p = n.payload
    if getattr(args, "category", None) and p.get("category") != args.category:
        return False
    if getattr(args, "topic", None) and p.get("topic") != args.topic:
        return False
    if getattr(args, "status", None) and n.status != args.status:
        return False
    if getattr(args, "project", None) and not n.path.startswith(f"projects/{args.project}/"):
        return False
    if getattr(args, "section", None) and not getattr(args, "category", None) and args.section not in p.get("section_name", ""):
        return False
    return True


def _vector_rows(store: SqliteStore, args, mode: str) -> list[dict]:
    """Dense or hybrid hits shaped like api.fts_rows rows (node · seq · heading · content · meta · rank)."""
    from kb.embed import Embedder
    model = store.embedding_model() or "BAAI/bge-m3"
    qvec = Embedder(model).encode_query(store.query_aliases().dense_text(args.query))
    pool = max(args.limit * 6, 30)
    ko = not getattr(args, "include_history", False) and not getattr(args, "category", None)
    hits = (store.search_vector(qvec, limit=pool, knowledge_only=ko) if mode == "semantic"
            else store.search_hybrid(args.query, qvec, limit=pool, knowledge_only=ko))
    rows = []
    for h in hits:
        if h.node.id.startswith("doc:") and not h.node.payload.get("indexed"):
            continue
        c = store.chunk(h.node.id, h.seq)
        if c is None:
            continue
        rows.append({"node": h.node, "seq": h.seq, "heading": c.heading, "content": c.text, "meta": c.meta, "rank": h.rank})
    return rows


def cmd_search(store: SqliteStore, args) -> None:
    mode = "hybrid" if getattr(args, "hybrid", False) else ("semantic" if getattr(args, "semantic", False) else "fts")
    rows = []
    note = ""
    try:
        source = api.fts_rows(store, args.query) if mode == "fts" else _vector_rows(store, args, mode)
    except ImportError as e:   # embeddings are optional (DEC-2026-10-29-20): no sentence-transformers/torch here → fts
        note = f"fts (embedding model unavailable: {e.name or e})"
        mode, source = "fts", api.fts_rows(store, args.query)
    include_history = getattr(args, "include_history", False)
    want_rerank = bool(getattr(args, "rerank", False))
    if want_rerank:
        from kb import rerank as rr
        pool = max(args.limit, rr.TOP_N)
    else:
        pool = args.limit

    def collect(src, with_history: bool):
        got, seen_records = [], set()
        for r in src:
            n = r["node"]
            if not _passes(n, args):
                continue
            if not api._in_scope(n, with_history, getattr(args, "category", None)):
                continue
            if api.role_of(n) != "knowledge":       # one line per session · decision · order, not per chunk
                if n.id in seen_records:
                    continue
                seen_records.add(n.id)
            got.append(r)
            if len(got) >= pool:
                break
        return got

    rows = collect(source, include_history)
    if mode == "fts" and not rows and len(args.query.split()) > 1 and not has_operators(args.query):
        source = api.fts_rows(store, args.query, any_terms=True)   # no chunk has every word → rank by any word
        rows = collect(source, include_history)
        note = " (모든 단어가 함께 있는 청크 없음 — 일부 단어 일치로 순위)"
    if not rows and not include_history and not getattr(args, "category", None):
        rows = collect(source, True)                                  # only history/records have it → show them with their documents
        if rows:
            note = " (지식 문서에는 없음 — 세션·결정 적중과 그 연결 문서)"
            include_history = True
    args.include_history = include_history
    if want_rerank and rows:
        try:
            rows, _ = rr.rerank(args.query, rows, lambda r: rr.chunk_text(r["heading"], r["content"]),
                                scorer=getattr(args, "_scorer", None))
            mode = f"{mode}+rerank"
        except rr.RerankUnavailable as e:
            note += f" (재순위 생략 — {e})"
    rows = rows[:args.limit]
    if not rows:
        print(f"검색 결과 없음: {args.query}")
        return
    filters = []
    if getattr(args, "category", None):
        filters.append(f"category={args.category}")
    if getattr(args, "topic", None):
        filters.append(f"topic={args.topic}")
    if getattr(args, "status", None):
        filters.append(f"status={args.status}")
    filter_str = f" ({', '.join(filters)})" if filters else ""
    mode_str = "" if mode == "fts" else f" [{mode}]"   # e.g. [hybrid+rerank]
    print(f'검색: "{args.query}"{filter_str}{mode_str} → {len(rows)}건{note}\n')
    for i, r in enumerate(rows):
        n, m = r["node"], r["meta"]
        short = _short_path(n.path)
        proj = _project_name(n.path)
        cat, topic, status = n.payload.get("category"), n.payload.get("topic"), n.status
        cat_info = ""
        if cat:
            cat_info = f"  [{cat}"
            if topic:
                cat_info += f"/{topic}"
            cat_info += "]"
            if status and status != "active":
                cat_info += f" ({status})"
        role = api.role_of(n)
        badge = f" 〔{api.role_label(n)}〕" if (role != "knowledge" or getattr(args, "include_history", False)) else ""
        print(f'[{i + 1}] {short} → "{r["heading"]}"{cat_info}{badge}')
        print(f"    문서: {n.title}")
        if proj:
            print(f"    프로젝트: {proj}")
        if m.get("line_start") is not None:
            print(f"    위치: L{m.get('line_start')}-{m.get('line_end')} ({m.get('char_count')} chars)")
        for lt in api.leads_to(store, n)[:6]:
            via = {"kb_updates": "갱신한 문서", "topic": "주제의 최종형상", "decision": "결정", "order": "오더", "mirror": "결정 노트"}.get(lt["via"], lt["via"])
            print(f"    → {via}: {_short_path(lt['path'])} — {lt['title'][:60]}")
        if args.content:
            content = r["content"]
            preview = content[:200].replace("\n", " ")
            if len(content) > 200:
                preview += "..."
            print(f"    내용: {preview}")
        print()


def _tag_str(tags) -> str:
    return f"  [{', '.join(str(t) for t in tags)}]" if tags else ""


def cmd_toc(store: SqliteStore, args) -> None:
    docs = api.documents(store)
    rows = [n for n in docs if n.payload.get("category") and _passes(n, args)]
    rows.sort(key=lambda n: (n.payload.get("category_order", 99), n.payload.get("topic_order", 99), n.payload.get("page_order", 99)))
    legacy_rows = []
    if not getattr(args, "category", None) and not getattr(args, "topic", None):
        for n in docs:
            p = n.payload
            if p.get("category") or not p.get("section_name"):
                continue
            if getattr(args, "section", None) and args.section not in p.get("section_name", ""):
                continue
            if getattr(args, "project", None) and not n.path.startswith(f"projects/{args.project}/"):
                continue
            if getattr(args, "status", None) and n.status != args.status:
                continue
            legacy_rows.append(n)
        legacy_rows.sort(key=lambda n: (n.payload.get("section_order", 0), n.payload.get("page_order", 99)))
    if not rows and not legacy_rows:
        print("문서 없음")
        return
    current_cat = current_topic = ""
    for n in rows:
        p = n.payload
        cat, topic, subtopic = p.get("category"), p.get("topic"), p.get("subtopic")
        if cat != current_cat:
            current_cat, current_topic = cat, ""
            print(f"\n## {cat}")
        if topic and topic != current_topic:
            current_topic = topic
            label = f"{topic}" + (f"/{subtopic}" if subtopic else "")
            print(f"\n  ### {label}")
        status_str = f" ({n.status})" if n.status and n.status != "active" else ""
        print(f"    {p.get('page_order', 99)}. [{p.get('type', '')}] {n.title} — {_short_path(n.path)}{_tag_str(p.get('tags'))}{status_str}")
    if legacy_rows:
        if rows:
            print("\n## (legacy sections)")
        current_section = ""
        for n in legacy_rows:
            p = n.payload
            if p.get("section_name") != current_section:
                current_section = p.get("section_name")
                print(f"\n  ### {current_section}")
            print(f"    {p.get('page_order', 99)}. {n.title} — {_short_path(n.path)}{_tag_str(p.get('tags'))}")


def cmd_tags(store: SqliteStore, args) -> None:
    needle = f'"{args.tags}"'
    rows = [n for n in api.documents(store)
            if needle in json.dumps(n.payload.get("tags") or [], ensure_ascii=False) and _passes(n, args)]
    rows.sort(key=lambda n: (n.payload.get("category_order", 99), n.payload.get("topic_order", 99), n.payload.get("page_order", 99)))
    if not rows:
        print(f"태그 '{args.tags}' 결과 없음")
        return
    print(f'태그: "{args.tags}" → {len(rows)}건\n')
    for n in rows:
        p = n.payload
        extra = ""
        if p.get("category"):
            extra = f" [{p['category']}" + (f"/{p['topic']}" if p.get("topic") else "") + "]"
            if n.status and n.status != "active":
                extra += f" ({n.status})"
        print(f"  {_short_path(n.path)} — {n.title}{extra}")


def cmd_doc(store: SqliteStore, args) -> None:
    docs = [n for n in api.documents(store) if args.doc in n.path]
    if not docs:
        print(f"문서 없음: {args.doc}")
        return
    chunks = []
    for n in docs:
        chunks.extend(store.chunks_of(n.id))
    chunks.sort(key=lambda c: c.seq)
    n = docs[0]
    p = n.payload
    print(f"문서: {n.title}")
    if p.get("category"):
        loc = p["category"] + (f"/{p['topic']}" if p.get("topic") else "")
        print(f"분류: {loc}")
        if n.status:
            print(f"상태: {n.status}")
    else:
        print(f"섹션: {p.get('section_name', '')} (page_order: {p.get('page_order', 99)})")
    print(f"타입: {p.get('type', '')}")
    tags = p.get("tags") or []
    if tags:
        print(f"태그: {', '.join(str(t) for t in tags)}")
    print(f"청크: {len(chunks)}개\n")
    for c in chunks:
        level = int(c.meta.get("heading_level") or 0)
        indent = "  " * (level - 2) if level >= 2 else ""
        print(f"  {indent}{'#' * level} {c.heading}  (L{c.meta.get('line_start')}-{c.meta.get('line_end')}, {c.meta.get('char_count')}c)")


def cmd_stats(store: SqliteStore, args) -> None:
    s = api.get_stats(store)
    docs = api.documents(store)
    cat_stats = []
    seen = set()
    for n in sorted((d for d in docs if d.payload.get("category")), key=lambda d: d.payload.get("category_order", 99)):
        cat = n.payload["category"]
        if cat in seen:
            continue
        seen.add(cat)
        members = {d.id for d in docs if d.payload.get("category") == cat}
        chunk_cnt = store.conn.execute(
            f"SELECT COUNT(*) FROM chunks WHERE node_id IN ({','.join('?' * len(members))})", list(members)).fetchone()[0]
        cat_stats.append((cat, len(members), chunk_cnt))
    status_stats = sorted((k, v) for k, v in s["statuses"].items() if k)
    legacy_count = sum(1 for d in docs if not d.payload.get("category") and d.payload.get("section_name"))
    print("KB 색인 통계")
    print(f"  문서: {s['documents']}개")
    print(f"  청크: {s['chunks']}개")
    print(f"  총 문자: {s['total_chars']:,} (~{s['total_chars'] // 4:,} tokens)")
    print(f"  링크: {s['links']}개")
    if cat_stats:
        print("\n  카테고리별:")
        for cat, cnt, chunk_cnt in cat_stats:
            print(f"    {cat}: {cnt}개 문서, {chunk_cnt or 0}개 청크")
        if legacy_count:
            print(f"    (legacy): {legacy_count}개 문서")
    if status_stats:
        print("\n  상태별:")
        for status, cnt in status_stats:
            print(f"    {status}: {cnt}개")
    print("\n  벡터: 없음 (Phase 1만)")
    print(f"  DB: {store.path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kb-search", description="Strata KB 검색", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="""예시:
  kb-search.py "배출계수"                          # 키워드 검색
  kb-search.py "jwt" --category architecture       # 카테고리 필터
  kb-search.py --toc --category domain             # 도메인 목차
  kb-search.py --toc --category domain --topic orders # 토픽 목차
  kb-search.py --tags "domain/orders"              # 태그 검색
  kb-search.py --stats                             # 통계""")
    parser.add_argument("query", nargs="?", help="FTS5 검색 쿼리")
    mode = parser.add_argument_group("모드")
    mode.add_argument("--toc", action="store_true", help="정렬된 문서 목차")
    mode.add_argument("--tags", help="태그 기반 검색")
    mode.add_argument("--doc", help="특정 문서의 chunk 목차")
    mode.add_argument("--stats", action="store_true", help="색인 통계")
    mode.add_argument("--semantic", action="store_true", help="벡터(bge-m3) 유사도 검색 — 먼저 python3 -m kb embed")
    mode.add_argument("--hybrid", action="store_true", help="FTS + 벡터 RRF 융합 검색")
    mode.add_argument("--rerank", action="store_true", help="상위 30개 후보를 교차 인코더(bge-reranker-v2-m3)로 다시 순위 — 기본 끔, 질의당 약 1초 더")
    filt = parser.add_argument_group("필터")
    filt.add_argument("--category", help="카테고리 필터 (domain, architecture, guides, references)")
    filt.add_argument("--topic", help="토픽 필터 (--category 와 함께)")
    filt.add_argument("--section", help="섹션 필터 (legacy NN-section 호환)")
    filt.add_argument("--status", help="상태 필터 (active, draft, review-needed, ...)")
    filt.add_argument("--project", help="프로젝트 필터")
    filt.add_argument("--no-archive", action="store_true", dest="no_archive", help="(호환용 — 이제 기본 동작) Archive 결과 제외")
    filt.add_argument("--include-history", action="store_true", dest="include_history", help="세션·태스크·기획 원문과 결정·오더 레코드까지 검색 (기본: 지식 문서만). 이력 적중은 연결된 정본 문서를 함께 보인다")
    out = parser.add_argument_group("출력")
    out.add_argument("--limit", type=int, default=5, help="검색 결과 수 (기본: 5)")
    out.add_argument("--content", action="store_true", help="검색 결과에 내용 미리보기 포함")
    out.add_argument("--db", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if not (args.stats or args.toc or args.tags or args.doc or args.query):
        parser.print_help()
        return 0
    store = get_store(args.db)
    if args.query and (args.semantic or args.hybrid):
        from kb.store import VectorsUnavailable
        try:
            cmd_search(store, args)
        except VectorsUnavailable as e:
            print(f"벡터 없음: {e}", file=sys.stderr)
            return 1
        return 0
    if args.stats:
        cmd_stats(store, args)
    elif args.toc:
        cmd_toc(store, args)
    elif args.tags:
        cmd_tags(store, args)
    elif args.doc:
        cmd_doc(store, args)
    else:
        cmd_search(store, args)
    return 0
