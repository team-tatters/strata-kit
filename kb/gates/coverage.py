"""Coverage resolver and session-end coverage gate, reading the store.

Same contract as strata/scripts/kb_coverage.py and kb_coverage_gate.py (which are now shuttles to this
module): resolve(paths) → owning documents, nodes_for, unowned, docs_to_update, owners_of_node;
run_gate(project_dir, session_fm, files, since) → warnings only (never blocks); format_report.
Matching rules are unchanged: covers.paths match by substring, covers.symbols by exact file stem,
longer patterns first. Endpoints and tables are kept but not resolved from file paths.

The store is opened through ensure_fresh_store, so a stale store is rebuilt before the query
(KB_NO_REFRESH=1 skips that). Both the legacy index and this store derive from the same frontmatter,
so the answers are the same; the equivalence script in kb/tests proves it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath

from kb.store import Node, SqliteStore, StoreError

COVERS_KINDS = ("paths", "symbols", "endpoints", "tables")
STATE_TYPES = ("specification", "concept")
SOURCE_EXT = {".kt", ".kts", ".java", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".sql", ".vue", ".swift"}
FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)


# ---------------------------------------------------------------- store

def get_store(store_path: str | None = None) -> SqliteStore:
    """Open the vault store, rebuilding it first when its sources are newer (KB_NO_REFRESH=1 to skip)."""
    from kb.engine import ensure_fresh_store
    return ensure_fresh_store(Path(store_path) if store_path else None)


def normalize_path(p: str) -> str:
    """저장소 상대경로로 정규화. 절대경로면 $STRATA_PROJECTS/{project}/ 접두를 뗀다."""
    s = str(p).strip().replace("\\", "/")
    if s.startswith("./"):
        s = s[2:]
    if s.startswith("/"):
        projects = os.environ.get("STRATA_PROJECTS")
        if projects:
            root = Path(projects).resolve()
            try:
                rel = Path(s).resolve().relative_to(root)
                parts = rel.parts
                if len(parts) > 1:
                    return "/".join(parts[1:])
            except ValueError:
                pass
    return s


# ---------------------------------------------------------------- coverage rows

def _doc_nodes(store: SqliteStore) -> list[Node]:
    """Every document node the scanner produced (doc · session · task kinds), in path order."""
    out = []
    for kind in ("doc", "session", "task"):
        out.extend(n for n in store.query(kind=kind) if n.id.startswith("doc:"))
    return sorted(out, key=lambda n: n.path)


def coverage_rows(store: SqliteStore) -> list[dict]:
    """One row per (document, covers kind, pattern, node) — the legacy `coverage` table, derived from
    the document nodes' frontmatter payload. Row order within a document follows the frontmatter."""
    rows = []
    for n in _doc_nodes(store):
        covers = n.payload.get("covers") or {}
        if not isinstance(covers, dict) or not covers:
            continue
        nodes = [str(x) for x in (n.payload.get("nodes") or [])]
        for kind in COVERS_KINDS:
            vals = covers.get(kind)
            if not isinstance(vals, list):
                continue
            for pattern in vals:
                for node_id in (nodes or [""]):
                    rows.append({"kind": kind, "pattern": str(pattern), "node_id": node_id, "doc_updated": n.updated,
                                 "file_path": n.path, "stable_id": n.payload.get("stable_id") or "", "title": n.title,
                                 "type": n.payload.get("type") or "", "status": n.status, "updated": n.updated,
                                 "nodes": nodes, "covers": covers})
    return rows


def resolve(store: SqliteStore, paths: list[str]) -> dict[str, list[dict]]:
    """경로 → 소유 문서 목록. 각 항목: doc, stable_id, title, type, status, updated, node, kind, pattern."""
    rows = coverage_rows(store)
    out: dict[str, list[dict]] = {}
    for raw in paths:
        p = normalize_path(raw)
        stem = PurePosixPath(p).stem
        hits = [r for r in rows if (r["kind"] == "paths" and r["pattern"] and r["pattern"] in p)
                or (r["kind"] == "symbols" and r["pattern"] == stem)]
        hits.sort(key=lambda r: (-len(r["pattern"]), r["file_path"]))
        seen = set()
        items = []
        for r in hits:
            key = (r["file_path"], r["node_id"], r["kind"], r["pattern"])
            if key in seen:
                continue
            seen.add(key)
            items.append({"doc": r["file_path"], "stable_id": r["stable_id"], "title": r["title"], "type": r["type"],
                          "status": r["status"], "updated": r["updated"] or r["doc_updated"] or "",
                          "node": r["node_id"] or "", "kind": r["kind"], "pattern": r["pattern"]})
        out[p] = items
    return out


def nodes_for(store: SqliteStore, paths: list[str]) -> list[str]:
    ids = {it["node"] for items in resolve(store, paths).values() for it in items if it["node"]}
    return sorted(ids)


def unowned(store: SqliteStore, paths: list[str]) -> list[str]:
    return [p for p, items in resolve(store, paths).items() if not items]


def docs_to_update(store: SqliteStore, paths: list[str]) -> list[dict]:
    """Builder 가 태스크 scope.docs_to_update 에 넣을 항목 — 문서당 1개, 매칭 근거를 reason 으로."""
    by_doc: dict[str, dict] = {}
    for p, items in resolve(store, paths).items():
        for it in items:
            entry = by_doc.setdefault(it["doc"], {
                "node": it["node"],
                "doc": f"[[{PurePosixPath(it['doc']).stem}]]",
                "id": it["stable_id"],
                "path": it["doc"],
                "status": it["status"],
                "updated": it["updated"],
                "matched": [],
            })
            entry["matched"].append(f"{it['kind']}:{it['pattern']} ← {p}")
            if not entry["node"] and it["node"]:
                entry["node"] = it["node"]
    result = []
    for e in by_doc.values():
        e["reason"] = "covers 일치 — " + "; ".join(dict.fromkeys(e.pop("matched")))
        result.append(e)
    return sorted(result, key=lambda x: (x["node"], x["path"]))


def owners_of_node(store: SqliteStore, node_id: str) -> list[dict]:
    """노드의 최종형상 문서 — nodes 에 node_id 를 가진 specification·concept (covers 유무 표시)."""
    out = []
    for n in _doc_nodes(store):
        t = n.payload.get("type") or ""
        if t not in STATE_TYPES or node_id not in [str(x) for x in (n.payload.get("nodes") or [])]:
            continue
        covers = n.payload.get("covers") or {}
        out.append({"doc": n.path, "stable_id": n.payload.get("stable_id") or "", "title": n.title, "type": t,
                    "status": n.status, "updated": n.payload.get("updated_fm") or "",   # legacy: frontmatter updated only
                    "covers": {k: len(v) for k, v in covers.items() if isinstance(v, list)}})
    return sorted(out, key=lambda e: (e["type"], e["doc"]))


# ---------------------------------------------------------------- reverse direction (오더 2026.10.29-04, MB-strata-kit-2026-012)

def _affect_paths(affects) -> list[str]:
    """Path-like tokens of a decision's free-text affects ('a/b.py(fn), c/d.sh' → ['a/b.py', 'c/d.sh'])."""
    out = []
    for entry in affects if isinstance(affects, list) else [affects or ""]:
        for tok in re.split(r"[,·]", re.sub(r"\([^)]*\)", "", str(entry))):
            tok = tok.strip()
            if tok and " " not in tok and ("/" in tok or re.search(r"\.\w{1,5}$", tok)) and tok not in out:
                out.append(tok)
    return out


def recheck_code(store: SqliteStore, project: str, docs: list[str] | None = None, decisions: list[str] | None = None) -> list[dict]:
    """Code to look at again when knowledge changed rather than code (advisory). A changed document that is not a
    specification with covers (a concept, policy or decision note) points to the covers of the specifications on the same
    topic nodes; a superseded or withdrawn decision points to its own affects, and a decision that supersedes another
    points to the old one's affects. Specifications with covers are the forward gate's business."""
    out: list[dict] = []
    specs = [n for n in store.query(kind="doc", project=project)
             if n.payload.get("type") in STATE_TYPES and isinstance(n.payload.get("covers"), dict) and n.payload.get("covers")]
    for path in docs or []:
        d = store.get(f"doc:{path}")
        if not d or (d.payload.get("type") in STATE_TYPES and d.payload.get("covers")):
            continue
        for node in [str(x) for x in d.payload.get("nodes") or []]:
            for s in specs:
                if s.path != path and node in [str(x) for x in s.payload.get("nodes") or []]:
                    cv = s.payload["covers"]
                    paths = [p for k in ("paths", "symbols") for p in (cv.get(k) or [])]
                    out.append({"from": path, "via": f"node {node}", "owner": s.path, "paths": paths})
    for dec in decisions or []:
        n = store.get(f"decision:{project}:{dec}")
        if not n:
            continue
        if n.status in ("superseded", "withdrawn"):
            out.append({"from": dec, "via": n.status, "owner": dec, "paths": _affect_paths(n.payload.get("affects"))})
        for old in n.payload.get("supersedes") or []:
            o = store.get(f"decision:{project}:{old}")
            if o:
                out.append({"from": dec, "via": f"supersedes {old}", "owner": old, "paths": _affect_paths(o.payload.get("affects"))})
    return out


def changed_knowledge(project: str, since: str, repo_changed: list[str], vault: Path | None = None) -> tuple[list[str], list[str]]:
    """Knowledge changed in the session: the project's vault documents (sessions, tasks and generated views excluded) and
    decision ids from Tier P records (the repo's .strata/decisions or the vault's projects/<p>/strata/decisions). DEC notes
    are not read: the note generator rewrites many of them at once."""
    if vault is None:
        from kb import vault_root
        vault = vault_root()
    docs, decs = set(), set()
    names = [f for f in repo_changed if re.search(r"(^|/)\.strata/decisions/DEC-", f)]
    if vault and (vault / ".git").exists():
        base = f"projects/{project}"
        log = _git(str(vault), "log", f"--since={since}", "--name-only", "--format=", "--", base)
        st = [l[3:] for l in _git(str(vault), "status", "--porcelain", "--", base).splitlines() if l.strip()]
        for f in {*log.split(), *st}:
            if re.search(r"/strata/decisions/DEC-", f):   # Tier P records only — DEC notes are regenerated mirrors
                names.append(f)
            elif f.endswith(".md") and not re.search(rf"^{base}/(sessions|tasks|nodes|decisions)/", f):
                docs.add(f)
    for f in names:
        m = re.search(r"(DEC-\d{4}-\d{2}-\d{2}-\d{2})", f)
        if m:
            decs.add(m.group(1))
    return sorted(docs), sorted(decs)


def recheck_lines(rows: list[dict], top: int = 8) -> list[str]:
    if not rows:
        return []
    paths = {p for r in rows for p in r["paths"]}
    L = [f"다시 확인할 코드(advisory) — 문서·결정 {len({r['from'] for r in rows})} → 경로 {len(paths)}"]
    L += [f"  {r['from']} → {r['owner']} ({r['via']}): " + ", ".join(r["paths"][:5]) + (" …" if len(r["paths"]) > 5 else "") for r in rows[:top]]
    if len(rows) > top:
        L.append(f"  … 외 {len(rows) - top}건")
    return L


# ---------------------------------------------------------------- desired shape (DEC-2026-10-29-09, 오더 2026.10.29-03 task-02)

DESIRED_SKIP = {"superseded"}   # a replaced plan no longer states a desired shape


def desired_shape(store: SqliteStore, owned: dict[str, list[str]], since: str | None = None) -> list[dict]:
    """Planning documents whose implementation.spec names a specification that owns changed code ({spec doc: paths}).
    implemented → the code moved after the plan was met: recheck the plan against it; anything else → the change may be
    (part of) the implementation: update implementation.status. A plan reviewed on or after `since` was already
    judged against these changes and is left out (DEC-2026-10-31-35). The list itself is advisory; the recheck rows are
    graded at the project's coverage grade in grade_new_spec (DEC-2026-11-02-05)."""
    rows = []
    for spec, paths in owned.items():
        for e in store.neighbors(f"doc:{spec}", kind="implementation", direction="in"):
            n = store.get(e.src)
            status = (n.payload.get("implementation_status") or "") if n else ""
            if not n or status in DESIRED_SKIP:
                continue
            if since and (n.payload.get("implementation_reviewed") or "") >= since:
                continue
            rows.append({"planning": n.path, "title": n.title, "spec": spec, "status": status or "-",
                         "action": "recheck" if status == "implemented" else "update-status", "paths": sorted(paths)})
    return sorted(rows, key=lambda r: (r["action"], r["planning"], r["spec"]))


def desired_shape_lines(rows: list[dict], top: int = 8) -> list[str]:
    if not rows:
        return []
    label = {"recheck": "구현됨인데 코드가 바뀜 — 재대조", "update-status": "상태 갱신 필요"}
    L = [f"바라는 형상 대조 — 기획 문서 {len({r['planning'] for r in rows})} (재대조는 coverage 등급, 상태 갱신은 advisory)"]
    L += [f"  [[{PurePosixPath(r['planning']).stem}]] ({r['status']}) → [[{PurePosixPath(r['spec']).stem}]]: {label[r['action']]}" for r in rows[:top]]
    if len(rows) > top:
        L.append(f"  … 외 {len(rows) - top}건")
    return L


# ---------------------------------------------------------------- gate

def _git(project_dir: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", project_dir, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def changed_files(project_dir: str, since: str | None) -> list[str]:
    """워킹트리 변경 ∪ since 이후 커밋 파일 (저장소 상대경로). git 이 아니면 빈 목록."""
    files: list[str] = []
    seen: set[str] = set()

    def add(p: str):
        p = p.strip().strip('"')
        if p and p not in seen:
            seen.add(p)
            files.append(p)

    for line in _git(project_dir, "status", "--porcelain", "--untracked-files=all").splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        add(path)
    if since:
        for line in _git(project_dir, "log", f"--since={since}T00:00:00", "--name-only", "--pretty=format:").splitlines():
            add(line)
    return files


def deleted_files(project_dir: str, since: str | None) -> list[str]:
    """Files this session removed (MB-strata-kit-2026-017): deleted in the working tree or in a commit since `since`,
    and still absent now. Read from git, so paths given with --files that git never saw stay ordinary changes."""
    out: list[str] = []
    for line in _git(project_dir, "status", "--porcelain").splitlines():
        if len(line) > 3 and "D" in line[:2]:
            out.append(line[3:].strip().strip('"'))
    if since:
        for line in _git(project_dir, "log", f"--since={since}T00:00:00", "--diff-filter=D", "--name-only",
                         "--pretty=format:").splitlines():
            if line.strip():
                out.append(line.strip().strip('"'))
    root = Path(project_dir)
    return sorted({f for f in out if not (root / f).exists()})


def read_session_fm(path: str | os.PathLike) -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    try:
        text = Path(path).read_text(encoding="utf-8")
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


def _wl(v) -> str:
    s = str(v).strip()
    m = re.match(r"^\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]$", s)
    return (m.group(1) if m else s.split("#", 1)[0]).strip()


def impact_candidates(store: SqliteStore, project: str, changed: list[str], direct_owner_docs: set[str], depth: int = 1) -> dict:
    """Documents that own files importing the changed files (code graph, reverse imports) but do not own the
    changed files themselves. Empty when the project has no code graph in the store."""
    try:
        from kb.code import impact
    except ImportError:  # pragma: no cover
        return {"files": 0, "candidates": []}
    ids = [f"code:{project}:paths:{normalize_path(p)}" for p in changed]
    ids = [i for i in ids if store.get(i)]
    if not ids:
        return {"files": 0, "candidates": []}
    r = impact(store, ids, depth)
    cands = []
    for o in r["owning_docs"]:
        doc = o["doc"]
        if doc in direct_owner_docs or not doc.startswith(f"projects/{project}/"):
            continue
        cands.append({"doc": doc, "stem": PurePosixPath(doc).stem, "title": o.get("title", ""), "via": o.get("via", "")})
    return {"files": len(r["impacted"]), "candidates": cands}


OWNER_TOP = 3
HUB_MIN_IN = 30   # 이 수 이상의 파일이 import 하는 이웃은 허브 — 투표하지 않는다 (DEC-2026-10-29-03; PR 8건 재측정: 모듈 안 권한 가드 34 를 거르고 전역 허브는 이미 모듈 밖)
INBOX_HEAD = "# covers 후보 Inbox — python3 -m kb hygiene --covers-candidates 가 생성 (정본 아님). status 를 approved 로 바꾼 항목만 적용 대상\n"


def module_of(path: str) -> str:
    from kb.code import module_of as _module_of
    return _module_of(path)


def owner_candidates(store: SqliteStore, project: str, files: list[str], top: int = OWNER_TOP,
                     hub_min_in: int | None = HUB_MIN_IN) -> list[dict]:
    """Covers candidates for changed files that no specification owns (오더 2026.10.28-11): for each file, the owner
    documents of its 1-hop import neighbours ranked by votes (kb.code.owner_votes), top `top`. Grouped by document,
    each candidate proposes the files' directories as covers.paths, in the Inbox shape of the hygiene pass (source: impact).
    Only neighbours in the file's module vote, and shared hubs do not (DEC-2026-10-29-03).
    A file outside the code graph or without owned neighbours yields nothing."""
    try:
        from kb.code import owner_votes
    except ImportError:  # pragma: no cover
        return []
    by_doc: dict[str, dict] = {}
    for raw in files:
        rel = normalize_path(raw)
        fid = f"code:{project}:paths:{rel}"
        if not store.get(fid):
            continue
        v = owner_votes(store, project, [fid], same_module=True, hub_min_in=hub_min_in)
        for rank, doc in enumerate(v["ranked"][:top], 1):
            if not doc.startswith(f"projects/{project}/"):
                continue
            n = store.get(f"doc:{doc}")
            c = by_doc.setdefault(doc, {"doc": doc, "title": n.title if n else "", "status": "pending", "source": "impact",
                                        "paths": [], "evidence": []})
            d = str(PurePosixPath(rel).parent) + "/"
            if d not in c["paths"]:
                c["paths"].append(d)
            c["evidence"].append({"file": rel, "rank": rank, "votes": v["votes"][doc], "neighbours": v["neighbours"],
                                  "voters": v["voters"][doc][:5]})
    return sorted(by_doc.values(), key=lambda c: (-sum(e["votes"] for e in c["evidence"]), c["doc"]))


def write_impact_inbox(vault: Path, project: str, cands: list[dict]) -> str | None:
    """Merge impact candidates into projects/<project>/_meta/covers-candidates.yaml. Entries of other sources and
    impact entries already decided (approved · applied · rejected) are kept as they are; a pending impact entry for
    the same document is replaced by the new one. Nothing is written when there are no candidates."""
    if not cands:
        return None
    import yaml
    p = vault / "projects" / project / "_meta" / "covers-candidates.yaml"
    data = {}
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    rows = list(data.get("candidates") or [])
    decided = {r["doc"] for r in rows if r.get("source") == "impact" and r.get("status") != "pending"}
    fresh = {c["doc"]: c for c in cands if c["doc"] not in decided}
    rows = [r for r in rows if not (r.get("source") == "impact" and r.get("status") == "pending" and r["doc"] in fresh)]
    rows += list(fresh.values())
    data = {"project": project, "generated": date.today().isoformat(), "candidates": rows}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(INBOX_HEAD + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p.relative_to(vault).as_posix()


def summary_line(unowned_count: int, cands: list[dict], exempt_count: int = 0, deleted_count: int = 0,
                 baseline_count: int = 0) -> str:
    """The session-end channel line (오더 2026.10.28-11 task-03): unowned changed sources · how many of them got a
    candidate, with the number of candidate specifications; files exempted by the coverage policy and files already
    on the baseline (DEC-2026-10-31-32) are counted apart."""
    files = len({e["file"] for c in cands for e in c["evidence"]})
    line = f"명세 없는 변경 코드 {unowned_count} · 후보 {files}"
    line += f" (후보 명세 {len(cands)}편)" if cands else ""
    line += f" · 새 명세 필요 {unowned_count - files - exempt_count - baseline_count}" if unowned_count else ""
    line += f" · 면제 {exempt_count}" if exempt_count else ""
    line += f" · 기준선 {baseline_count}" if baseline_count else ""
    return line + (f" · 삭제 {deleted_count}" if deleted_count else "")   # removed code needs no spec (MB-017)


# ---------------------------------------------------------------- coverage policy (오더 2026.10.29-03, DEC-2026-10-29-08)

def load_coverage_policy(tier_root: Path | None) -> dict:
    """The grade comes from Tier P profile.yaml enforcement.coverage (DEC-2026-10-31-31); undeclared → advisory (report
    only), unlike the other enforcement families whose undeclared grade is block. coverage-policy.yaml holds the
    exempt list [{path, reason}]; its old `grade` is still read when the profile declares none, with a note to move it."""
    import yaml
    from kb.gates.grades import GRADES
    pol = {"grade": "advisory", "exempt": [], "notes": []}
    if not tier_root:
        return pol
    prof = tier_root / "profile.yaml"
    enf = ((yaml.safe_load(prof.read_text(encoding="utf-8")) or {}).get("enforcement") if prof.is_file() else None) or {}
    declared = enf.get("coverage") if isinstance(enf, dict) else None
    p = tier_root / "coverage-policy.yaml"
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}
    pol["exempt"] = [e for e in d.get("exempt") or [] if isinstance(e, dict) and e.get("path")]
    old = d.get("grade")
    if declared is not None:
        if declared not in GRADES:
            raise ValueError(f"enforcement.coverage: unknown grade {declared!r} (one of {', '.join(GRADES)})")
        pol["grade"] = declared
        if old is not None:
            pol["notes"].append(f"coverage-policy.yaml 의 grade({old}) 는 읽지 않는다 — 등급은 profile.yaml enforcement.coverage({declared}) (DEC-2026-10-31-31)")
    elif old is not None:
        pol["grade"] = old if old in GRADES else "advisory"
        pol["notes"].append(f"등급을 coverage-policy.yaml grade({old}) 에서 읽음 — profile.yaml enforcement.coverage 로 옮긴다 (DEC-2026-10-31-31)")
    return pol


# ---------------------------------------------------------------- baseline (DEC-2026-10-31-32)

BASELINE = "coverage-baseline.yaml"
BASELINE_HEAD = ("# 커버리지 기준선 — 저장한 날 소유 명세가 없던 소스 파일 (DEC-2026-10-31-32). 생성물: kb coverage-gate --write-baseline.\n"
                 "# 여기 있는 파일을 바꾼 것은 등급을 받지 않고 '기준선 N' 으로 센다. 명세가 맡으면 다음 저장에서 빠진다.\n")


def load_baseline(tier_root: Path | None) -> set[str] | None:
    """Files on the baseline, or None when the project has not saved one."""
    p = (tier_root / BASELINE) if tier_root else None
    if not (p and p.is_file()):
        return None
    import yaml
    return {str(f) for f in ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("files") or [])}


def unowned_sources(resolved: dict[str, list[dict]], project: str, has_project_docs: bool) -> list[str]:
    """Source files no document of this project owns (any owner counts when the project has no documents yet)."""
    return [p for p, items in resolved.items()
            if not any((not has_project_docs) or it["doc"].startswith(f"projects/{project}/") for it in items)
            and PurePosixPath(p).suffix in SOURCE_EXT]


def write_baseline(project_dir: str, tier_root: Path, store: SqliteStore, today: str | None = None) -> tuple[Path, int]:
    """Save every tracked source file that no specification owns today and the policy does not exempt."""
    import yaml
    project = Path(project_dir).resolve().name
    tracked = [f for f in _git(project_dir, "ls-files").splitlines() if f]
    has_project_docs = bool(store.query(path_prefix=f"projects/{project}/"))
    pol = load_coverage_policy(tier_root)
    files = sorted(f for f in unowned_sources(resolve(store, tracked), project, has_project_docs)
                   if not any(f.startswith(e["path"]) for e in pol["exempt"]))
    p = tier_root / BASELINE
    data = {"project": project, "created": today or date.today().isoformat(), "count": len(files), "files": files}
    p.write_text(BASELINE_HEAD + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p, len(files)


def apply_baseline(kept: dict[str, list[str]], base: set[str] | None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split 'new spec needed' into files that are new gaps and files already on the baseline."""
    if not base:
        return kept, {}
    new: dict[str, list[str]] = {}
    old: dict[str, list[str]] = {}
    for mod, files in kept.items():
        for f in files:
            (old if f in base else new).setdefault(mod, []).append(f)
    return new, old


def apply_exemptions(need: dict[str, list[str]], pol: dict) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split 'new spec needed' files into those still needing a spec and those the policy exempts (by reason)."""
    kept: dict[str, list[str]] = {}
    exempt: dict[str, list[str]] = {}
    for mod, files in need.items():
        for f in files:
            hit = next((e for e in pol["exempt"] if f.startswith(e["path"])), None)
            if hit:
                exempt.setdefault(hit.get("reason") or hit["path"], []).append(f)
            else:
                kept.setdefault(mod, []).append(f)
    return kept, exempt


def grade_new_spec(kept: dict[str, list[str]], pol: dict, tier_root: Path | None, today: str | None = None,
                   desired: list[dict] | None = None) -> dict:
    """Findings at the policy's grade, overrides from Tier P: one per module needing a spec, and one per implemented
    plan whose specification's code changed without the plan being judged in the window (DEC-2026-11-02-05)."""
    from kb.gates.grades import Finding, evaluate, load_overrides
    if pol.get("grade") not in ("default", "block"):
        return {"rc": 0, "blocked": [], "unresolved": [], "overridden": [], "advisory": [], "expired": []}
    found = [Finding("coverage", f"new_spec:{m}", pol["grade"], f"소유 명세 없는 변경 {len(fs)}개 — 명세를 쓰거나 사유·기한을 남긴다")
             for m, fs in sorted(kept.items())]
    for plan in sorted({r["planning"] for r in desired or [] if r.get("action") == "recheck"}):
        rows = [r for r in desired if r["planning"] == plan and r["action"] == "recheck"]
        specs = ", ".join(sorted({PurePosixPath(r["spec"]).stem for r in rows}))
        found.append(Finding("coverage", f"desired:{PurePosixPath(plan).stem}", pol["grade"],
                             f"구현됨 기획의 명세({specs})가 맡은 코드가 바뀜 — 대조해 판정한다(kb divergence add·judge) 또는 사유·기한"))
    return evaluate(found, load_overrides(tier_root / "gate-overrides.yaml") if tier_root else [], today=today)


def new_spec_needed(unowned_paths: list[str], cands: list[dict]) -> dict[str, list[str]]:
    """Unowned changed files that got no candidate, grouped by module (DEC-2026-10-29-03) — the areas that need a
    specification of their own rather than an existing one's covers."""
    got = {e["file"] for c in cands for e in c["evidence"]}
    out: dict[str, list[str]] = {}
    for p in unowned_paths:
        rel = normalize_path(p)
        if rel not in got:
            out.setdefault(module_of(rel), []).append(rel)
    return {m: sorted(fs) for m, fs in sorted(out.items())}


def _since_date(value: str) -> str:
    """since is a day (YYYY-MM-DD): git log --since and the doc 'updated' comparison both read it as one. A revision
    here made git read the whole history without a word (MB-strata-kit-2026-030), so anything else is refused."""
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"--since 는 날짜(YYYY-MM-DD)여야 한다: {value!r} — 커밋 범위는 --files $(git diff --name-only <rev> HEAD) 로")
    return value


def run_gate(project_dir: str, session_fm: dict | None = None, files: list[str] | None = None,
             since: str | None = None, db: str | None = None, store: SqliteStore | None = None,
             knowledge: tuple[list[str], list[str]] | None = None) -> dict:
    session_fm = session_fm or {}
    since = since or str(session_fm.get("created") or "")[:10] or date.today().isoformat()
    _since_date(since)
    project = Path(project_dir).resolve().name
    result = {"project": project, "since": since, "changed": [], "deleted": [], "owners": [], "unowned": [],
              "nodes": [], "warnings": [], "info": [], "owner_candidates": [], "new_spec_needed": {}, "exempt": {}, "baselined": {}, "grades": [], "grade_rc": 0, "recheck": [], "desired_shape": [], "summary_line": summary_line(0, [])}

    changed = files if files is not None else changed_files(project_dir, since)
    result["changed"] = changed
    gone = set(deleted_files(project_dir, since)) & set(changed)
    result["deleted"] = sorted(gone)
    if not changed:
        result["info"].append("변경 파일 없음 — 커버리지 검사 대상 없음")
        return result

    try:
        store = store or get_store(db)
    except (StoreError, SystemExit) as e:
        result["warnings"].append(f"커버리지 게이트 생략 — {e}")
        return result
    except Exception as e:  # noqa: BLE001
        result["warnings"].append(f"커버리지 게이트 생략 — 저장소 접근 실패: {e}")
        return result

    resolved = resolve(store, changed)
    has_project_docs = bool(store.query(path_prefix=f"projects/{project}/"))

    kb_updates = {_wl(x) for x in (session_fm.get("kb_updates") or [])}
    declared_nodes = {str(n) for n in (session_fm.get("nodes") or [])}
    doc_change = str(session_fm.get("doc_change") or "")
    doc_change_reason = str(session_fm.get("doc_change_reason") or "").strip()

    # removed code is counted apart: it needs no spec, but a spec that owned it may now describe what is gone
    gone_owned: dict[str, list[str]] = {}
    for path in gone:
        for it in resolved.get(path, []):
            if has_project_docs and not it["doc"].startswith(f"projects/{project}/"):
                continue
            if path not in gone_owned.setdefault(it["doc"], []):   # one row per node of the spec — count a file once
                gone_owned[it["doc"]].append(path)
    resolved = {p: items for p, items in resolved.items() if p not in gone}
    owners: dict[str, dict] = {}
    for path, items in resolved.items():
        for it in items:
            if has_project_docs and not it["doc"].startswith(f"projects/{project}/"):
                continue
            o = owners.setdefault(it["doc"], {
                "doc": it["doc"], "stem": PurePosixPath(it["doc"]).stem, "id": it["stable_id"],
                "node": it["node"], "nodes": set(), "updated": it["updated"], "status": it["status"],
                "matched": [],
            })
            if it["node"]:
                o["nodes"].add(it["node"])
            o["matched"].append(f"{path} ← {it['kind']}:{it['pattern']}")

    derived_nodes: set[str] = set()
    for o in owners.values():
        derived_nodes |= o["nodes"]
        o["fresh"] = bool(o["updated"]) and o["updated"][:10] >= since
        o["in_kb_updates"] = bool({o["stem"], o["id"]} & kb_updates)
        o["nodes"] = sorted(o["nodes"])
        o["node"] = o["node"] or (o["nodes"][0] if o["nodes"] else "")
    result["owners"] = list(owners.values())
    result["nodes"] = sorted(derived_nodes)

    unowned_paths = unowned_sources(resolved, project, has_project_docs)
    result["unowned"] = unowned_paths
    result["owner_candidates"] = owner_candidates(store, project, unowned_paths) if unowned_paths else []
    result["summary_line"] = summary_line(len(unowned_paths), result["owner_candidates"], 0, len(gone))
    result["info"].append(result["summary_line"])
    need = new_spec_needed(unowned_paths, result["owner_candidates"])
    try:
        from kb.legacy.strata_paths import resolve_tier_p
        tier = resolve_tier_p(project_dir)
    except Exception:  # noqa: BLE001
        tier = None
    try:
        pol = load_coverage_policy(tier.root if tier else None)
    except ValueError as e:
        result["warnings"].append(f"커버리지 등급 무시 — {e}")
        pol = {"grade": "advisory", "exempt": [], "notes": []}
    kept, result["exempt"] = apply_exemptions(need, pol)
    base = load_baseline(tier.root if tier else None)
    result["new_spec_needed"], result["baselined"] = apply_baseline(kept, base)
    exempt_n = sum(len(v) for v in result["exempt"].values())
    base_n = sum(len(v) for v in result["baselined"].values())
    result["summary_line"] = summary_line(len(unowned_paths), result["owner_candidates"], exempt_n, len(gone), base_n)
    result["info"][-1] = result["summary_line"]
    result["info"] += pol["notes"]
    if base is None and pol["grade"] in ("default", "block"):
        result["info"].append("기준선 없음 — 원래 있던 빈틈도 새 위반으로 센다. 저장: kb coverage-gate --project-dir . --write-baseline (DEC-2026-10-31-32)")
    if result["new_spec_needed"]:
        groups = sorted(result["new_spec_needed"].items(), key=lambda kv: (-len(kv[1]), kv[0]))
        result["info"].append("새 명세 필요 — " + ", ".join(f"{m} {len(fs)}" for m, fs in groups))
    if result["exempt"]:
        result["info"].append("면제 — " + ", ".join(f"{r} {len(fs)}" for r, fs in sorted(result["exempt"].items())))
    if result["baselined"]:
        result["info"].append("기준선(원래 있던 빈틈) — " + ", ".join(f"{m} {len(fs)}" for m, fs in sorted(result["baselined"].items())))

    # 영향 반경 후보 (strata DEC-2026-10-28-05): 변경 파일을 import 하는 파일(역방향 1홉, 코드 그래프)의 소유 명세 —
    # 직접 소유 명세에 없는 것만, 경고가 아니라 후보로 낸다
    # 역방향(오더 2026.10.29-04): 지식이 바뀐 쪽에서 다시 확인할 코드 — advisory, 막지 않는다
    kdocs, kdecs = knowledge if knowledge is not None else changed_knowledge(project, since, changed)
    result["recheck"] = recheck_code(store, project, kdocs, kdecs)
    result["info"] += recheck_lines(result["recheck"])
    owned: dict[str, list[str]] = {}
    for path, items in resolved.items():
        for it in items:
            if it["doc"] in owners and path not in owned.setdefault(it["doc"], []):
                owned[it["doc"]].append(path)
    result["desired_shape"] = desired_shape(store, owned, since)
    result["info"] += desired_shape_lines(result["desired_shape"])
    # graded after the desired-shape rows exist: an unjudged implemented plan is graded with the unowned changes
    from kb.gates.grades import render
    g = grade_new_spec(result["new_spec_needed"], pol, tier.root if tier else None, desired=result["desired_shape"])
    result["grade_rc"] = g["rc"]
    result["grades"] = render(g)
    result["info"] += [f"등급 {line}" for line in result["grades"]]
    result["impact"] = impact_candidates(store, project, [p for p in changed if p not in gone], set(owners))
    if result["impact"]["candidates"]:
        head = ", ".join(f"[[{c['stem']}]]" for c in result["impact"]["candidates"][:4])
        result["info"].append(f"영향 반경(import 역방향 1홉) 파일 {result['impact']['files']} · 후보 명세 {len(result['impact']['candidates'])}: {head}")

    result["info"].append(f"변경 파일 {len(changed)} · 소유 명세 {len(owners)} · 미소유 소스 {len(unowned_paths)} · 유도 노드 {len(derived_nodes)}")
    missing_nodes = sorted(derived_nodes - declared_nodes)
    if missing_nodes:
        result["warnings"].append(f"nodes 누락: {', '.join(missing_nodes)} — 세션 frontmatter nodes 에 추가")
    if doc_change == "none" and not doc_change_reason:
        result["warnings"].append("doc_change: none 인데 doc_change_reason 없음 — 빈 값 금지")
    for o in owners.values():
        if o["fresh"] or o["in_kb_updates"] or doc_change == "none":
            continue
        result["warnings"].append(
            f"형상 미갱신: [[{o['stem']}]] (updated {o['updated'] or '-'} < 세션 {since}) — "
            f"갱신하거나 doc_change: none + 사유. 근거: {o['matched'][0]}"
        )
    for o in owners.values():
        if o["in_kb_updates"] and not o["fresh"]:
            result["warnings"].append(f"[[{o['stem']}]] 을 kb_updates 에 적었으나 updated({o['updated'] or '-'}) 가 세션 이전 — updated 스탬프 누락")
    for doc, paths in sorted(gone_owned.items()):
        head = ", ".join(sorted(paths)[:3]) + (" …" if len(paths) > 3 else "")
        result["warnings"].append(f"형상 갱신 필요(코드 삭제): [[{PurePosixPath(doc).stem}]] 이 맡던 파일 {len(paths)}개가 지워짐 — "
                                  f"지운 기능의 설명을 정리하거나 covers 를 줄인다: {head}")
    if unowned_paths:
        head = ", ".join(unowned_paths[:5]) + (" …" if len(unowned_paths) > 5 else "")
        result["warnings"].append(f"미소유 표면 {len(unowned_paths)}건 (소유 명세 없음): {head} — 명세 생성 또는 covers 확장")
    return result


def format_report(result: dict) -> str:
    L = [f"커버리지 게이트 — {result['project']} (since {result['since']})"]
    L += [f"  {i}" for i in result["info"]]
    for o in result["owners"]:
        state = "갱신됨" if o["fresh"] else ("kb_updates" if o["in_kb_updates"] else "미갱신")
        L.append(f"  소유: [[{o['stem']}]] {o['node'] or '(노드 없음)'} — {state} (updated {o['updated'] or '-'})")
    for w in result["warnings"]:
        L.append(f"  WARN[advisory]: {w}")   # 보고만 — 등급을 받는 것은 '등급' 줄(새 명세 필요)뿐 (오더 2026.10.31-04)
    if not result["warnings"] and result["changed"]:
        L.append("  통과 — 경고 없음")
    return "\n".join(L)


# ---------------------------------------------------------------- CLI (same shapes as the legacy scripts)

RESOLVER_DOC = """커버리지 리졸버 — "이 코드 경로를 소유한 명세는 무엇인가" (store 기반)

  coverage resolve <path>...          경로별 소유 문서·노드
  coverage nodes <path>...            경로들이 속한 노드 id 집합
  coverage unowned <path>...          소유 문서가 없는 경로 (미소유 표면)
  coverage docs-to-update <path>...   Builder 주입용 {node, doc, reason} 목록
  coverage node <node-id>             노드의 최종형상 문서(specification·concept) 목록
  옵션: --json  /  --db <store.sqlite>  (기본 $STRATA_VAULT/.kb/store.sqlite)
"""


def _print_resolve(res: dict[str, list[dict]]) -> None:
    for p, items in res.items():
        if not items:
            print(f"{p}\n  (소유 문서 없음 — 미소유 표면)")
            continue
        print(p)
        for it in items:
            node = it["node"] or "(노드 없음)"
            print(f"  {node:36s} {it['doc']}  [{it['kind']}:{it['pattern']}]  updated={it['updated'] or '-'}")


def main_resolver(argv: list[str]) -> int:
    """argv: everything after the program name (legacy kb_coverage.py main took sys.argv)."""
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    db = None
    if "--db" in argv:
        db = argv[argv.index("--db") + 1]
        args = [a for a in args if a != db]
    if not args:
        print(RESOLVER_DOC)
        return 2
    cmd, rest = args[0], args[1:]
    store = get_store(db)

    if cmd == "resolve":
        res = resolve(store, rest)
        print(json.dumps(res, ensure_ascii=False, indent=2)) if as_json else _print_resolve(res)
    elif cmd == "nodes":
        ids = nodes_for(store, rest)
        print(json.dumps(ids, ensure_ascii=False)) if as_json else print("\n".join(ids) or "(없음)")
    elif cmd == "unowned":
        u = unowned(store, rest)
        print(json.dumps(u, ensure_ascii=False)) if as_json else print("\n".join(u) or "(전부 소유됨)")
    elif cmd == "docs-to-update":
        d = docs_to_update(store, rest)
        if as_json:
            print(json.dumps(d, ensure_ascii=False, indent=2))
        else:
            for e in d:
                print(f"- node: {e['node'] or '(없음)'}\n  doc: \"{e['doc']}\"   # id: {e['id'] or '-'}\n  reason: \"{e['reason']}\"")
            if not d:
                print("(소유 문서 없음)")
    elif cmd == "node":
        if not rest:
            print("사용법: coverage node <node-id>")
            return 2
        o = owners_of_node(store, rest[0])
        if as_json:
            print(json.dumps(o, ensure_ascii=False, indent=2))
        else:
            for e in o:
                cov = ", ".join(f"{k} {v}" for k, v in e["covers"].items()) or "covers 없음"
                print(f"{e['type']:14s} {e['doc']}  ({e['status']}, updated={e['updated'] or '-'}, {cov})")
            if not o:
                print("(최종형상 문서 없음)")
    else:
        print(RESOLVER_DOC)
        return 2
    return 0


def main_gate(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="coverage-gate", description="세션 종료 커버리지 게이트 (경고만)")
    ap.add_argument("--project-dir", required=True)
    def since_arg(v: str) -> str:
        try:
            return _since_date(v)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e))
    ap.add_argument("--since", type=since_arg,
                    help="세션 시작일 YYYY-MM-DD (기본: 세션 파일 created 또는 오늘). 커밋 범위가 아니다")
    ap.add_argument("--session", help="세션 문서(핸드오프·ledger) — nodes/kb_updates/doc_change 대조")
    ap.add_argument("--files", nargs="*", help="변경 파일을 직접 지정 (git 대신)")
    ap.add_argument("--db", help="store.sqlite 경로")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--save", help="보고와 함께 결과 JSON(nodes·summary_line 포함)을 이 파일에 쓴다 — 핸드오프가 게이트를 한 번만 돌리게")
    ap.add_argument("--nodes-only", action="store_true", help="유도된 노드 id JSON 배열만 출력 (핸드오프 prefill 용)")
    ap.add_argument("--summary-line", action="store_true", help="'명세 없는 변경 코드 N · 후보 M' 한 줄만 출력 (핸드오프 본문용)")
    ap.add_argument("--divergence-inbox", action="store_true",
                    help="바라는 형상 대조의 재대조 행을 vault projects/<p>/_meta/divergence-inbox.yaml 의 판정 요청으로 쌓는다 (DEC-2026-10-31-35)")
    ap.add_argument("--write-baseline", action="store_true",
                    help="지금 소유 명세가 없는 추적 소스 파일을 Tier P coverage-baseline.yaml 에 저장한다 — 이 파일들은 등급을 받지 않는다 (DEC-2026-10-31-32)")
    ap.add_argument("--enforce", action="store_true", help="profile.yaml enforcement.coverage 의 default·block 등급 결과로 종료 코드를 낸다(미해결이면 2). 기본은 0 — 핸드오프는 막지 않는다 (DEC-2026-10-29-08)")
    ap.add_argument("--covers-candidates", action="store_true",
                    help="소유 명세 없는 변경 소스의 covers 후보(이웃 투표)를 vault projects/<p>/_meta/covers-candidates.yaml 에 병합 (source: impact)")
    args = ap.parse_args(argv)

    if args.write_baseline:
        from kb.legacy.strata_paths import resolve_tier_p
        try:
            tier = resolve_tier_p(args.project_dir)
        except ValueError as e:
            print(f"기준선 저장 실패 — Tier P 를 찾지 못함: {e}", file=sys.stderr)
            return 2
        path, n = write_baseline(args.project_dir, tier.root, get_store(args.db))
        print(f"기준선 저장: {path} — 소유 명세 없는 소스 {n}개")
        return 0
    fm = read_session_fm(args.session) if args.session else {}
    res = run_gate(args.project_dir, fm, args.files, args.since, args.db)
    if args.covers_candidates:
        from kb import vault_root
        vault = vault_root()
        written = write_impact_inbox(vault, res["project"], res.get("owner_candidates") or []) if vault else None
        res["inbox"] = written
        if not args.json and not args.nodes_only and not args.summary_line:
            print(f"covers 후보 Inbox: {written or '(후보 없음 — 쓰지 않음)'}", file=sys.stderr)
    if args.divergence_inbox:
        from kb import vault_root
        from kb.gates.divergence import from_gate
        vault = vault_root()
        res["divergence_added"] = from_gate(vault, res["project"], res.get("desired_shape") or [], res["since"]) if vault else []
        if not args.json and not args.nodes_only and not args.summary_line:
            print(f"판정 요청 추가: {', '.join(res['divergence_added']) or '없음'}", file=sys.stderr)
    if args.save:
        Path(args.save).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    if args.nodes_only:
        print(json.dumps(res["nodes"], ensure_ascii=False))
    elif args.summary_line:
        print(res["summary_line"])
    elif args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(format_report(res))
    return res.get("grade_rc", 0) if args.enforce else 0
