"""Planning impact assessment (DEC-2026-11-01-16, MB-strata-kit-2026-019).

Starts from the topic nodes a planning declares (frontmatter `nodes` of the refined documents of a bundle, or of one
planning document) and gathers what the planning touches, from the store:

  specifications  final-shape documents (specification · concept) of each node and its child nodes
  code            files those documents cover (covers paths · symbols)
  dependents      code that depends on those files, --depth hops (default 1), and the tests that import them
  decisions       DEC notes on the same nodes, current and superseded apart
  other planning  planning documents elsewhere that declare the same nodes

A bundle gets audit/impact.md (generated, rewritten each run, evidence layer — never injected); a single planning
document is printed only. What to do about the impact — change a specification, supersede a decision — is the
person's call.

  python3 -m kb planning impact <bundle-dir | planning.md> [--depth 1] [--print]
"""
from __future__ import annotations

from datetime import date
from pathlib import Path, PurePosixPath

LIST_TOP = 30


def _nodes_of(paths: list[Path]) -> list[str]:
    from kb.planning import split_frontmatter
    out: list[str] = []
    for p in paths:
        fm, _, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        raw = fm.get("nodes") or []
        for n in (raw if isinstance(raw, list) else [raw]):
            if str(n) and str(n) not in out:
                out.append(str(n))
    return out


def _covered_files(store, doc_path: str) -> list[str]:
    """Code file ids a document's covers reach: a directory target expands to the files under it, a symbol to its file."""
    files: list[str] = []
    for e in store.neighbors(f"doc:{doc_path}", kind="covers", direction="out"):
        t = e.dst
        if ":symbols:" in t:
            files += [x.dst for x in store.neighbors(t, kind="member_of", direction="out")]
        elif t.endswith("/"):
            rows = store.conn.execute("SELECT id FROM nodes WHERE kind = 'code' AND id LIKE ? AND json_extract(payload_json, '$.kind') = 'file'",
                                      (t.replace("%", r"\%") + "%",)).fetchall()
            files += [r[0] for r in rows]
        elif store.get(t):
            files.append(t)
    return list(dict.fromkeys(files))


def assess(vault: Path, store, target: Path, depth: int = 1) -> dict:
    from kb.code import impact as code_impact
    from kb.gates.coverage import owners_of_node
    from kb.planning import is_bundle, refined_docs
    from kb.views.node_pages import load_decisions, load_toc
    target = target.resolve()
    rel = target.relative_to(vault.resolve())
    if len(rel.parts) < 4 or rel.parts[0] != "projects" or rel.parts[2] != "planning":
        raise ValueError(f"{rel} 는 projects/<p>/planning/ 아래가 아니다")
    project = rel.parts[1]
    project_dir = vault / "projects" / project
    bundle = is_bundle(target)
    docs = refined_docs(target) if bundle else [target]
    declared = _nodes_of(docs)
    toc_nodes, alias = load_toc(project_dir)
    known = [alias[n] for n in declared if n in alias]
    unknown = [n for n in declared if n not in alias]
    scope = list(dict.fromkeys(known + [t.id for t in toc_nodes for k in known if t.id.startswith(k + ".")]))
    specs: list[dict] = []
    for nid in scope:
        for o in owners_of_node(store, nid):
            if o["doc"] not in {s["doc"] for s in specs}:
                specs.append({**o, "node": nid})
    files: list[str] = []
    for s in specs:
        s["files"] = _covered_files(store, s["doc"])
        files += [f for f in s["files"] if f not in files]
    imp = code_impact(store, files, depth) if files else {"impacted": [], "tests": []}
    decs_by_node, superseded = load_decisions(project_dir, alias)
    decisions, seen = [], set()
    for nid in scope:
        for d in decs_by_node.get(nid, []):
            if d["rec"] not in seen:
                seen.add(d["rec"])
                decisions.append({**d, "node": nid, "superseded": d["rec"] in superseded})
    own = {str(p.resolve().relative_to(vault.resolve())) for p in docs}
    others = []
    for n in store.query(path_prefix=f"projects/{project}/planning/"):
        nn = [alias.get(str(x), str(x)) for x in (n.payload.get("nodes") or [])]
        if n.path in own or (bundle and n.path.startswith(str(rel) + "/")):
            continue
        hit = sorted(set(nn) & set(scope))
        if hit:
            others.append({"path": n.path, "title": n.title, "nodes": hit, "status": n.status})
    others.sort(key=lambda o: o["path"])
    return {"project": project, "target": str(rel), "bundle": bundle, "docs": sorted(own), "declared": declared,
            "unknown_nodes": unknown, "scope": scope, "specs": specs,
            "files": [f.split(":", 3)[3] for f in files], "depth": depth,
            "dependents": imp["impacted"], "tests": imp["tests"], "decisions": decisions, "others": others}


def _module(path: str) -> str:
    return "/".join(PurePosixPath(path).parts[:2])


def render(r: dict, today: date) -> str:
    cur = [d for d in r["decisions"] if not d["superseded"]]
    L = ["---", "title: \"영향 평가 — " + r["target"].split("/")[-1] + "\"", "type: report", "category: audit",
         f"project: {r['project']}", f"generated: {today.isoformat()}", "---", "",
         "> GENERATED — `python3 -m kb planning impact` 가 다시 쓴다(DEC-2026-11-01-16). 손으로 고치지 않는다. 영향의 판단은 사람이 한다.", "",
         f"# 영향 평가 — {r['target']}", "",
         f"주제 노드 {len(r['scope'])} · 명세 {len(r['specs'])} · 맡은 코드 {len(r['files'])} · 기대는 코드 {len(r['dependents'])}"
         f"(깊이 {r['depth']}) · 시험 {len(r['tests'])} · 현행 결정 {len(cur)} · 같은 노드의 다른 기획 {len(r['others'])}", ""]
    L += ["## 주제 노드", ""]
    if not r["declared"]:
        L.append("- (없음) — 정리본 frontmatter `nodes` 가 비어 있어 평가할 출발점이 없다. toc.yaml 의 노드 id 를 적는다.")
    L += [f"- {n}" for n in r["scope"]]
    L += [f"- {n} — toc.yaml 에 없는 노드(평가에서 빠짐)" for n in r["unknown_nodes"]]
    L += ["", "## 명세", ""]
    L += [f"- [[{PurePosixPath(s['doc']).stem}]] ({s['type']}, {s['status'] or '?'}, 노드 {s['node']}) — 맡은 파일 {len(s['files'])}"
          for s in r["specs"]] or ["- (없음) — 이 노드에 최종형상 문서가 없다"]
    L += ["", "## 맡은 코드", ""]
    by: dict[str, int] = {}
    for f in r["files"]:
        by[_module(f)] = by.get(_module(f), 0) + 1
    L += [f"- {m} — 파일 {c}" for m, c in sorted(by.items(), key=lambda x: (-x[1], x[0]))] or ["- (없음) — 명세에 covers 가 없거나 코드가 색인되지 않았다"]
    def grouped(paths: list[str], empty: str) -> list[str]:
        cnt: dict[str, int] = {}
        for x in paths:
            cnt[_module(x)] = cnt.get(_module(x), 0) + 1
        rows = sorted(cnt.items(), key=lambda x: (-x[1], x[0]))
        out = [f"- {m} — {c}" for m, c in rows[:LIST_TOP]] or [empty]
        if len(rows) > LIST_TOP:
            out.append(f"- … 그 밖 모듈 {len(rows) - LIST_TOP} ({sum(c for _, c in rows[LIST_TOP:])} 파일)")
        return out
    L += ["", f"## 기대는 코드 (깊이 {r['depth']}, 모듈별 파일 수)", ""]
    L += grouped([d["file"] for d in r["dependents"]], "- (없음)")
    L += ["", "## 시험 (모듈별 파일 수)", ""]
    L += grouped(r["tests"], "- (없음) — 맡은 코드를 import 하는 시험 파일이 색인에 없다")
    L += ["", "## 결정", ""]
    L += [f"- [[{d['stem']}]] {d['title']} ({d['created']}, 노드 {d['node']})" for d in cur] or ["- (없음)"]
    old = [d for d in r["decisions"] if d["superseded"]]
    if old:
        L.append(f"- 대체된 결정 {len(old)}: " + ", ".join(f"[[{d['stem']}]]" for d in old))
    L += ["", "## 같은 노드의 다른 기획", ""]
    L += [f"- [[{PurePosixPath(o['path']).stem}]] ({o['status'] or '?'}, 노드 {', '.join(o['nodes'])})" for o in r["others"][:LIST_TOP]] or ["- (없음)"]
    if len(r["others"]) > LIST_TOP:
        L.append(f"- … 그 밖 {len(r['others']) - LIST_TOP}")
    return "\n".join(L) + "\n"


def run(target: Path, depth: int = 1, print_only: bool = False, today: date | None = None) -> tuple[int, str]:
    from kb import vault_root
    from kb.gates.coverage import get_store
    vault = vault_root()
    if not vault:
        return 2, "STRATA_VAULT 없음"
    if not target.exists():
        return 2, f"없음: {target}"
    r = assess(vault, get_store(), target, depth)
    text = render(r, today or date.today())
    if r["bundle"] and not print_only:
        out = target / "audit" / "impact.md"
        out.write_text(text, encoding="utf-8")
        return 0, f"씀: {out}\n" + next(l for l in text.splitlines() if l.startswith("주제 노드 "))
    return 0, text
