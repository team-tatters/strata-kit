"""python3 -m kb code — the graph questions of strata DEC-2026-10-28-05 answered from the store's code provider.

  deps <file>            what the file imports (extracted · inferred), one hop
  impact <file…>         who depends on the files, transitively (--depth), and the specifications that own them (covers)
  tests-for <file>       test files that import the file (inferred `tests` edges)
  symbol <Name>          where a type-level symbol is defined and which documents cover it
  owner-gate             strata DEC-2026-10-28-05 gate: over the last --prs merge commits of --repo, hide the changed
                         files' covers and ask whether their import neighbours' owner votes name the human-written owner
Files are repo-relative paths; --project names the repo (default: the only project that has the file).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import deque
from pathlib import Path, PurePosixPath

from kb import vault_root
from kb.engine import ensure_fresh_store
from kb.store import SqliteStore


def _find_file(store: SqliteStore, rel: str, project: str | None) -> str | None:
    rel = rel.strip().lstrip("./")
    if project:
        nid = f"code:{project}:paths:{rel}"
        return nid if store.get(nid) else None
    rows = store.conn.execute("SELECT id FROM nodes WHERE kind = 'code' AND path = ? AND json_extract(payload_json, '$.kind') = 'file'", (rel,)).fetchall()
    if len(rows) == 1:
        return rows[0][0]
    if len(rows) > 1:
        print(f"ambiguous: {rel} exists in {[r[0].split(':')[1] for r in rows]} — pass --project", file=sys.stderr)
    return None


def _owners(store: SqliteStore, file_id: str) -> list[dict]:
    """Documents whose covers name the file's directory (any ancestor) or a symbol defined in the file."""
    project, rel = file_id.split(":")[1], file_id.split(":", 3)[3]
    targets = []
    d = str(PurePosixPath(rel).parent)
    while d and d != ".":
        targets.append(f"code:{project}:paths:{d}/")
        d = str(PurePosixPath(d).parent)
    for e in store.neighbors(file_id, kind="member_of", direction="in"):
        if e.src.startswith(f"code:{project}:symbols:"):
            targets.append(e.src)
    seen, out = set(), []
    for t in targets:
        for e in store.neighbors(t, kind="covers", direction="in"):
            if e.src in seen:
                continue
            seen.add(e.src)
            n = store.get(e.src)
            out.append({"doc": e.src.split(":", 1)[1], "title": n.title if n else "", "via": t.split(":", 2)[2]})
    return out


def deps(store: SqliteStore, file_id: str) -> list[dict]:
    return [{"to": e.dst.split(":", 3)[3], "confidence": e.confidence} for e in store.neighbors(file_id, kind="imports", direction="out")]


def impact(store: SqliteStore, file_ids: list[str], depth: int = 3) -> dict:
    level = {f: 0 for f in file_ids}
    q = deque(file_ids)
    while q:
        cur = q.popleft()
        if level[cur] >= depth:
            continue
        for e in store.neighbors(cur, kind="imports", direction="in"):
            if e.src not in level:
                level[e.src] = level[cur] + 1
                q.append(e.src)
        # a directory target (wildcard import) reaches the importer of the whole package
        d = str(PurePosixPath(cur.split(":", 3)[3]).parent)
        if d and d != ".":
            dir_id = f"{cur.rsplit(':', 1)[0]}:{d}/"
            for e in store.neighbors(dir_id, kind="imports", direction="in"):
                if e.src not in level:
                    level[e.src] = level[cur] + 1
                    q.append(e.src)
    files = sorted((f for f in level if f not in file_ids), key=lambda f: (level[f], f))
    owners, seen = [], set()
    for f in file_ids + files:
        for o in _owners(store, f):
            if o["doc"] not in seen:
                seen.add(o["doc"])
                owners.append(o)
    tests = sorted({e.src.split(":", 3)[3] for f in file_ids + files for e in store.neighbors(f, kind="tests", direction="in")})
    return {"seed": [f.split(":", 3)[3] for f in file_ids],
            "impacted": [{"file": f.split(":", 3)[3], "depth": level[f]} for f in files],
            "owning_docs": owners, "tests": tests}


def module_of(rel: str) -> str:
    """The module a repository path belongs to (DEC-2026-10-29-03): its first two segments, e.g. service/catalog-api."""
    return "/".join(PurePosixPath(rel).parts[:2])


def importers(store: SqliteStore, file_id: str) -> int:
    """How many files import the file, directly or through its directory (wildcard imports)."""
    project, rel = file_id.split(":")[1], file_id.split(":", 3)[3]
    n = len(store.neighbors(file_id, kind="imports", direction="in"))
    d = str(PurePosixPath(rel).parent)
    if d and d != ".":
        n += len(store.neighbors(f"code:{project}:paths:{d}/", kind="imports", direction="in"))
    return n


def owner_votes(store: SqliteStore, project: str, file_ids: list[str], same_module: bool = False,
                hub_min_in: int | None = None) -> dict:
    """truth: documents whose covers name the files; ranked: owner documents of the files' 1-hop import neighbours
    (both directions, wildcard imports through the directory), ordered by how many neighbours vote for them.
    The files' own covers are not consulted for the ranking — that is what the gate tests.
    Filters (DEC-2026-10-29-03, off by default so the owner-gate measurement stays as it was): same_module keeps only
    neighbours in the files' modules; hub_min_in drops neighbours imported by at least that many files (shared hubs
    such as common type or error-code packages, which every file imports and which say nothing about ownership)."""
    truth: set[str] = set()
    for f in file_ids:
        truth |= {o["doc"] for o in _owners(store, f)}
    neighbours: set[str] = set()
    for f in file_ids:
        neighbours |= {e.src for e in store.neighbors(f, kind="imports", direction="in")}
        neighbours |= {e.dst for e in store.neighbors(f, kind="imports", direction="out") if not e.dst.endswith("/")}
        d = str(PurePosixPath(f.split(":", 3)[3]).parent)
        if d and d != ".":
            neighbours |= {e.src for e in store.neighbors(f"code:{project}:paths:{d}/", kind="imports", direction="in")}
    neighbours -= set(file_ids)
    skipped = {"other_module": 0, "hub": 0}
    if same_module:
        mods = {module_of(f.split(":", 3)[3]) for f in file_ids}
        kept = {n for n in neighbours if module_of(n.split(":", 3)[3]) in mods}
        skipped["other_module"] = len(neighbours - kept)
        neighbours = kept
    if hub_min_in:
        hubs = {n for n in neighbours if importers(store, n) >= hub_min_in}
        skipped["hub"] = len(hubs)
        neighbours -= hubs
    votes: dict[str, int] = {}
    voters: dict[str, list[str]] = {}
    for n in sorted(neighbours):
        for o in _owners(store, n):
            votes[o["doc"]] = votes.get(o["doc"], 0) + 1
            voters.setdefault(o["doc"], []).append(n.split(":", 3)[3])
    ranked = sorted(votes, key=lambda d_: (-votes[d_], d_))
    return {"truth": sorted(truth), "ranked": ranked, "votes": votes, "voters": voters, "neighbours": len(neighbours),
            "skipped": skipped}


def owner_gate(store: SqliteStore, project: str, repo: Path, prs: int = 20, branch: str = "main") -> dict:
    """The DEC-2026-10-28-05 gate measured with the store's own code graph: one row per first-parent merge commit."""
    log = subprocess.run(["git", "log", "--merges", "--first-parent", f"-{prs}", "--format=%h\t%ad\t%s", "--date=short", branch],
                         cwd=repo, capture_output=True, text=True, check=True).stdout.strip().splitlines()
    rows = []
    for line in log:
        h, d, subj = line.split("\t", 2)
        files = subprocess.run(["git", "diff", "--name-only", f"{h}^1", h], cwd=repo, capture_output=True, text=True, check=True).stdout.split()
        ids = [i for i in (f"code:{project}:paths:{f}" for f in files) if store.get(i)]
        v = owner_votes(store, project, ids) if ids else {"truth": [], "ranked": [], "neighbours": 0}
        truth, ranked = set(v["truth"]), v["ranked"]
        m = re.search(r"#(\d+)", subj)
        rows.append({"commit": h, "pr": f"#{m.group(1)}" if m else h, "date": d, "changed": len(files), "in_graph": len(ids),
                     "neighbours": v["neighbours"], "truth": [PurePosixPath(t).stem for t in v["truth"]],
                     "top": [PurePosixPath(p).stem for p in ranked[:5]],
                     "hit_any": bool(truth & set(ranked)), "hit1": bool(ranked) and ranked[0] in truth, "hit3": bool(truth & set(ranked[:3]))})
    judged = [r for r in rows if r["truth"]]
    return {"project": project, "branch": branch, "rows": rows,
            "summary": {"prs": len(rows), "with_code": sum(1 for r in rows if r["in_graph"]), "judgeable": len(judged),
                        "hit_any": sum(r["hit_any"] for r in judged), "hit1": sum(r["hit1"] for r in judged), "hit3": sum(r["hit3"] for r in judged),
                        "passes": len(judged) > 0 and sum(r["hit3"] for r in judged) * 2 > len(judged)}}


def tests_for(store: SqliteStore, file_id: str) -> list[str]:
    return sorted(e.src.split(":", 3)[3] for e in store.neighbors(file_id, kind="tests", direction="in"))


def symbol(store: SqliteStore, name: str, project: str | None) -> list[dict]:
    rows = store.conn.execute("SELECT id FROM nodes WHERE kind = 'code' AND id LIKE ? ESCAPE '\\'", (f"code:%:symbols:{name}".replace("_", "\\_"),)).fetchall()
    out = []
    for (nid,) in rows:
        if project and nid.split(":")[1] != project:
            continue
        n = store.get(nid)
        covered = [e.src.split(":", 1)[1] for e in store.neighbors(nid, kind="covers", direction="in")]
        out.append({"project": nid.split(":")[1], "defs": n.payload.get("defs", []), "covered_by": covered})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb code", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["deps", "impact", "tests-for", "symbol", "owner-gate"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--project", default=None)
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--repo", default=None, help="owner-gate: the git checkout of --project")
    ap.add_argument("--prs", type=int, default=20, help="owner-gate: merge commits to sample")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--vault", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve() if a.vault else vault_root()
    if vault is None:
        print("STRATA_VAULT not set and --vault not given", file=sys.stderr)
        return 2
    store = ensure_fresh_store(Path(a.db).resolve() if a.db else None, vault=vault)
    try:
        if a.cmd == "owner-gate":
            if not (a.project and a.repo):
                print("owner-gate needs --project and --repo", file=sys.stderr)
                return 2
            result = owner_gate(store, a.project, Path(a.repo).resolve(), a.prs, a.branch)
        elif a.cmd == "symbol":
            result = symbol(store, a.args[0], a.project)
        elif not a.args:
            print(f"{a.cmd} needs a file", file=sys.stderr)
            return 2
        else:
            ids = []
            for f in a.args:
                nid = _find_file(store, f, a.project)
                if not nid:
                    print(f"not in the code graph: {f}", file=sys.stderr)
                    return 1
                ids.append(nid)
            if a.cmd == "deps":
                result = deps(store, ids[0])
            elif a.cmd == "tests-for":
                result = tests_for(store, ids[0])
            else:
                result = impact(store, ids, a.depth)
    finally:
        store.close()
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "owner-gate":
        for r in result["rows"]:
            print(f"  {r['pr']:8} {r['date']} changed {r['changed']:3} in-graph {r['in_graph']:3} neighbours {r['neighbours']:5}  "
                  f"truth {r['truth'] or '-'}  top3 {r['top'][:3]}  top1={'Y' if r['hit1'] else 'n'} top3={'Y' if r['hit3'] else 'n'}")
        s_ = result["summary"]
        print(f"{s_['prs']} merge commits · {s_['with_code']} with code in the graph · {s_['judgeable']} judgeable (covers exist) · "
              f"hit any {s_['hit_any']} · top-1 {s_['hit1']} · top-3 {s_['hit3']} → gate {'PASSES' if s_['passes'] else 'FAILS'} (top-3 over half)")
    elif a.cmd == "deps":
        for r in result:
            print(f"  {r['to']}  ({r['confidence']})")
        print(f"{len(result)} imports")
    elif a.cmd == "tests-for":
        print("\n".join(f"  {t}" for t in result) or "  (none)")
    elif a.cmd == "symbol":
        for r in result:
            for d in r["defs"]:
                print(f"  {r['project']}: {d['file']}:{d['line']} ({d['type']})")
            print(f"  covered by: {', '.join(r['covered_by']) or '(no document)'}")
        if not result:
            print("  (no such symbol)")
    else:
        for r in result["impacted"]:
            print(f"  {'  ' * (r['depth'] - 1)}{r['file']}")
        print(f"{len(result['impacted'])} impacted files (depth ≤ {a.depth}); tests: {len(result['tests'])}")
        for o in result["owning_docs"]:
            print(f"  owner: {o['doc']} — {o['title']} (via {o['via']})")
        if not result["owning_docs"]:
            print("  owner: (no specification covers these files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
