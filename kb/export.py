"""kb export — the injection layer as a folder that outside tools read (MB-strata-kit-2026-044, DEC-2026-11-01-06).

Copies, under their vault-relative paths, only what may be injected:
  knowledge   projects/<p>/knowledge-base/** and projects/<p>/overview.md (as-built documents)
  planning    refined documents of planning bundles (kb planning boundary --list; DEC-2026-11-01-04·05)
  decision    decision notes projects/<p>/decisions/DEC-*.md
and writes manifest.json (path · role · title · project · updated · sha256) and, per project with a code graph,
code-graph/<p>.md and .json (modules · dependencies between modules · owning documents).
Never exported: sources and audit of planning, original planning documents, sessions, tasks, reviews, generated
pages, and every path share.yaml lists under never — the same boundary as sharing.

  python3 -m kb export [--project P ...] [--out DIR] [--dry-run]     default DIR: $STRATA_VAULT/outputs/export/<date>/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path, PurePosixPath

import yaml

from kb import vault_root


# -- share.yaml globs (same semantics as the share runner: ** crosses directories, * one level, {a,b} alternatives)

def expand_braces(pat: str) -> list[str]:
    m = re.search(r"\{([^{}]*)\}", pat)
    if not m:
        return [pat]
    out = []
    for alt in m.group(1).split(","):
        out.extend(expand_braces(pat[: m.start()] + alt + pat[m.end():]))
    return out


def glob_to_re(pat: str) -> re.Pattern:
    i, out = 0, "^"
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"; i += 3; continue
        if pat.startswith("**", i):
            out += ".*"; i += 2; continue
        c = pat[i]
        out += "[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c)
        i += 1
    return re.compile(out + "$")


def never_matcher(vault: Path):
    p = vault / "_meta" / "share.yaml"
    pats = ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("never") or []) if p.is_file() else []
    res = [glob_to_re(x) for raw in pats for x in expand_braces(str(raw))]
    return lambda rel: any(r.match(rel) for r in res)


# -- selection -----------------------------------------------------------------

def role_for(n) -> str | None:
    """knowledge · planning · decision, or None when the document is not part of the injection layer."""
    parts = n.path.split("/")
    if len(parts) < 3 or parts[0] != "projects":
        return None
    if parts[2] == "decisions" and re.fullmatch(r"DEC-[\d-]+\.md", parts[-1]):
        return "decision"                       # generated notes: not indexed for search, still the decision layer
    if not n.payload.get("indexed", True):
        return None
    cat = n.payload.get("category") or ""
    if cat == "planning":
        return "planning" if n.payload.get("planning_layer") == "refined" else None
    if cat in ("archive", "review"):
        return None
    if parts[2] == "knowledge-base" or (len(parts) == 3 and parts[2] == "overview.md"):
        return "knowledge"
    return None


def select(store, vault: Path, projects: list[str] | None = None) -> list[dict]:
    never = never_matcher(vault)
    out = []
    for n in store.query(kind="doc"):
        if projects and n.project not in projects:
            continue
        role = role_for(n)
        if not role or never(n.path) or not (vault / n.path).is_file():
            continue
        out.append({"path": n.path, "role": role, "title": n.title, "project": n.project,
                    "type": n.payload.get("type") or "", "updated": n.updated or ""})
    return sorted(out, key=lambda d: d["path"])


# -- code graph summary ----------------------------------------------------------

def module_key(rel: str, is_dir: bool) -> str:
    """The module of a path (DEC-2026-10-29-03: the first two segments) taken from the file's directory."""
    d = PurePosixPath(rel.rstrip("/")) if is_dir else PurePosixPath(rel).parent
    parts = [p for p in d.parts if p != "."]
    return "/".join(parts[:2]) or "(root)"


def code_summary(store, project: str) -> dict | None:
    nodes = [n for n in store.query(kind="code", project=project) if ":paths:" in n.id]
    if not nodes:
        return None
    mods: dict[str, dict] = defaultdict(lambda: {"files": 0, "lines": 0, "tests": 0, "depends_on": defaultdict(int), "owners": set()})
    kind_of = {}
    for n in nodes:
        is_dir = n.payload.get("kind") == "dir"
        kind_of[n.id] = module_key(n.path, is_dir)
        if not is_dir:
            m = mods[kind_of[n.id]]
            m["files"] += 1
            m["lines"] += int(n.payload.get("lines") or 0)
            m["tests"] += 1 if n.payload.get("test") else 0
    for (src, dst) in store.conn.execute("SELECT src, dst FROM edges WHERE kind = 'imports' AND src LIKE ?", (f"code:{project}:paths:%",)):
        a, b = kind_of.get(src), kind_of.get(dst)
        if a and b and a != b:
            mods[a]["depends_on"][b] += 1
    for (src, dst) in store.conn.execute("SELECT src, dst FROM edges WHERE kind = 'covers' AND dst LIKE ?", (f"code:{project}:paths:%",)):
        m = kind_of.get(dst)
        if m and m in mods:
            mods[m]["owners"].add(src.split(":", 1)[1] if src.startswith("doc:") else src)
    return {"project": project, "modules": [
        {"module": k, "files": v["files"], "lines": v["lines"], "tests": v["tests"],
         "depends_on": [{"module": d, "imports": c} for d, c in sorted(v["depends_on"].items())],
         "owning_documents": sorted(v["owners"])}
        for k, v in sorted(mods.items()) if v["files"]]}


def code_summary_md(s: dict) -> str:
    out = [f"# Code graph — {s['project']}", "",
           "Modules (first two path segments), their size, the modules they import and the documents whose covers own them.", "",
           "| Module | Files | Lines | Tests | Depends on | Owning documents |", "|---|---:|---:|---:|---|---|"]
    for m in s["modules"]:
        deps = ", ".join(f"{d['module']} ({d['imports']})" for d in m["depends_on"]) or "—"
        owners = ", ".join(m["owning_documents"]) or "none"
        out.append(f"| {m['module']} | {m['files']} | {m['lines']} | {m['tests']} | {deps} | {owners} |")
    return "\n".join(out) + "\n"


# -- write ---------------------------------------------------------------------

def export(store, vault: Path, out: Path, projects: list[str] | None = None) -> dict:
    docs = select(store, vault, projects)
    out.mkdir(parents=True, exist_ok=True)
    for d in docs:
        src, dst = vault / d["path"], out / d["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        d["sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
    graphs = []
    never = never_matcher(vault)
    for p in sorted(projects or {d["project"] for d in docs} | {r[0] for r in store.conn.execute("SELECT DISTINCT project FROM nodes WHERE kind = 'code'")}):
        if never(f"projects/{p}/knowledge-base/_.md"):   # a project whose knowledge never leaves keeps its code graph too
            continue
        s = code_summary(store, p)
        if not s:
            continue
        g = out / "code-graph"
        g.mkdir(exist_ok=True)
        (g / f"{p}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        (g / f"{p}.md").write_text(code_summary_md(s), encoding="utf-8")
        graphs.append(f"code-graph/{p}.md")
    manifest = {"generated": date.today().isoformat(), "decision": "DEC-2026-11-01-06",
                "boundary": "share.yaml never + planning refined only", "documents": docs, "code_graphs": graphs}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb export", description="the injection layer as a folder (DEC-2026-11-01-06)")
    ap.add_argument("--project", action="append", help="limit to these projects (repeat)")
    ap.add_argument("--out", help="output folder (default $STRATA_VAULT/outputs/export/<date>/)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be exported, write nothing")
    a = ap.parse_args(argv)
    v = vault_root()
    if not v:
        print("STRATA_VAULT 가 없음", file=sys.stderr)
        return 2
    from kb.engine import ensure_fresh_store
    store = ensure_fresh_store()
    if a.dry_run:
        docs = select(store, v, a.project)
        counts = defaultdict(int)
        for d in docs:
            counts[d["role"]] += 1
            print(f"{d['role']:9} {d['path']}")
        print(f"합계 {len(docs)} — " + " · ".join(f"{k} {n}" for k, n in sorted(counts.items())))
        return 0
    out = Path(a.out) if a.out else v / "outputs" / "export" / date.today().isoformat()
    m = export(store, v, out, a.project)
    counts = defaultdict(int)
    for d in m["documents"]:
        counts[d["role"]] += 1
    print(f"내보냄 → {out}: 문서 {len(m['documents'])} (" + " · ".join(f"{k} {n}" for k, n in sorted(counts.items()))
          + f"), 코드 그래프 {len(m['code_graphs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
