"""knowledge-base MCP server — the strata-mcp tools, now inside the kit (DEC-2026-10-28-11).

Run:  uv run --directory $STRATA_KIT strata-kb-mcp        (stdio)
The Claude Code plugin's .mcp.json registers exactly that. STRATA_VAULT names the vault.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
from typing import Any

try:                                  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:                   # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from kb import api, taxonomy as tx
from kb.engine import build_store, default_project_dirs, ensure_fresh_store

mcp = FastMCP(
    "knowledge-base",
    instructions=("Strata Knowledge Base MCP 서버 (strata-kit kb). 프로젝트 KB 문서 검색·조회·store 재생성·taxonomy. "
                  "검색 mode: hybrid(기본, 사용자 결정 2026-10-28)·dense·fts. vault 경로는 STRATA_VAULT."),
)


def _vault() -> Path:
    v = os.environ.get("STRATA_VAULT")
    if not v:
        raise RuntimeError("STRATA_VAULT 환경변수가 설정되지 않았습니다.")
    p = Path(os.path.expanduser(v))
    if not p.is_dir():
        raise RuntimeError(f"STRATA_VAULT 경로가 존재하지 않습니다: {p}")
    return p


def _store():
    return ensure_fresh_store(vault=_vault())


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


@mcp.tool()
def search_docs(query: str, category: str | None = None, topic: str | None = None, status: str | None = None,
                project: str | None = None, limit: int = 10, include_content: bool = False,
                include_history: bool = False, mode: str = "hybrid", context: str = "neighbors",
                context_chars: int = 1200, rerank: bool = False) -> str:
    """KB 문서를 검색합니다. mode=hybrid(기본 — FTS 와 bge-m3 벡터의 RRF 융합, 표현이 다른 질문에 유리; store 에 임베딩이
    없으면 fts 로 대신하고 결과의 mode 에 적는다) · dense(벡터만) · fts(bm25; 모든 단어가 함께 없으면 일부 단어 일치로,
    지식 문서에 없으면 세션·결정 적중을 연결 문서와 함께).

    기본 범위는 지식 문서(knowledge-base·patterns·glossary·overview)다. include_history=True 면 세션·태스크·기획 원문과
    결정·오더 레코드까지 본다. 적중마다 role(knowledge·planning·session·task·order·decision)이 붙고, 지식 문서가 아닌
    적중에는 leads_to(그 세션이 갱신한 문서·결정·주제의 최종형상 문서)가 붙는다.

    include_content=True 면 적중마다 context 가 붙는다: 같은 문서에서 그 청크 주변의 청크(heading·text·seq).
    청크 하나는 절의 조각일 때가 많아, 앞뒤를 함께 보면 다시 read_document 를 부르지 않아도 된다.

    Args:
        query: 검색어 (FTS5 구문 지원: AND, OR, NOT, "phrase", prefix*)
        category: 카테고리 필터 (domain, architecture, guides, references)
        topic: 토픽 필터 (category 와 함께)
        status: 상태 필터 (active, draft, review-needed, …)
        project: 프로젝트명 필터
        limit: 결과 수 (기본 10)
        include_content: True 면 청크 본문 포함
        include_history: True 면 작업 이력과 레코드도 검색
        mode: fts · dense · hybrid
        context: neighbors(기본 — 바로 앞·뒤 청크) · section(적중을 품은 H2 절의 나머지 청크) · none
        context_chars: 적중 하나에 붙는 context 의 최대 글자 수(기본 1200). 가까운 청크부터, 적중에서 먼 쪽을 자른다
        rerank: True 면 상위 30개 후보를 교차 인코더(bge-reranker-v2-m3)로 다시 순위한다(기본 False). 재현율이 조금
            오르는 대신 질의당 약 1초가 더 들고, 첫 호출은 모델 적재로 3~4초 걸린다. 모델이 없으면 원래 순서 그대로
            두고 mode 에 'rerank skipped' 를 적는다
    """
    store = _store()
    try:
        return _dump(api.search(store, query, mode=mode, category=category, topic=topic, status=status, project=project,
                                limit=limit, include_content=include_content, include_history=include_history,
                                context=context, context_chars=context_chars, rerank=rerank))
    finally:
        store.close()


@mcp.tool()
def get_doc(path: str) -> str:
    """KB 문서의 메타데이터, 청크 구조, 링크를 조회합니다. path 는 부분 매칭 (예: "domain/orders/concepts.md")."""
    store = _store()
    try:
        doc = api.get_document(store, path)
        if not doc:
            return _dump({"error": f"문서를 찾을 수 없습니다: {path}"})
        doc.pop("sha256", None)
        return _dump(doc)
    finally:
        store.close()


@mcp.tool()
def list_docs(category: str | None = None, topic: str | None = None, status: str | None = None,
              project: str | None = None) -> str:
    """KB 문서 목록을 taxonomy 정렬 순서로 반환합니다 (제목·타입·카테고리·토픽·상태)."""
    store = _store()
    try:
        return _dump(api.list_documents(store, category=category, topic=topic, status=status, project=project))
    finally:
        store.close()


@mcp.tool()
def get_stats(project: str | None = None) -> str:
    """KB 통계 — 문서·청크·문자·링크 수, 카테고리별·상태별 분포, store 노드·엣지·임베딩 적용률."""
    store = _store()
    try:
        stats = api.get_stats(store, project=project)
        counts = store.counts()
        with_vec, total = store.embedding_coverage()
        stats["store"] = {"nodes": counts["nodes"], "edges": counts["edges"], "chunks": counts["chunks"],
                          "embedded_chunks": with_vec, "embedding_model": store.embedding_model(),
                          "revision": (store.revision().store_rev if store.revision() else None)}
        return _dump(stats)
    finally:
        store.close()


@mcp.tool()
def get_taxonomy(project: str | None = None) -> str:
    """Taxonomy 분류 체계 — 카테고리 목록과 문서 타입 목록 (프로젝트 확장 포함)."""
    tax = tx.load_taxonomy(_vault(), project)
    if not tax:
        return _dump({"error": "taxonomy.yaml이 없습니다."})
    return _dump({"version": tax.get("version"), "categories": tx.category_info(tax), "document_types": tx.document_types(tax)})


@mcp.tool()
def build_index(project: str | None = None, force: bool = False) -> str:
    """KB 색인 빌드: store 를 다시 만들고(vault 스캐너·오더·결정 레코드 provider) 생성 뷰(노드 페이지·sortspec·리뷰 Inbox·manifest)를
    낸다. 조회는 낡으면 store 를 스스로 재생성하므로 보통 필요 없고, 생성 뷰까지 갱신하고 싶을 때 부른다.
    project 를 주면 보고 범위만 그 프로젝트로 좁힌다(store 는 항상 전체). exit_code 2 는 taxonomy block 위반."""
    from kb.build import build as build_index
    vault = _vault()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = build_index(vault, vault / ".kb" / "store.sqlite", project, None)
        return _dump({"success": rc == 0, "exit_code": rc, "output": buf.getvalue().strip(), "force": force})
    except Exception as e:  # noqa: BLE001
        return _dump({"success": False, "error": str(e), "output": buf.getvalue().strip()})


@mcp.tool()
def read_document(path: str) -> str:
    """KB 문서의 원본 마크다운(frontmatter 포함)을 읽습니다. path 는 부분 매칭."""
    vault = _vault()
    store = _store()
    try:
        doc = api.get_document(store, path)
        if not doc:
            return _dump({"error": f"문서를 찾을 수 없습니다: {path}"})
        fp = vault / doc["file_path"]
        if not fp.exists():
            return _dump({"error": f"파일이 디스크에 없습니다: {doc['file_path']}"})
        return _dump({"file_path": doc["file_path"], "title": doc["title"], "content": fp.read_text(encoding="utf-8")})
    finally:
        store.close()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
