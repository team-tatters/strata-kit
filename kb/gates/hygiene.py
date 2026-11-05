"""hygiene — the vault hygiene report (order 2026.10.28-08, read-only).

Reads the store and lists what the hygiene pass has to decide on: the history status vocabulary (sessions · tasks)
against the taxonomy, projects whose documents name topic nodes but have no toc.yaml, state documents without covers,
and broken references (body links, frontmatter links, nodes, orders, decisions) plus the code targets that wait for
the code-graph provider. It changes nothing; the cleanup is a separate order after the user decides.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path, PurePosixPath

from kb import vault_root
from kb.engine import ensure_fresh_store
from kb.providers.vault_scanner import is_origin_immutable
from kb.store import Edge, Node, SqliteStore
from kb.taxonomy import load_taxonomy

HISTORY_KINDS = ("session", "task")
STATE_TYPES = ("specification", "concept")
# a draft canonical mapping for the history vocabulary — a proposal for the user, not applied anywhere
STATUS_PROPOSAL = {
    "open": "open", "active": "open", "planned": "open", "draft": "open",
    "in_progress": "in_progress", "in-progress": "in_progress",
    "awaiting_review": "awaiting", "awaiting_user": "awaiting", "blocked": "awaiting", "pending": "awaiting", "review": "awaiting",
    "handoff": "handed_off", "handoff_ready": "handed_off", "handed-off": "handed_off", "handed_off": "handed_off",
    "closed": "closed", "completed": "closed", "implemented": "closed", "done": "closed", "realized": "closed",
    "decided": "closed", "confirmed": "closed", "agreed": "closed", "accepted": "closed", "archived": "closed",
}
HISTORY_STATUSES = ("open", "in_progress", "awaiting", "handed_off", "closed")


def proposed_status(value: str) -> str | None:
    """The canonical history status for a raw frontmatter value, or None when nothing fits."""
    v = value.strip().strip("'\"").strip()
    if v in HISTORY_STATUSES:
        return v
    key = v.replace(" ", "_")
    if key in STATUS_PROPOSAL:
        return STATUS_PROPOSAL[key]
    head = re.split(r"[\s(]", v, maxsplit=1)[0]          # "handoff (context clear 직전)" → handoff
    return STATUS_PROPOSAL.get(head)


STATUS_LINE_RE = re.compile(r"^(status:)([ \t]*)([^#\n]*?)([ \t]*(#.*)?)$", re.M)
FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)


def rewrite_status(store: SqliteStore, vault: Path, project: str | None = None, apply: bool = False) -> dict:
    """Map every session·task document's status to the five-value vocabulary. Dry-run by default: returns the plan
    (file, old, new) and the values nothing maps to; --apply rewrites only the status line, keeping its quoting and comment."""
    plan, unmapped, same = [], [], 0
    taxonomy = load_taxonomy(vault, project)
    for n in store.query():
        if n.kind not in HISTORY_KINDS or not n.payload.get("discovered") or (project and n.project != project):
            continue
        doc_type = str(n.payload.get("type") or "")
        if doc_type not in HISTORY_KINDS and _has_override(taxonomy, doc_type):
            continue   # a planning document in a task folder keeps its own vocabulary
        path = vault / n.path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = FM_RE.match(text)
        if not m:
            continue
        sm = STATUS_LINE_RE.search(m.group(1))
        if not sm:
            continue
        raw = sm.group(3).strip()
        new = proposed_status(raw)
        if new is None:
            unmapped.append({"path": n.path, "status": raw})
            continue
        if raw.strip("'\"") == new:
            same += 1
            continue
        plan.append({"path": n.path, "old": raw, "new": new})
        if apply:
            quoted = raw.startswith('"') or raw.startswith("'")
            value = f'"{new}"' if quoted else new
            fm = m.group(1)[: sm.start()] + sm.group(1) + sm.group(2) + value + sm.group(4) + m.group(1)[sm.end():]
            path.write_text(text[: m.start(1)] + fm + text[m.end(1):], encoding="utf-8")
    return {"applied": apply, "rewritten": plan, "unmapped": unmapped, "already_canonical": same}


# ---------------------------------------------------------------- covers candidates

IDENT_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`|\b([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+)\b")


def covers_candidates(store: SqliteStore, vault: Path, repo_projects: set[str], project: str | None = None, min_symbols: int = 1) -> dict:
    """For state documents without covers in projects that have a code repo: symbols the body names that the code
    graph knows, and the directories those symbols live in. Written as an Inbox (pending) — nothing is applied."""
    nodes = {n.id: n for n in store.query()}
    out: dict[str, list[dict]] = defaultdict(list)
    for d in nodes.values():
        if d.kind != "doc" or not d.payload.get("discovered") or d.payload.get("type") not in STATE_TYPES or d.payload.get("covers"):
            continue
        if d.project not in repo_projects or (project and d.project != project):
            continue
        try:
            body = (vault / d.path).read_text(encoding="utf-8")
        except OSError:
            continue
        names = {a or b for a, b in IDENT_RE.findall(body)}
        names = {x.split(".")[-1] for x in names if x}
        symbols, dirs = [], Counter()
        for name in sorted(names):
            sym = nodes.get(f"code:{d.project}:symbols:{name}")
            if not sym:
                continue
            files = sym.payload.get("files") or []
            symbols.append({"symbol": name, "files": files[:3]})
            for f in files:
                dirs[str(PurePosixPath(f).parent) + "/"] += 1
        if len(symbols) < min_symbols:
            continue
        out[d.project].append({"doc": d.path, "title": d.title, "status": "pending",
                               "symbols": [s["symbol"] for s in symbols],
                               "paths": [p for p, _ in dirs.most_common(6)],
                               "evidence": symbols[:12]})
    return out


COVERS_BLOCK_RE = re.compile(r"^covers:.*\n(?:[ \t-].*\n?)*", re.M)


def _merge_covers(fm_text: str, add: dict) -> tuple[str, dict] | None:
    """Add the patterns of `add` that the frontmatter's covers lacks; the covers block is rewritten in place and
    other keys are untouched. None when every pattern is already there."""
    import yaml
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return None
    covers = fm.get("covers") if isinstance(fm.get("covers"), dict) else {}
    merged = {k: list(v) for k, v in covers.items()}
    added = {}
    for kind, vals in add.items():
        cur = merged.setdefault(kind, [])
        new = [v for v in vals if v not in cur]
        if new:
            cur.extend(new)
            added[kind] = len(new)
    if not added:
        return None
    block = yaml.safe_dump({"covers": {k: v for k, v in merged.items() if v}}, allow_unicode=True, sort_keys=False,
                           default_flow_style=None)
    body = fm_text.rstrip("\n") + "\n"
    if COVERS_BLOCK_RE.search(body):
        body = COVERS_BLOCK_RE.sub(lambda _m: block, body, count=1)
    else:
        body += block
    return body.rstrip("\n"), added


def apply_covers(vault: Path, project: str | None = None) -> list[dict]:
    """Write covers (paths · symbols) into the frontmatter of every candidate marked status: approved in
    projects/<p>/_meta/covers-candidates.yaml. Hygiene candidates skip documents that already have covers;
    impact candidates (source: impact, 오더 2026.10.28-11) add only the patterns the document's covers lacks,
    so an approved candidate whose patterns are all present is marked applied without touching the document."""
    import yaml
    applied = []
    for inbox in sorted((vault / "projects").glob("*/_meta/covers-candidates.yaml")):
        proj = inbox.parts[-3]
        if project and proj != project:
            continue
        data = yaml.safe_load(inbox.read_text(encoding="utf-8")) or {}
        changed = False
        for c in data.get("candidates") or []:
            if c.get("status") != "approved":
                continue
            path = vault / c["doc"]
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            m = FM_RE.match(text)
            if not m:
                continue
            if c.get("source") == "impact":
                add = {k: v for k, v in (("paths", c.get("paths") or []), ("symbols", c.get("symbols") or [])) if v}
                r = _merge_covers(m.group(1), add)
                if r:
                    path.write_text(text[: m.start(1)] + r[0] + text[m.end(1):], encoding="utf-8")
                    applied.append({"doc": c["doc"], "paths": r[1].get("paths", 0), "symbols": r[1].get("symbols", 0)})
                c["status"] = "applied"; changed = True
                continue
            if re.search(r"^covers:", m.group(1), re.M):
                continue
            block = yaml.safe_dump({"covers": {k: v for k, v in (("paths", c.get("paths") or []), ("symbols", c.get("symbols") or [])) if v}},
                                   allow_unicode=True, sort_keys=False, default_flow_style=None).rstrip("\n")
            fm = m.group(1).rstrip("\n") + "\n" + block
            path.write_text(text[: m.start(1)] + fm + text[m.end(1):], encoding="utf-8")
            c["status"] = "applied"; changed = True
            applied.append({"doc": c["doc"], "paths": len(c.get("paths") or []), "symbols": len(c.get("symbols") or [])})
        if changed:
            inbox.write_text("# covers 후보 Inbox — python3 -m kb hygiene --covers-candidates 가 생성 (정본 아님). status 를 approved 로 바꾼 항목만 적용 대상\n"
                             + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return applied


def write_covers_inbox(vault: Path, cands: dict) -> list[str]:
    import yaml
    written = []
    for proj, rows in cands.items():
        p = vault / "projects" / proj / "_meta" / "covers-candidates.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():   # impact candidates (coverage-gate --covers-candidates) live in the same Inbox — keep them
            old = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            rows = list(rows) + [r for r in (old.get("candidates") or []) if r.get("source") == "impact"]
        p.write_text("# covers 후보 Inbox — python3 -m kb hygiene --covers-candidates 가 생성 (정본 아님). status 를 approved 로 바꾼 항목만 적용 대상\n"
                     + yaml.safe_dump({"project": proj, "generated": date.today().isoformat(), "candidates": rows}, allow_unicode=True, sort_keys=False),
                     encoding="utf-8")
        written.append(p.relative_to(vault).as_posix())
    return written


def allowed_statuses(taxonomy: dict | None, doc_type: str) -> set[str]:
    if not taxonomy:
        return set()
    override = ((taxonomy.get("document_types") or {}).get(doc_type) or {}).get("lifecycle_override")
    if isinstance(override, dict):
        override = override.get("statuses") or []
    if override:
        return {str(s) for s in override}
    return set((taxonomy.get("lifecycle") or {}).get("statuses") or {})


def _has_override(taxonomy: dict | None, doc_type: str) -> bool:
    return bool(doc_type and taxonomy and ((taxonomy.get("document_types") or {}).get(doc_type) or {}).get("lifecycle_override"))


def _project_of(node_id: str, nodes: dict[str, Node]) -> str:
    n = nodes.get(node_id)
    return n.project if n else ""


def repo_projects(vault: Path) -> set[str]:
    from kb.engine import default_project_dirs
    return {d.name for d in default_project_dirs(vault)}


HUB_MIN_IN = 30   # same threshold as the coverage candidate filter (DEC-2026-10-29-03)


def coverage_exemptions(vault: Path) -> dict[str, list[dict]]:
    """Each repo project's coverage-policy exempt list [{path, reason}] from its Tier P (DEC-2026-10-29-08)."""
    from kb.engine import default_project_dirs
    from kb.gates.coverage import load_exemptions
    from kb.legacy.strata_paths import resolve_project_name, resolve_tier_p
    out: dict[str, list[dict]] = {}
    for d in default_project_dirs(vault):
        try:
            tier = resolve_tier_p(d)
        except ValueError:
            continue
        ex = load_exemptions(tier.root if tier else None)
        if ex:
            out[resolve_project_name(d)] = ex
    return out


def _exempt_reason(rel: str, entries: list[dict]) -> str | None:
    hit = next((e for e in entries if rel.startswith(e["path"])), None)
    return (hit.get("reason") or hit["path"]) if hit else None


def hub_covers(store: SqliteStore, project: str | None = None, min_in: int = HUB_MIN_IN,
               exempt: dict[str, list[dict]] | None = None) -> list[dict]:
    """Covers patterns that name a shared hub (MB-strata-kit-2026-013): paths imported by at least `min_in` files of
    other modules. A review list, not a violation: a library's own specification rightly covers the library, but a
    document that only uses a shared package (several documents on the same hub — shared_by) blurs ownership and, before
    DEC-2026-10-29-03, drew every importer's covers candidate; such covers should name the code the document implements.
    A row whose hub lies under a path the project's coverage policy exempts (`exempt`, per project) carries `exempt`
    (the reason) and is not a review target: a path covers under an exempt path, a symbol whose every hub file is."""
    from kb.code import module_of, symbol_files
    code = {n.id: n for n in store.query(kind="code", project=project)}
    rows = []
    for d in store.query(kind="doc", project=project):
        for e in store.neighbors(d.id, kind="covers", direction="out"):
            via, rel = e.dst.split(":", 3)[2:]
            if via == "paths":
                files = [i for i, n in code.items() if i.startswith(e.dst) and n.payload.get("kind") == "file"] if rel.endswith("/") else [e.dst]
                importers = {x.src for f in files for x in store.neighbors(f, kind="imports", direction="in")}
                if rel.endswith("/"):
                    importers |= {x.src for x in store.neighbors(e.dst, kind="imports", direction="in")}
                other = {i for i in importers if module_of(i.split(":", 3)[3]) != module_of(rel)}
                if len(other) >= min_in:
                    rows.append({"project": d.project, "doc": d.id.split(":", 1)[1], "via": via, "pattern": rel, "importers_other_modules": len(other)})
            elif via == "symbols":
                # a symbol defined in a hub file (a shared types file) is a hub too. Symbol nodes are keyed by simple
                # name, so one name can join unrelated files: only the files the symbol resolves to for this document
                # are judged (kb.code.symbol_files), each on its own, never pooled; an unresolved name is marked
                res = symbol_files(store, e.dst, d.id)
                hub_files = {}
                for frel in res["files"]:
                    fid = e.dst.rsplit(":symbols:", 1)[0] + ":paths:" + frel
                    other = {i.src for i in store.neighbors(fid, kind="imports", direction="in") if module_of(i.src.split(":", 3)[3]) != module_of(frel)}
                    if len(other) >= min_in:
                        hub_files[frel] = len(other)
                if hub_files:
                    row = {"project": d.project, "doc": d.id.split(":", 1)[1], "via": via, "pattern": rel,
                           "importers_other_modules": max(hub_files.values()), "defined_in": sorted(hub_files)}
                    if res["ambiguous"]:
                        row["ambiguous"] = res["files"]
                    rows.append(row)
    for r in rows:
        entries = (exempt or {}).get(r["project"]) or []
        reasons = [_exempt_reason(f, entries) for f in (r["defined_in"] if r["via"] == "symbols" else [r["pattern"]])]
        if entries and all(reasons):
            r["exempt"] = reasons[0]
    shared = Counter((r["via"], r["pattern"]) for r in rows)
    for r in rows:
        r["shared_by"] = shared[(r["via"], r["pattern"])]   # several documents on one hub: ownership is blurred — review these first
    return sorted(rows, key=lambda r: (-r["shared_by"], -r["importers_other_modules"], r["doc"], r["pattern"]))


def report(store: SqliteStore, vault: Path, project: str | None = None, top: int = 8) -> dict:
    nodes = {n.id: n for n in store.query()}
    with_repo = repo_projects(vault)
    docs = [n for n in nodes.values() if n.kind in ("doc", *HISTORY_KINDS) and n.payload.get("discovered")
            and (not project or n.project == project)]
    taxonomy = load_taxonomy(vault, project)

    # 1. history status vocabulary
    vocab: dict[str, Counter] = {k: Counter() for k in HISTORY_KINDS}
    for d in docs:
        if d.kind in HISTORY_KINDS:
            declared = d.payload.get("status_declared", True)
            # a planning document kept inside a task folder follows its declared type's vocabulary, not the folder's
            doc_type = str(d.payload.get("type") or "")
            bucket = doc_type if doc_type not in HISTORY_KINDS and _has_override(taxonomy, doc_type) else d.kind
            vocab.setdefault(bucket, Counter())[d.status if declared else "(없음 → 기본값)"] += 1
    history = {}
    for kind, counter in vocab.items():
        allowed = allowed_statuses(taxonomy, kind)
        history[kind] = {
            "allowed_by_taxonomy": sorted(allowed),
            "values": [{"status": s, "count": c, "allowed": s in allowed or s.startswith("(없음"),
                        "proposed": proposed_status(s) or ("open" if s.startswith("(없음") else "?")}
                       for s, c in counter.most_common()],
        }

    # 2. projects without toc.yaml
    projects = sorted({d.project for d in docs if d.project != "vault"})
    toc_rows = []
    for p in projects:
        has_toc = (vault / "projects" / p / "_meta" / "toc.yaml").is_file()
        pdocs = [d for d in docs if d.project == p]
        with_nodes = [d for d in pdocs if d.payload.get("nodes")]
        declared = Counter(str(x) for d in with_nodes for x in d.payload.get("nodes") or [])
        toc_rows.append({"project": p, "toc": has_toc, "docs": len(pdocs), "docs_with_nodes": len(with_nodes),
                         "node_ids_declared": len(declared), "top_node_ids": [k for k, _ in declared.most_common(6)]})

    # 3. state documents without covers
    no_covers = [{"project": d.project, "path": d.path, "type": d.payload.get("type"), "updated": d.updated}
                 for d in docs if d.kind == "doc" and d.payload.get("type") in STATE_TYPES and not d.payload.get("covers")
                 and d.project in with_repo]   # projects without a code repo cannot own code surfaces (user decision 2026-10-28)
    no_covers.sort(key=lambda r: (r["project"], r["path"]))
    no_repo_state_docs = Counter(d.project for d in docs if d.kind == "doc" and d.payload.get("type") in STATE_TYPES
                                 and not d.payload.get("covers") and d.project not in with_repo)

    # 4. broken references — dangling edges grouped by what the link meant
    groups: dict[str, list[dict]] = defaultdict(list)
    origin_refs = 0
    for e in store.dangling_edges():
        src_project = _project_of(e.src, nodes)
        if project and src_project != project:
            continue
        row = {"project": src_project, "from": e.src.split(":", 1)[-1], "to": e.dst, "via": e.source_ref}
        if e.kind == "links" and e.src in nodes and is_origin_immutable(nodes[e.src].payload):
            origin_refs += 1   # a verbatim export's link into its source system — a reference, not a broken vault link
            continue
        if e.kind == "links":
            if e.source_ref.startswith("wiki:none:"):
                groups["wiki"].append(row)
            elif e.source_ref.startswith("md:none:"):
                groups["md-link"].append(row)
            continue   # a resolved link to a non-markdown file is not a node and not broken
        if e.dst.startswith("file:"):
            continue   # a frontmatter path resolved to a non-markdown file on disk — a file, not a node
        if e.kind == "covers" and e.dst.startswith("code:"):
            groups["code"].append(row)
        elif e.kind == "member_of" and e.dst.startswith("node:"):
            groups["node"].append(row)
        elif e.kind == "orders":
            groups["order"].append(row)
        elif e.dst.startswith("decision:"):
            groups["decision"].append(row)
        elif e.dst.startswith("ref:"):
            groups["frontmatter"].append(row)
        else:
            groups["other"].append(row)
    broken = {}
    for key in ("wiki", "md-link", "frontmatter", "node", "order", "decision", "code", "other"):
        rows = groups.get(key, [])
        if not rows:
            continue
        by_project = Counter(r["project"] for r in rows)
        targets = Counter(r["to"] for r in rows)
        broken[key] = {"count": len(rows), "by_project": dict(by_project.most_common()),
                       "top_targets": [{"to": t, "count": c} for t, c in targets.most_common(top)],
                       "sample": rows[:top]}

    # 5. covers that name a shared hub (MB-strata-kit-2026-013)
    hubs = hub_covers(store, project, exempt=coverage_exemptions(vault))

    summary = {
        "documents": len(docs),
        "history_status_values": sum(len(h["values"]) for h in history.values()),
        "history_status_values_outside_taxonomy": sum(1 for h in history.values() for v in h["values"] if not v["allowed"]),
        "projects_without_toc": sum(1 for r in toc_rows if not r["toc"]),
        "projects_without_toc_but_declaring_nodes": sum(1 for r in toc_rows if not r["toc"] and r["docs_with_nodes"]),
        "state_docs_without_covers": len(no_covers),
        "state_docs_without_covers_no_repo": dict(no_repo_state_docs),
        "broken": {k: v["count"] for k, v in broken.items()},
        "origin_references": origin_refs,
        "hub_covers": sum(1 for h in hubs if not h.get("exempt")),
        "hub_covers_exempt": sum(1 for h in hubs if h.get("exempt")),
    }
    return {"vault": str(vault), "project": project, "summary": summary, "history_status": history,
            "projects": toc_rows, "state_docs_without_covers": no_covers, "broken_references": broken,
            "hub_covers": hubs}


def render(r: dict, top: int = 8) -> str:
    s = r["summary"]
    L = [f"# vault 위생 리포트 — {r['vault']}" + (f" (프로젝트 {r['project']})" if r["project"] else ""),
         "등급: advisory — 보고만 하고 막지 않는다 (오더 2026.10.29-02)", "",
         f"문서 {s['documents']} · 이력 상태값 {s['history_status_values']}종(taxonomy 밖 {s['history_status_values_outside_taxonomy']}) · "
         f"toc 없는 프로젝트 {s['projects_without_toc']}(노드를 선언한 문서가 있는 곳 {s['projects_without_toc_but_declaring_nodes']}) · "
         f"covers 없는 최종형상 {s['state_docs_without_covers']} · 깨진 참조 " + (", ".join(f"{k} {v}" for k, v in s["broken"].items()) or "없음")
         + (f" · 원문 불변 문서의 바깥 참조 {s['origin_references']}(참고)" if s.get("origin_references") else ""), ""]
    L.append("## 1. 이력 상태 어휘 (session · task) — taxonomy 와 대조")
    for kind, h in r["history_status"].items():
        L.append(f"- {kind}: taxonomy 허용 집합 {h['allowed_by_taxonomy'] or '(없음 — lifecycle_override 미정의, 코어 lifecycle 만 적용)'}")
        for v in h["values"]:
            mark = "" if v["allowed"] else "  ← taxonomy 밖"
            L.append(f"    {v['count']:4d}  {v['status']}  → 제안 {v['proposed']}{mark}")
    L += ["", "## 2. toc.yaml 없는 프로젝트 (nodes 를 선언한 문서 수 · 선언된 노드 id)"]
    for row in r["projects"]:
        if row["toc"]:
            continue
        L.append(f"- {row['project']}: 문서 {row['docs']}, nodes 선언 문서 {row['docs_with_nodes']}, 노드 id {row['node_ids_declared']}종 {row['top_node_ids']}")
    L += ["", f"## 3. covers 없는 최종형상 문서 ({s['state_docs_without_covers']}; 코드 저장소 없는 프로젝트는 제외: {s['state_docs_without_covers_no_repo']})"]
    by = defaultdict(list)
    for row in r["state_docs_without_covers"]:
        by[row["project"]].append(row)
    for p, rows in sorted(by.items()):
        L.append(f"- {p} ({len(rows)}): " + ", ".join(Path(x["path"]).stem for x in rows[:top]) + (f" … 외 {len(rows) - top}" if len(rows) > top else ""))
    L += ["", "## 4. 깨진 참조 (store dangling edges)"]
    labels = {"wiki": "본문 위키링크 → 없는 문서", "md-link": "본문 마크다운 링크 → 없는 파일", "frontmatter": "frontmatter(kb_updates·decisions_made·supersedes) → 없는 문서",
              "node": "nodes → toc 에 없는 노드", "order": "orders → 없는 오더", "decision": "decisions → 없는 결정 레코드",
              "code": "covers → 저장소에 없는 코드 표면 (코드 그래프가 못 찾음 — covers 가 낡았거나 패턴 오타)", "other": "기타"}
    for key, g in r["broken_references"].items():
        L.append(f"- {labels[key]}: {g['count']} — 프로젝트별 {g['by_project']}")
        for t in g["top_targets"][:5]:
            L.append(f"    {t['count']:3d} × {t['to']}")
    L += ["", f"## 5. 공용 허브를 covers 로 가진 문서 ({s.get('hub_covers', 0)}; 다른 모듈에서 {HUB_MIN_IN}개 이상 파일이 import 하는 경로, 또는 그런 파일에 정의된 심볼) — 검토 대상",
          "  그 라이브러리의 명세면 그대로 둔다. 쓰기만 하는 문서면 covers 를 자기 구현 지점으로 좁힌다. 같은 허브를 여러 문서가 가지면(공유 n) 먼저 본다."]
    target = lambda row: f"심볼 {row['pattern']} ({', '.join(row['defined_in'])})" if row.get("via") == "symbols" else row["pattern"]
    rows = r.get("hub_covers", [])
    for row in [x for x in rows if not x.get("exempt")][:top]:
        amb = f" · 정의 모호 {len(row['ambiguous'])}곳 — covers.paths 로 정의 파일을 좁힌다" if row.get("ambiguous") else ""
        L.append(f"- {row['doc']}: {target(row)} (다른 모듈 import {row['importers_other_modules']} · 공유 {row['shared_by']}{amb})")
    exempt_rows = [x for x in rows if x.get("exempt")]
    if exempt_rows:
        L.append(f"  커버리지 정책 면제 {len(exempt_rows)} — coverage-policy.yaml 이 면제한 경로라 검토 대상이 아니다 (목록만)")
        for row in exempt_rows[:top]:
            L.append(f"    {row['doc']}: {target(row)} — {row['exempt']}")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb hygiene", description="vault 위생 리포트 (읽기 전용)")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--db", default=None, help="store.sqlite (기본 <vault>/.kb/store.sqlite; 낡았으면 다시 만든다)")
    ap.add_argument("--project", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--rewrite-status", action="store_true", help="session·task 상태를 5종 어휘로 (기본 dry-run)")
    ap.add_argument("--covers-candidates", action="store_true", help="covers 없는 최종형상의 후보 covers 를 _meta/covers-candidates.yaml 로")
    ap.add_argument("--covers-apply", action="store_true", help="Inbox 에서 status: approved 인 후보의 covers 를 문서 frontmatter 에 쓴다 (source: impact 는 기존 covers 에 빠진 패턴만 더함)")
    ap.add_argument("--apply", action="store_true", help="--rewrite-status 를 실제로 쓴다")
    ap.add_argument("--memory", nargs="?", const="", default=None, metavar="DIR",
                    help="메모리 절만 — DIR(없으면 지금 폴더의 Claude Code 프로젝트 메모리)의 정리 후보 (읽기 전용, DEC-2026-10-31-18)")
    ap.add_argument("--memory-all", action="store_true", help="이 머신의 Claude Code 프로젝트 메모리 전부의 집계 (본문 없이)")
    args = ap.parse_args(argv)
    from kb.gates import memory_hygiene as mh
    if args.memory is not None or args.memory_all:
        dirs = ([p for p in sorted((Path.home() / ".claude" / "projects").glob("*/memory")) if any(p.glob("*.md"))]
                if args.memory_all else [Path(args.memory).expanduser() if args.memory else mh.memory_dir_for(Path.cwd())])
        rs = [mh.report(d) for d in dirs]
        if args.json:
            print(json.dumps(rs if args.memory_all else rs[0], ensure_ascii=False, indent=2))
        elif args.memory_all:
            for r in rs:
                c = mh.counts(r)
                print(f"{Path(r['dir']).parent.name}: 항목 {r['facts']} · 인덱스 {r['index_bytes']}B"
                      + (" (12KB 초과)" if r["index_over_budget"] else "") + " · "
                      + ", ".join(f"{mh.LABEL[k]} {v}" for k, v in c.items()) + f" · 반대 피드백 후보 {len(r['pairs'])}"
                      + f" · 인덱스 불일치 {len(r['index_only']) + len(r['file_only'])}")
        else:
            print("\n".join(mh.render(rs[0], args.top if args.top != 8 else 20)))
        return 0
    vault = Path(args.vault).resolve() if args.vault else vault_root()
    if vault is None:
        print("STRATA_VAULT not set and --vault not given", file=sys.stderr)
        return 2
    store = ensure_fresh_store(Path(args.db).resolve() if args.db else None, vault=vault)
    try:
        if args.rewrite_status:
            r = rewrite_status(store, vault, args.project, args.apply)
            if args.json:
                print(json.dumps(r, ensure_ascii=False, indent=2))
            else:
                for x in r["rewritten"]:
                    print(f"  {x['path']}: {x['old']} → {x['new']}")
                for x in r["unmapped"]:
                    print(f"  ? {x['path']}: '{x['status']}' 는 매핑 없음")
                print(f"{'적용' if args.apply else 'dry-run'}: 치환 {len(r['rewritten'])} · 이미 정식 {r['already_canonical']} · 매핑 없음 {len(r['unmapped'])}")
            return 0
        if args.covers_apply:
            for a in apply_covers(vault, args.project):
                print(f"  covers 기록: {a['doc']} (paths {a['paths']} · symbols {a['symbols']})")
            return 0
        if args.covers_candidates:
            cands = covers_candidates(store, vault, repo_projects(vault), args.project)
            files = write_covers_inbox(vault, cands)
            for proj, rows in cands.items():
                print(f"  {proj}: 후보 {len(rows)}건")
            print("Inbox:", ", ".join(files) or "(없음)")
            return 0
        r = report(store, vault, args.project, args.top)
    finally:
        store.close()
    mem = mh.report(mh.memory_dir_for(Path.cwd()))
    if args.json:
        print(json.dumps({**r, "memory": mem}, ensure_ascii=False, indent=2))
    else:
        print(render(r, args.top), end="")
        if mem["exists"]:
            print("\n".join(mh.render(mem, args.top)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
