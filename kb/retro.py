"""Retrospective bundle (order 2026.10.30-03, DEC-2026-10-30-05): for a period and a project, the decisions (with the
alternatives that lost, background and the supersede chain), reviews, session handoffs and measurements, each as a
markdown file that reads on its own — ready to upload to NotebookLM and talk through.

  python3 -m kb retro-bundle --project P --from YYYY-MM-DD --to YYYY-MM-DD [--node N] [--query Q]
                             [--project-dir DIR] [--name NAME] [--force] [--dry-run]
  python3 -m kb retro-bundle --project P --decision DEC-id [--from D --to D] ...

--decision starts from one decision (DEC-2026-10-30-07): the decision and its supersede chain both ways, and only the
reviews and sessions whose decisions_made names a decision of that chain (a mention in the body is not enough —
DEC-2026-10-31-01). The period is optional then. Decision ids in the table of contents carry their titles.
The table of contents lists every item with facts from the records (date, nodes, supersede relation, linked reviews),
never a summary or the conclusion — the retrospective asks before it says anything.

Output: $STRATA_VAULT/outputs/retro/<name>/ (default name <from>_<to>-<project>[-<node>][-<query>]). The bundle is a
regenerable copy: outside the index (kb/docrules.py discovers no outputs/), never edited by hand. An existing folder is
not written again without --force, and files the bundle did not write are never removed (rec.data.soft-delete-only).
Wikilinks become the target's title, so no file depends on the vault. Sources are only read.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from kb.decisions import _dec_ids, derive_status
from kb.docrules import parse_frontmatter

FILES = ("00-목차.md", "01-결정.md", "02-리뷰.md", "03-세션.md", "04-측정.md")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _in(value, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    d = _day(value)
    return d is not None and (start is None or start <= d) and (end is None or d <= end)


def _chain(records, rid: str) -> set[str]:
    """rid and every decision it replaced or was replaced by, through any number of steps."""
    edges: dict[str, set[str]] = {}
    for _, b in records:
        for old in _dec_ids(b.get("supersedes")):
            edges.setdefault(str(b["id"]), set()).add(old)
            edges.setdefault(old, set()).add(str(b["id"]))
    seen, todo = {rid}, [rid]
    while todo:
        for n in edges.get(todo.pop(), ()):
            if n not in seen:
                seen.add(n)
                todo.append(n)
    return seen


def _names(fm: dict, ids: set[str]) -> bool:
    return any(i in ids for i in _dec_ids(fm.get("decisions_made")))


SEP = re.compile(r": | — ")


def _cap(text: str) -> str:
    return text if len(text) <= 60 else text[:59] + "…"


def _labels(topics: dict[str, str]) -> dict[str, str]:
    """id → the title part of its topic (before ': ' or ' — ') so an id reads as what it decided. Where two decisions of
    the project share that part (MB-strata-kit-2026-032: 'QA 스킬의 자리' twice), those take the next phrase too —
    taken from the record as written, never summarised."""
    parts = {i: SEP.split(t) for i, t in topics.items()}
    short = {i: p[0] for i, p in parts.items()}
    seen: dict[str, int] = {}
    for v in short.values():
        seen[v] = seen.get(v, 0) + 1
    return {i: _cap(short[i] if seen[short[i]] == 1 or len(p) == 1 else f"{p[0]}: {p[1]}") for i, p in parts.items()}


def _list(value) -> list:
    return value if isinstance(value, list) else ([value] if value else [])


def _under(nodes, node: str | None) -> bool:
    return node is None or any(str(n) == node or str(n).startswith(node + ".") for n in _list(nodes))


def _has(text: str, query: str | None) -> bool:
    return query is None or query.lower() in text.lower()


def _records(project: str, vault: Path, project_dir: Path | None) -> list[tuple[Path, dict]]:
    from kb.engine import default_project_dirs
    from kb.paths import resolve_tier_p
    dirs = [project_dir] if project_dir else [d for d in default_project_dirs(vault) if d.name == project]
    for d in dirs:
        tier = resolve_tier_p(d)
        if tier is not None and tier.decisions_dir.is_dir():
            from kb.legacy.gen_decision_notes import load_records
            return list(load_records(tier.decisions_dir))
    return []


def _docs(pdir: Path, sub: str) -> list[tuple[Path, dict, str]]:
    out = []
    for f in sorted((pdir / sub).rglob("*.md")) if (pdir / sub).is_dir() else []:
        if f.is_symlink():
            continue   # latest.md
        text = f.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        out.append((f, fm if isinstance(fm, dict) else {}, body))
    return out


class _Titles:
    """Wikilink target → readable text: a vault document's title, a decision's 'id — topic', else the target itself."""

    def __init__(self, vault: Path, project: str, records: list[tuple[Path, dict]]):
        self.by_stem: dict[str, str] = {}
        for f in sorted((vault / "projects" / project).rglob("*.md")):
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
            if isinstance(fm, dict) and fm.get("title"):
                self.by_stem.setdefault(f.stem, str(fm["title"]))
        for _, body in records:
            self.by_stem.setdefault(str(body["id"]), f"{body['id']} — {_topic(body)}")

    def sub(self, text: str) -> str:
        def one(m: re.Match) -> str:
            target, alias = m.group(1).strip(), m.group(2)
            return alias.strip() if alias else self.by_stem.get(target.rsplit("/", 1)[-1], target)
        return LINK_RE.sub(one, text)


def _topic(body: dict) -> str:
    return " ".join(str(body.get("topic") or body.get("title") or "").split())


def _demote(body: str, by: int = 2) -> str:
    """A document embedded under a '## title' keeps its outline: '# x' → '### x'."""
    out, fence = [], None
    for line in body.split("\n"):
        m = re.match(r"^(```|~~~)", line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
        elif fence is None:
            line = re.sub(r"^(#{1,4}) ", lambda h: "#" * min(len(h.group(1)) + by, 6) + " ", line)
        out.append(line)
    return "\n".join(out)


def _block(text) -> str:
    return " ".join(str(text).split()) if text else ""


def _decisions(records, start, end, node, query, titles: _Titles, chain: set[str] | None,
               reviews_of: dict[str, int], labels: dict[str, str]) -> tuple[str, list[str]]:
    derived = derive_status(records)
    topics = {str(b["id"]): _topic(b) for _, b in records}
    picked = [b for _, b in sorted(records, key=lambda r: str(r[1]["id"]))
              if (chain is None or str(b["id"]) in chain) and _in(b.get("date"), start, end)
              and _under(b.get("nodes"), node) and _has(yaml.safe_dump(b, allow_unicode=True), query)]
    items = []
    for b in picked:
        rid = str(b["id"])
        _, by = derived.get(rid, ("active", []))
        facts = [str(b.get("date"))] + ([f"노드 {', '.join(map(str, _list(b.get('nodes'))))}"] if b.get("nodes") else [])
        facts += [f"{o}({labels.get(o, '기록 없음')}) 를 대신함" for o in _dec_ids(b.get("supersedes"))]
        facts += [f"{n}({labels.get(n, '기록 없음')}) 에 대신됨" for n in by]
        facts += [f"리뷰 {reviews_of[rid]}"] if reviews_of.get(rid) else []
        items.append(f"- {rid} — {topics[rid]} · " + " · ".join(facts))
    parts = ["# 결정\n", "결정마다 결론, 이유, 검토했다가 진 대안, 참고한 배경, 영향 범위, 대체 관계를 싣는다. "
             "대체 관계는 이 결정이 무엇을 대신했고 무엇에 대신됐는지다.\n"]
    for b in picked:
        rid = str(b["id"])
        status, superseded_by = derived.get(rid, ("active", []))
        parts.append(f"## {rid} — {topics[rid]}\n")
        parts.append(f"날짜 {b.get('date')} · 상태 {status}" + (f" · 노드 {', '.join(map(str, _list(b.get('nodes'))))}" if b.get("nodes") else "") + "\n")
        parts.append(f"### 결론\n\n{_block(b.get('decision'))}\n")
        if b.get("reason"):
            parts.append(f"### 이유\n\n{_block(b.get('reason'))}\n")
        if b.get("alternatives"):
            parts.append("### 진 대안\n\n" + "\n".join(f"- {_block(a)}" for a in _list(b["alternatives"])) + "\n")
        if b.get("background"):
            parts.append("### 배경\n\n" + "\n".join(f"- {_block(a)}" for a in _list(b["background"])) + "\n")
        if b.get("affects"):
            parts.append("### 영향\n\n" + "\n".join(f"- {_block(a)}" for a in _list(b["affects"])) + "\n")
        chain = [f"- 이 결정이 대신한 것: {o} — {topics.get(o, '(기록 없음)')}" for o in _dec_ids(b.get("supersedes"))]
        chain += [f"- 이 결정을 대신한 것: {n} — {topics.get(n, '(기록 없음)')}" for n in superseded_by]
        if chain:
            parts.append("### 대체 관계\n\n" + "\n".join(chain) + "\n")
    if not picked:
        parts.append("이 조건에 맞는 결정이 없다.\n")
    return titles.sub("\n".join(parts)), items


def _docs_file(title: str, intro: str, docs, date_of, start, end, node, query, titles: _Titles,
               chain: set[str] | None, facts_of) -> tuple[str, list[str]]:
    picked = [(f, fm, body) for f, fm, body in docs
              if (chain is None or _names(fm, chain)) and _in(date_of(fm), start, end)
              and _under(fm.get("nodes"), node) and _has(body + str(fm), query)]
    picked.sort(key=lambda d: (str(_day(date_of(d[1]))), d[0].name))
    items = [f"- {fm.get('title') or f.stem} · " + " · ".join([str(_day(date_of(fm)))] + facts_of(fm)) for f, fm, _ in picked]
    parts = [f"# {title}\n", intro + "\n"]
    for f, fm, body in picked:
        parts.append(f"## {fm.get('title') or f.stem}\n")
        parts.append(f"날짜 {_day(date_of(fm))}" + (f" · 주제 {_block(fm['topic'])}" if fm.get("topic") else "")
                     + (f" · 리뷰 대상 {fm['review_of']}" if fm.get("review_of") else "")
                     + (f" · 출처 {fm['source']}" if fm.get("source") else "") + "\n")
        parts.append(titles.sub(_demote(body)).strip() + "\n")
    if not picked:
        parts.append("이 조건에 맞는 문서가 없다.\n")
    return "\n".join(parts), items


def _measurements(pdir: Path, start: date, end: date) -> tuple[str, int]:
    f = pdir / "measurements" / "strata-metrics.yaml"
    parts = ["# 측정\n"]
    if not f.is_file():
        return "\n".join(parts + ["이 프로젝트에는 측정 파일이 없다.\n"]), 0
    m = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    revs = {k: v for k, v in (m.get("revisions") or {}).items() if isinstance(v, dict) and _in(v.get("date"), start, end)}
    snapshot = {k: v for k, v in m.items() if k != "revisions"}
    parts.append(f"측정값은 {str(m.get('collected', '?'))[:10]} 에 모은 한 시점의 값이다. 기간으로 거를 수 있는 것은 날짜가 있는 "
                 "판(revision)별 값뿐이라, 판별 값은 기간 안의 것만 싣고 나머지는 수집 시점 값 그대로 싣는다.\n")
    parts.append("## 기간 안의 판별 값\n\n" + (f"```yaml\n{yaml.safe_dump(revs, allow_unicode=True, sort_keys=True)}```\n" if revs else "기간 안의 판이 없다.\n"))
    parts.append(f"## 수집 시점 값\n\n```yaml\n{yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=True)}```\n")
    return "\n".join(parts), len(revs)


def build_bundle(vault: Path, project: str, start: date | None, end: date | None, project_dir: Path | None = None,
                 node: str | None = None, query: str | None = None, decision: str | None = None) -> dict[str, str]:
    """file name → content. Pure: same inputs, same output (no timestamps)."""
    pdir = vault / "projects" / project
    records = _records(project, vault, project_dir)
    titles = _Titles(vault, project, records)
    chain = _chain(records, decision) if decision else None
    labels = _labels({str(b["id"]): _topic(b) for _, b in records})
    label = lambda i: f"{i}({labels[i]})" if i in labels else i
    reviews = _docs(pdir, "reviews")
    reviews_of: dict[str, int] = {}
    for _, fm, _ in reviews:
        for rid in _dec_ids(fm.get("decisions_made")):
            reviews_of[rid] = reviews_of.get(rid, 0) + 1
    files: dict[str, str] = {}
    files[FILES[1]], di = _decisions(records, start, end, node, query, titles, chain, reviews_of, labels)
    files[FILES[2]], ri = _docs_file("리뷰", "외부·교차 리뷰 보고와 이 프로젝트의 대응(받아들인 것, 반론, 이어진 결정)이다.",
                                     reviews, lambda fm: fm.get("received") or fm.get("created"), start, end, node, query, titles,
                                     chain, lambda fm: ([f"대상 {fm['review_of']}"] if fm.get("review_of") else [])
                                     + ([f"이어진 결정 {len(_dec_ids(fm.get('decisions_made')))}"] if fm.get("decisions_made") else []))
    files[FILES[3]], si = _docs_file("세션", "세션 핸드오프다. '판단 과정' 절에 물은 것과 답, 뒤집힌 판단과 이유가 있다.",
                                     _docs(pdir, "sessions"), lambda fm: fm.get("created"), start, end, node, query, titles,
                                     chain, lambda fm: [f"결정 {', '.join(label(i) for i in _dec_ids(fm.get('decisions_made')))}"] if fm.get("decisions_made") else [])
    files[FILES[4]], nm = _measurements(pdir, start, end)
    period = f"{start or '처음'} ~ {end or '끝'}"
    cond = f"프로젝트 {project}" + (f" · 결정 {decision} 과 대체 사슬" if decision else "") + (f" · 기간 {period}" if start or end else "") \
        + (f" · 노드 {node}" if node else "") + (f" · 검색어 '{query}'" if query else "")
    nd, nr, ns = len(di), len(ri), len(si)
    files[FILES[0]] = "\n".join([
        f"# 회고 자료 — {project} " + (decision if decision else period) + "\n",
        f"조건: {cond}\n",
        "이 폴더는 vault 의 결정 기록·리뷰·세션 핸드오프·측정 파일에서 뽑은 생성본이다. 파일마다 혼자 읽히게 링크를 제목으로 풀었다. "
        "원본을 고치지 말고, 다시 만들려면 같은 조건으로 명령을 다시 실행한다.\n",
        "## 파일\n",
        f"- {FILES[1]} — 결정 {nd}건: 결론, 이유, 진 대안, 배경, 대체 관계",
        f"- {FILES[2]} — 리뷰 {nr}건: 보고와 대응",
        f"- {FILES[3]} — 세션 {ns}건: 핸드오프와 판단 과정",
        f"- {FILES[4]} — 측정: 기간 안의 판별 값 {nm}건과 수집 시점 값\n",
        "## 항목\n",
        "항목마다 기록에 적힌 사실만 붙였다(날짜, 노드, 대체 관계, 연결된 리뷰·결정). 요약이나 결론은 싣지 않는다 — 내용은 각 파일에서 읽는다.\n",
        "### 결정\n", *(di or ["- 없음"]), "",
        "### 리뷰\n", *(ri or ["- 없음"]), "",
        "### 세션\n", *(si or ["- 없음"]), "",
    ])
    return {k: v.rstrip() + "\n" for k, v in files.items()}


def write_bundle(out: Path, files: dict[str, str], force: bool = False) -> dict:
    if out.exists() and any(out.iterdir()) and not force:
        return {"result": "exists", "path": out}
    out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    return {"result": "written", "path": out}


def _slug(text: str) -> str:
    return re.sub(r"[^\w.-]+", "-", text).strip("-")[:40]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb retro-bundle", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--from", dest="start", default=None, type=date.fromisoformat)
    ap.add_argument("--to", dest="end", default=None, type=date.fromisoformat)
    ap.add_argument("--decision", default=None, help="start from one decision and its supersede chain (period optional)")
    ap.add_argument("--node", default=None)
    ap.add_argument("--query", default=None)
    ap.add_argument("--project-dir", type=Path, default=None, help="repo (or detached root) whose Tier P holds the decisions")
    ap.add_argument("--name", default=None)
    ap.add_argument("--force", action="store_true", help="write into an existing folder (files it did not write stay)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.decision and not (a.start and a.end):
        ap.error("--from 과 --to, 또는 --decision 이 필요하다")
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    if not (vault / "projects" / a.project).is_dir():
        print(f"project not found in vault: {a.project}", file=sys.stderr)
        return 2
    files = build_bundle(vault, a.project, a.start, a.end, a.project_dir, a.node, a.query, a.decision)
    period = f"{a.start}_{a.end}" if a.start or a.end else None
    name = a.name or "-".join(x for x in (a.decision, period, a.project, a.node and _slug(a.node), a.query and _slug(a.query)) if x)
    out = vault / "outputs" / "retro" / name
    for fname, text in files.items():
        print(f"{'would write' if a.dry_run else 'write'} {out / fname} ({len(text.encode())} B)")
    if a.dry_run:
        return 0
    r = write_bundle(out, files, force=a.force)
    if r["result"] == "exists":
        print(f"exists: {out} — 같은 이름의 묶음이 있다. 덮어쓰려면 --force(묶음이 쓰지 않은 파일은 남는다), 아니면 --name", file=sys.stderr)
        return 3
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
