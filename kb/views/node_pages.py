#!/usr/bin/env python3
"""
노드 페이지 생성기 — 주제 노드별 최종형상·정책·결정·기획·작업이력·부채 조인 페이지 (생성 전용, Index 계층)

정본: taxonomy `topic_nodes.page`, core/docs/ko/knowledge-base/document-format.md `node` 타입, core/docs/ko/methodology/context-protocol.md CB-5(노드당 8KB),
      core/docs/ko/environment/data-placement.md 노드 페이지 행(생성 시점: KB 색인 빌드·세션 종료 채널과 같은 실행).
입력:
  - projects/{n}/_meta/toc.yaml                 노드 트리 (없으면 그 프로젝트는 건너뜀)
  - .kb/store.sqlite                            문서 노드 payload(type·status·created·updated_fm·covers·doc_change·category·nodes)
  - projects/{n}/decisions/DEC-*.md             결정 미러 frontmatter (nodes, supersedes, status)
  - 세션·제약 문서의 frontmatter                 kb_updates / severity·rule (부채·정책 면에만 필요, 파일 직접 읽음)
출력:
  - projects/{n}/nodes/{node-id}.md            전량·멱등 재생성, 정본(toc) 없는 페이지 제거
  - projects/{n}/nodes/_index.md               노드 트리 목차 (type moc)

원칙: 아무것도 새로 쓰지 않는다 — 이미 있는 것을 한 화면에 모을 뿐이며, 구멍은 구멍으로 보이게 둔다.
      날짜는 절대값으로만 적어 매일 돌려도 내용이 같으면 파일을 다시 쓰지 않는다.

CLI: python3 -m kb gen-node-pages [--vault V] [--project P] [--db STORE] [--budget 8192] [--quiet]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:
    sys.stderr.write("⚠ Strata: PyYAML 이 없어 노드 페이지를 생성할 수 없습니다.\n")
    sys.exit(0)

from kb.store import SqliteStore

FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)
HEADER = ("> GENERATED — 편집 금지. 정본: `_meta/toc.yaml` + 각 문서 frontmatter(nodes·covers·doc_change) + `decisions/`. "
          "재생성: 노드 페이지 생성기 (KB 색인 빌드·세션 종료 채널이 호출).\n")
DEFAULT_SECTIONS = ["최종형상", "정책", "결정", "기획", "작업이력", "부채"]
STATE_TYPES = ("specification", "concept")
HISTORY_LIMIT = 5
PLANNING_LIMIT = 8
# 기획 문서 implementation.status → 배지·정렬 (DEC-2026-09-09-01). 순서 = 주의가 필요한 것부터
PLAN_BADGE = {"diverged": "기획과 다름", "partial": "일부 구현", "not-implemented": "미구현",
              "unreviewed": "미검토", "implemented": "구현됨", "superseded": "대체됨"}
PLAN_ORDER = {k: i for i, k in enumerate(PLAN_BADGE)}


# ---------------------------------------------------------------- 유틸

def read_fm(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    m = FM_RE.match(text)
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return fm if isinstance(fm, dict) else {}


def wl(value) -> str:
    """'[[x|y]]' / 'x' → 'x' (링크 대상 정규화)."""
    s = str(value).strip()
    m = re.match(r"^\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]$", s)
    return (m.group(1) if m else s.split("#", 1)[0]).strip()


def stem(fp: str) -> str:
    return PurePosixPath(fp).stem


def body_sections(vault: Path) -> list[str]:
    from kb.legacy._kit import VAULT_TAXONOMY_TEMPLATE
    for cand in [vault / "_meta" / "taxonomy.yaml", VAULT_TAXONOMY_TEMPLATE]:
        if cand.is_file():
            try:
                tx = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            secs = ((tx.get("document_types") or {}).get("node") or {}).get("body_sections")
            if isinstance(secs, list) and len(secs) == 6:
                return [str(s) for s in secs]
            if isinstance(secs, list) and len(secs) == 5:      # 5면 taxonomy(기획 면 이전) — 기획 제목만 기본값으로 보충
                return [str(s) for s in secs[:3]] + [DEFAULT_SECTIONS[3]] + [str(s) for s in secs[3:]]
    return DEFAULT_SECTIONS


# ---------------------------------------------------------------- toc

class Node:
    def __init__(self, nid: str, label: str, labels: list[str], order, spec: dict, depth: int):
        self.id, self.label, self.labels, self.order, self.depth = nid, label, labels, order, depth
        self.summary = str(spec.get("summary") or "").strip()
        self.aliases = [str(a) for a in (spec.get("aliases") or [])]
        self.status = str(spec.get("status") or "active")
        self.children: list[Node] = []


def load_toc(project_dir: Path) -> tuple[list[Node], dict[str, str]]:
    """(노드 목록(트리 순서), alias→id 매핑). toc 없으면 ([], {})."""
    path = project_dir / "_meta" / "toc.yaml"
    if not path.is_file():
        return [], {}
    try:
        toc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"  ⚠ toc.yaml 파싱 실패: {e}", file=sys.stderr)
        return [], {}
    nodes: list[Node] = []
    alias_map: dict[str, str] = {}

    def walk(tree: dict, prefix: str, labels: list[str], depth: int, parent: Node | None):
        items = []
        for key, spec in (tree or {}).items():
            spec = spec if isinstance(spec, dict) else {}
            items.append((spec.get("order", 99), str(key), spec))
        for order, key, spec in sorted(items, key=lambda x: (x[0], x[1])):
            nid = f"{prefix}.{key}" if prefix else key
            label = str(spec.get("label") or key)
            node = Node(nid, label, labels + [label], order, spec, depth)
            nodes.append(node)
            if parent:
                parent.children.append(node)
            alias_map[nid] = nid
            for a in node.aliases:
                alias_map.setdefault(a, nid)
            walk(spec.get("children") or {}, nid, labels + [label], depth + 1, node)

    walk(toc.get("nodes") or {}, "", [], 1, None)
    return nodes, alias_map


# ---------------------------------------------------------------- 데이터 수집

def project_docs(store: SqliteStore, project: str) -> list[dict]:
    """프로젝트의 색인 문서(legacy documents 테이블과 같은 집합: 스캐너가 발견했고 indexed 인 문서),
    legacy 와 같은 순서(created 내림차순, 경로 오름차순)."""
    docs = []
    for n in store.query(path_prefix=f"projects/{project}/"):
        if n.kind not in ("doc", "session", "task") or not n.payload.get("indexed"):
            continue
        pl = n.payload
        covers = pl.get("covers") if isinstance(pl.get("covers"), dict) else {}
        docs.append({
            "path": n.path, "stem": stem(n.path), "id": str(pl.get("stable_id") or ""),
            "title": n.title or stem(n.path), "type": str(pl.get("type") or ""), "status": n.status or "",
            "created": str(pl.get("created") or "")[:10], "updated": str(pl.get("updated_fm") or "")[:10],
            "covers": {k: v for k, v in covers.items() if isinstance(v, list)},
            "doc_change": str(pl.get("doc_change") or ""), "category": str(pl.get("category") or ""),
            "nodes": [str(x) for x in (pl.get("nodes") or [])],
        })
    docs.sort(key=lambda d: d["path"])
    docs.sort(key=lambda d: d["created"], reverse=True)
    return docs


def load_docs(store: SqliteStore, project: str, alias_map: dict[str, str]) -> dict[str, list[dict]]:
    """노드 id → 문서 목록. alias 로 적힌 nodes 도 정식 id 로 접는다."""
    by_node: dict[str, list[dict]] = {}
    for doc in project_docs(store, project):
        for raw in doc["nodes"]:
            nid = alias_map.get(raw)
            if nid:
                by_node.setdefault(nid, []).append(doc)
    return by_node


def load_decisions(project_dir: Path, alias_map: dict[str, str]) -> tuple[dict[str, list[dict]], set[str]]:
    """노드 id → DEC 노트 목록, 그리고 supersedes 로 대체된 DEC id 집합."""
    by_node: dict[str, list[dict]] = {}
    superseded: set[str] = set()
    for f in sorted((project_dir / "decisions").glob("DEC-*.md")):
        fm = read_fm(f)
        rec_id = next((a for a in fm.get("aliases") or [] if str(a).startswith("DEC-")), f.stem)
        sup = [wl(s) for s in (fm.get("supersedes") or [])]
        superseded.update(sup)
        title = str(fm.get("title") or f.stem)
        title = re.sub(rf"^{re.escape(str(rec_id))}\s*[—\-:]\s*", "", title)  # 노트 제목의 'DEC-… — ' 접두 제거
        dec = {
            "rec": str(rec_id), "stem": f.stem, "title": title,
            "status": str(fm.get("status") or ""), "created": str(fm.get("created") or "")[:10],
            "supersedes": sup,
        }
        for raw in fm.get("nodes") or []:
            nid = alias_map.get(str(raw))
            if nid:
                by_node.setdefault(nid, []).append(dec)
    for lst in by_node.values():
        lst.sort(key=lambda d: d["created"], reverse=True)
    return by_node, superseded


# ---------------------------------------------------------------- 렌더

def _kb_updates_of(vault: Path, doc: dict) -> set[str]:
    fm = read_fm(vault / doc["path"])
    return {wl(x) for x in (fm.get("kb_updates") or [])}


def _constraint_line(vault: Path, doc: dict) -> str:
    fm = read_fm(vault / doc["path"])
    sev = fm.get("severity") or "-"
    rule = str(fm.get("rule") or doc["title"]).strip()
    st = fm.get("status") or doc["status"] or "-"
    return f"- **{sev}** [[{doc['stem']}]] — {rule} ({st})"


def _planning_info(vault: Path, doc: dict) -> dict:
    """기획 문서의 구현 검토 요약 (frontmatter implementation) — 배지·정렬 키."""
    fm = read_fm(vault / doc["path"])
    impl = fm.get("implementation") if isinstance(fm.get("implementation"), dict) else {}
    st = str(impl.get("status") or "unreviewed")
    return {"status": st, "badge": PLAN_BADGE.get(st, st), "order": PLAN_ORDER.get(st, 99),
            "reviewed": str(impl.get("reviewed") or "")[:10], "spec": wl(impl.get("spec")) if impl.get("spec") else ""}


def render(vault: Path, project: str, node: Node, docs: list[dict], decs: list[dict], superseded: set[str],
           sections: list[str], budget: int, existing_created: str | None) -> str:
    state = [d for d in docs if d["type"] in STATE_TYPES]
    policy = [d for d in docs if d["type"] == "constraint"]
    history = [d for d in docs if d["category"] == "archive"]
    planning = [d for d in docs if d["type"] == "planning"]
    related = [d for d in docs if d not in state and d not in policy and d not in history and d not in planning
               and d["type"] not in ("node", "moc")]
    plan_info = {d["path"]: _planning_info(vault, d) for d in planning}
    planning.sort(key=lambda d: (plan_info[d["path"]]["order"], d["created"] or ""), reverse=False)

    fm = {
        "title": " › ".join(node.labels),
        "id": f"node-{project}-{node.id}",
        "type": "node",
        "project": project,
        "node": node.id,
        "status": "active" if node.status == "active" else "archived",
        "created": existing_created or date.today().isoformat(),
    }
    if node.aliases:
        fm["aliases"] = node.aliases

    def build(history_n: int, show_superseded: bool, show_related: bool, planning_n: int = PLANNING_LIMIT) -> str:
        L = ["---\n", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False), "---\n\n",
             f"# {' › '.join(node.labels)}\n\n", HEADER, "\n"]
        if node.status != "active":
            L.append("> **폐기된 노드** — toc.yaml 에서 retired. 이력 참조용으로만 남긴다.\n\n")
        if node.summary:
            L.append(f"{node.summary}\n\n")
        L.append(f"`node: {node.id}`\n\n")

        # 최종형상 — specification·concept 가 정본. 없으면 guide·runbook·reference 등 Knowledge 문서를 "정본 후보"로 보여 준다
        # (컨벤션·백오피스처럼 현행 형상이 guide 로만 존재하는 노드가 "(없음)"으로 보이지 않게 — 2026-09-08 검토)
        L.append(f"## {sections[0]}\n\n")
        if not state and not related:
            L.append("- (없음) — 이 노드의 정본 명세가 없다. specification 을 만들거나 기존 문서의 `nodes:` 에 이 노드를 추가한다.\n")
        for d in state:
            cov = " · ".join(f"{k} {len(v)}" for k, v in d["covers"].items()) or "covers 없음"
            flag = " ⚠ 리뷰 필요" if d["status"] == "review-needed" else ""
            L.append(f"- **[[{d['stem']}]]** ({d['type']}, {d['status'] or '-'}, updated {d['updated'] or d['created'] or '-'}) — {cov}{flag}\n")
        if related and not state:
            L.append("정본 명세(specification·concept) 없음 — 현행 형상을 담은 Knowledge 문서:\n")
            for d in related:
                flag = " ⚠ 리뷰 필요" if d["status"] == "review-needed" else ""
                L.append(f"- [[{d['stem']}]] ({d['type']}, {d['status'] or '-'}, updated {d['updated'] or d['created'] or '-'}){flag}\n")
        elif related and show_related:
            L.append("\n관련 문서: " + ", ".join(f"[[{d['stem']}]]" for d in related) + "\n")
        L.append("\n")

        # 정책
        L.append(f"## {sections[1]}\n\n")
        if not policy:
            L.append("- (없음) — 이 노드를 가리키는 Constraint Card 가 없다. registry 항목은 노드 미지원.\n")
        for d in policy:
            L.append(_constraint_line(vault, d) + "\n")
        L.append("\n")

        # 결정
        L.append(f"## {sections[2]}\n\n")
        current = [d for d in decs if d["rec"] not in superseded and d["status"] != "superseded"]
        old = [d for d in decs if d not in current]
        if not decs:
            L.append("- (없음) — 이 노드를 가리키는 결정이 없다. decision writer CLI 의 `--nodes` 로 연결한다.\n")
        for d in current:
            chain = f" ← supersedes {', '.join(f'[[{s}]]' for s in d['supersedes'])}" if d["supersedes"] else ""
            L.append(f"- **[[{d['stem']}]] (현행)** {d['created']} — {d['title']}{chain}\n")
        shown_old = old[:1] if show_superseded else []
        for d in shown_old:
            L.append(f"- [[{d['stem']}]] (대체됨) {d['created']} — {d['title']}\n")
        if len(old) > len(shown_old):
            L.append(f"- … 대체된 결정 {len(old) - len(shown_old)}건 더 (DEC 인덱스 참조)\n")
        L.append("\n")

        # 기획 — as-intended. 원문은 planning/ 에, 구현 검토 결과는 implementation.status 배지로 (DEC-2026-09-09-01)
        L.append(f"## {sections[3]}\n\n")
        if not planning:
            L.append("- (없음) — 이 노드를 가리키는 기획 문서가 없다.\n")
        for d in planning[:planning_n]:
            pi = plan_info[d["path"]]
            extra = [f"기획 {d['status'] or '-'}"]
            if pi["reviewed"]:
                extra.append(f"reviewed {pi['reviewed']}")
            if pi["spec"]:
                extra.append(f"spec [[{pi['spec']}]]")
            L.append(f"- **{pi['badge']}** [[{d['stem']}]] — {d['title']} ({', '.join(extra)})\n")
        if len(planning) > planning_n:
            L.append(f"- … {len(planning) - planning_n}건 더 (planning/)\n")
        L.append("\n")

        # 작업이력
        L.append(f"## {sections[4]}\n\n")
        if not history:
            L.append("- (없음) — 이 노드를 가리키는 세션·태스크가 없다.\n")
        for d in history[:history_n]:
            dc = d["doc_change"]
            mark = "형상 미갱신 선언(사유 있음)" if dc == "none" else ("형상 갱신" if dc == "updated" else "doc_change 선언 없음")
            L.append(f"- {d['created'] or '-'} [[{d['stem']}]] — {mark}\n")
        if len(history) > history_n:
            L.append(f"- … {len(history) - history_n}건 더 (sessions/·tasks/)\n")
        L.append("\n")

        # 부채
        L.append(f"## {sections[5]}\n\n")
        debts = []
        n_unrev = sum(1 for d in planning if plan_info[d["path"]]["status"] == "unreviewed")
        if n_unrev:
            debts.append(f"기획 문서 {n_unrev}건 구현 검토 전 (implementation.status unreviewed).")
        for d in planning:
            if plan_info[d["path"]]["status"] in ("diverged", "partial"):
                debts.append(f"[[{d['stem']}]] 기획과 구현이 다름({plan_info[d['path']]['badge']}) — 최종형상 반영·근거 기록 여부 확인.")
        state_dates = [d["updated"] or d["created"] for d in state if (d["updated"] or d["created"])]
        state_latest = max(state_dates) if state_dates else ""
        state_stems = {d["stem"] for d in state} | {d["id"] for d in state if d["id"]}
        if history and not state and not related:
            debts.append("최종형상 없음 — 작업이력은 있는데 정본 명세가 없다.")
        elif history and not state and related:
            debts.append("정본 명세(specification·concept) 없음 — guide·runbook 만 있다. 형상을 명세로 승격할지 판단 필요.")
        for d in state:
            if d["status"] == "review-needed":
                debts.append(f"[[{d['stem']}]] 리뷰 필요 (status review-needed).")
            if not d["covers"]:
                debts.append(f"[[{d['stem']}]] covers 없음 — 커버리지 게이트가 이 노드의 코드 변경을 감지하지 못한다.")
        for d in history:
            if not d["created"] or not state_latest or d["created"] <= state_latest:
                continue
            if d["doc_change"] == "none":
                continue
            touched = _kb_updates_of(vault, d) & state_stems
            if touched:
                debts.append(f"[[{d['stem']}]] ({d['created']}) 이 {', '.join(f'[[{t}]]' for t in sorted(touched))} 를 갱신했다고 적었으나 그 문서의 updated({state_latest})가 더 오래됨 — updated 스탬프 누락.")
            else:
                debts.append(f"[[{d['stem']}]] ({d['created']}) 이 노드를 다뤘으나 최종형상(updated {state_latest}) 미갱신, doc_change 선언 없음.")
        if not debts:
            L.append("- (없음)\n")
        for x in debts:
            L.append(f"- {x}\n")
        L.append("\n")
        return "".join(L).rstrip() + "\n"

    text = build(HISTORY_LIMIT, True, True)
    if len(text.encode("utf-8")) > budget:
        text = build(3, False, False, 3)
    if len(text.encode("utf-8")) > budget:
        text = build(0, False, False, 0)
        text = text.rstrip() + "\n\n> CB-5: 8KB 예산 초과로 작업이력·기획·대체 결정·관련 문서를 생략했다. 원문은 sessions/·planning/·decisions/ 참조.\n"
    return text


def render_index(project: str, nodes: list[Node], counts: dict[str, tuple[int, int, int, int, int, int]],
                 existing_created: str | None = None) -> str:
    L = ["---\n", f'title: "노드 목차 — {project}"\n', f"id: moc-{project}-nodes\n", "type: moc\n",
         f"project: {project}\n", "status: active\n", f"created: '{existing_created or date.today().isoformat()}'\n",
         "---\n\n", f"# 주제 노드 — {project}\n\n", HEADER, "\n",
         "| 노드 | 형상 | 정책 | 결정 | 기획 | 이력 | 부채 |\n|---|---:|---:|---:|---:|---:|---:|\n"]
    for n in nodes:
        s, p, d, pl, h, b = counts.get(n.id, (0, 0, 0, 0, 0, 0))
        indent = "　" * (n.depth - 1)
        retired = " (폐기)" if n.status != "active" else ""
        L.append(f"| {indent}[[{n.id}\\|{n.label}]]{retired} | {s} | {p} | {d} | {pl} | {h} | {b} |\n")
    if not nodes:
        L.append("| (노드 없음 — _meta/toc.yaml 을 작성한다) | | | | | | |\n")
    return "".join(L)


# ---------------------------------------------------------------- main

def generate(vault: Path, project: str, store: SqliteStore, sections: list[str], budget: int, quiet: bool) -> tuple[int, int, int]:
    project_dir = vault / "projects" / project
    nodes, alias_map = load_toc(project_dir)
    out_dir = project_dir / "nodes"
    if not nodes:
        if out_dir.exists():
            removed = 0
            for f in out_dir.glob("*.md"):
                f.unlink()
                removed += 1
            if removed and not quiet:
                print(f"  {project}: toc.yaml 없음 — 노드 페이지 {removed}건 제거")
        return 0, 0, 0
    out_dir.mkdir(exist_ok=True)
    docs_by_node = load_docs(store, project, alias_map)
    decs_by_node, superseded = load_decisions(project_dir, alias_map)

    written = unchanged = 0
    generated: set[str] = set()
    counts: dict[str, tuple[int, int, int, int, int, int]] = {}
    for node in nodes:
        docs = docs_by_node.get(node.id, [])
        decs = decs_by_node.get(node.id, [])
        target = out_dir / f"{node.id}.md"
        existing_created = read_fm(target).get("created") if target.exists() else None
        text = render(vault, project, node, docs, decs, superseded, sections, budget, str(existing_created) if existing_created else None)
        generated.add(target.name)
        debts = text.split(f"## {sections[5]}")[-1].count("\n- ") - (1 if "- (없음)" in text.split(f"## {sections[5]}")[-1] else 0)
        counts[node.id] = (
            sum(1 for d in docs if d["type"] in STATE_TYPES) or sum(1 for d in docs if d["category"] not in ("archive", "planning") and d["type"] not in ("constraint", "node", "moc")),
            sum(1 for d in docs if d["type"] == "constraint"),
            len(decs),
            sum(1 for d in docs if d["type"] == "planning"),
            sum(1 for d in docs if d["category"] == "archive"),
            max(debts, 0),
        )
        if target.exists() and target.read_text(encoding="utf-8") == text:
            unchanged += 1
            continue
        target.write_text(text, encoding="utf-8")
        written += 1

    idx = out_dir / "_index.md"
    idx_created = read_fm(idx).get("created") if idx.exists() else None
    idx_text = render_index(project, nodes, counts, str(idx_created) if idx_created else None)
    generated.add(idx.name)
    if not idx.exists() or idx.read_text(encoding="utf-8") != idx_text:
        idx.write_text(idx_text, encoding="utf-8")
        written += 1

    removed = 0
    for f in out_dir.glob("*.md"):
        if f.name not in generated:
            f.unlink()
            removed += 1
    if not quiet:
        print(f"  {project}: 노드 {len(nodes)}개 — 작성 {written} / 변경없음 {unchanged} / 제거 {removed}")
    return written, unchanged, removed


def generate_all(vault: Path, store: SqliteStore, project: str | None = None, budget: int = 8192,
                 quiet: bool = True) -> tuple[int, int, int, int]:
    """toc.yaml 이 있는(또는 nodes/ 가 남은) 모든 프로젝트의 노드 페이지를 다시 만든다.
    반환 (작성, 변경없음, 제거, 프로젝트 수). 색인 빌더가 빌드 끝에 호출한다."""
    sections = body_sections(vault)
    projects = [project] if project else sorted(
        p.name for p in (vault / "projects").iterdir()
        if p.is_dir() and ((p / "_meta" / "toc.yaml").is_file() or (p / "nodes").is_dir())
    )
    total = [0, 0, 0]
    for name in projects:
        w, u, r = generate(vault, name, store, sections, budget, quiet)
        total[0] += w; total[1] += u; total[2] += r
    return total[0], total[1], total[2], len(projects)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb gen-node-pages", description="Strata 노드 페이지 생성기 (생성 전용, store 입력)")
    ap.add_argument("--vault", default=os.environ.get("STRATA_VAULT"))
    ap.add_argument("--project", help="특정 프로젝트만 (기본: toc.yaml 이 있는 모든 프로젝트)")
    ap.add_argument("--db", help="store.sqlite 경로 (기본 $STRATA_VAULT/.kb/store.sqlite). 낡았으면 먼저 다시 만든다")
    ap.add_argument("--budget", type=int, default=8192, help="노드 페이지 바이트 예산 (CB-5)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    if not args.vault:
        print("STRATA_VAULT 필요", file=sys.stderr)
        return 2
    vault = Path(args.vault).resolve()
    if not (vault / "projects").is_dir():
        print(f"projects/ 없음 — vault 가 아님: {vault}", file=sys.stderr)
        return 0
    from kb.engine import ensure_fresh_store
    store = ensure_fresh_store(Path(args.db).resolve() if args.db else None, vault=vault)
    try:
        w, u, r, n = generate_all(vault, store, args.project, args.budget, args.quiet)
    finally:
        store.close()
    if not args.quiet or w or r:
        print(f"노드 페이지: 작성 {w} / 변경없음 {u} / 제거 {r} (프로젝트 {n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
