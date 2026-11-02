"""Idea notes for the ideation pack (planning/ideation-pack, DEC-2026-10-31-38 · DEC-2026-11-01-01 · DEC-2026-11-01-02).

One idea, one note: $STRATA_VAULT/ideas/<YYYY-MM-DD>-<slug>.md. The frontmatter holds the nature (problem | intuition),
the status (active | archived), the related projects, the conditions the idea needs (each met or not), the orders it is
expected to take, and the day the person confirmed that weight. The body has the five facets (발단 · 문제 · 방법 · 결과 ·
의미 — an empty facet is allowed), the eliminated cases, and the growth log. There is no threshold to cross: an idea may
be used at any stage. Remaining weight = unmet conditions + remaining expected orders; the sum over open ideas is the
load of thought being carried. Only a weight the person confirmed counts. An idea that has not grown for more than 30
days is offered for archiving; archiving changes the status only (no move, no delete), and a new growth event reopens it.

  python3 -m kb ideas list   [--all]
  python3 -m kb ideas check
  python3 -m kb ideas tidy   [--days 30] [--apply]
  python3 -m kb ideas event  <note> facet|link|use|condition <text>
  python3 -m kb ideas draw   [--note <note>] [--count 3] [--seed N]
  python3 -m kb ideas near   <note> [--top 3] [--embed]
  python3 -m kb ideas map    <note> [--facet F] [--embed]

`near` (planning/idea-facet-distance) compares same-name facets by cosine similarity: empty facets are left out, near and
far are read against the quartiles of that facet's pair distribution over all ideas (a facet with fewer than 4 pairs
holds its judgement), and relation kinds come with the facet values they rest on — alternative (same problem, other
method), exaptation (same method, other problem), bundle (same meaning), competition (same outcome). A neighbour-bias
line appears when every close neighbour is close in one facet only, and link candidates are printed, never written.
`list` adds an overall-bias line when the open ideas' mean pair similarity in one facet stands BIAS_GAP above the
median of the other facets (only when every facet is in the cache). Facet texts are read from the notes, vectors from
the store's embedding cache; `--embed` fills the missing ones with the local model. Nothing is written to the notes.

`map` writes an Obsidian canvas, $STRATA_VAULT/outputs/ideas/<note>[.<facet>].canvas (generated, rewritten each run):
the idea in the centre, every other idea as a file node at a radius proportional to its distance (1 − similarity) for
the facet, or the mean over measurable facets; edges carry the similarity and the relation kinds, coloured by the first
kind; ideas not measurable for the facet sit on an outer ring.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[1]
FACETS = ("발단", "문제", "방법", "결과", "의미")
FACET_ALIASES = {"origin": "발단", "problem": "문제", "method": "방법", "outcome": "결과", "meaning": "의미"}
NATURES = ("problem", "intuition")
STATUSES = ("active", "archived")
EVENTS = ("facet", "link", "use", "condition")
LOG = "발전 기록"
EVENT_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\w+)\b")
DRAW_TYPES = ("decision", "pattern", "review", "reference", "concept", "report")
CONSTRAINTS = KIT / "skills" / "packs" / "ideation" / "ideation.shape" / "data" / "constraints.json"


def ideas_dir(vault: Path) -> Path:
    return vault / "ideas"


def split(text: str) -> tuple[dict, str, str]:
    """(frontmatter, raw frontmatter block, body). The body is kept byte for byte."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            raw = text[: end + 4]
            try:
                fm = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                fm = {}
            return (fm if isinstance(fm, dict) else {}), raw, text[end + 4:]
    return {}, "", text


def join(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---" + body


def sections(body: str) -> dict[str, str]:
    out, cur = {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            cur = FACET_ALIASES.get(name.lower(), name)
            out[cur] = ""
        elif cur is not None:
            out[cur] += line + "\n"
    return out


@dataclass
class Idea:
    path: Path
    fm: dict
    body: str
    problems: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return str(self.fm.get("status") or "")

    @property
    def title(self) -> str:
        return str(self.fm.get("title") or self.path.stem)

    def events(self) -> list[tuple[str, str]]:
        log = sections(self.body).get(LOG, "")
        return [(m.group(1), m.group(2)) for m in (EVENT_LINE.match(l.strip()) for l in log.splitlines()) if m]

    def last_growth(self) -> date | None:
        days = [d for d, _ in self.events()]
        created = self.fm.get("created")
        if created:
            days.append(str(created))
        try:
            return max(date.fromisoformat(d) for d in days) if days else None
        except ValueError:
            return None

    def weight(self) -> int | None:
        """Unmet conditions + remaining expected orders, or None until the person confirmed the weight."""
        if not self.fm.get("weight_confirmed"):
            return None
        conds = self.fm.get("conditions") or []
        unmet = sum(1 for c in conds if isinstance(c, dict) and not c.get("met"))
        left = max(int(self.fm.get("orders_expected") or 0) - int(self.fm.get("orders_done") or 0), 0)
        return unmet + left

    def empty_facets(self) -> list[str]:
        s = sections(self.body)
        return [f for f in FACETS if f in s and not re.sub(r"(?m)^\s*(비어 있음|empty)\s*$", "", s[f]).strip()]


def load(path: Path) -> Idea:
    fm, _, body = split(path.read_text(encoding="utf-8"))
    idea = Idea(path, fm, body)
    if fm.get("type") != "idea":
        idea.problems.append(f"type {fm.get('type') or '없음'} — idea 여야 한다")
    if fm.get("nature") not in NATURES:
        idea.problems.append(f"nature {fm.get('nature') or '없음'} — {', '.join(NATURES)} 중 하나")
    if fm.get("status") not in STATUSES:
        idea.problems.append(f"status {fm.get('status') or '없음'} — {', '.join(STATUSES)} 중 하나")
    conds = fm.get("conditions")
    if conds is not None and not (isinstance(conds, list) and all(isinstance(c, dict) and isinstance(c.get("text"), str)
                                                                    and isinstance(c.get("met", False), bool) for c in conds)):
        idea.problems.append("conditions — 항목마다 {text: 문장, met: true|false}")
    for k in ("orders_expected", "orders_done"):
        v = fm.get(k)
        if v is not None and not (isinstance(v, int) and v >= 0):
            idea.problems.append(f"{k} {v!r} — 0 이상의 정수")
    s = sections(body)
    missing = [f for f in FACETS if f not in s]
    if missing:
        idea.problems.append(f"속성 절 없음: {', '.join(missing)} (빈 칸은 '비어 있음' 으로 둔다)")
    if LOG not in s:
        idea.problems.append(f"'{LOG}' 절 없음")
    bad = [k for _, k in idea.events() if k not in EVENTS]
    if bad:
        idea.problems.append(f"발전 기록의 사건 종류 {', '.join(sorted(set(bad)))} — {', '.join(EVENTS)} 중 하나")
    return idea


def all_ideas(vault: Path) -> list[Idea]:
    d = ideas_dir(vault)
    return [load(p) for p in sorted(d.glob("*.md")) if not p.name.startswith(("_", "."))] if d.is_dir() else []


BIAS_GAP = 0.15


def overall_bias(ideas: list[Idea], vectors) -> str | None:
    """One line when open ideas are much more alike in one facet (mean pair similarity) than in the others."""
    import numpy as np
    open_ = [i for i in ideas if i.status == "active"]
    texts = [facet_texts(i) for i in open_]
    vec = vectors(sorted({t for f in texts for t in f.values()}))
    means = {}
    for f in FACETS:
        xs = [float(np.dot(vec[a[f]], vec[b[f]])) for k, a in enumerate(texts) for b in texts[k + 1:] if f in a and f in b]
        if len(xs) >= MIN_PAIRS:
            means[f] = sum(xs) / len(xs)
    if len(means) < 2:
        return None
    top = max(means, key=means.get)
    rest = sorted(v for f, v in means.items() if f != top)
    mid = rest[len(rest) // 2] if len(rest) % 2 else (rest[len(rest) // 2 - 1] + rest[len(rest) // 2]) / 2
    if means[top] - mid < BIAS_GAP:
        return None
    return (f"전체 치우침: 열린 아이디어 {len(open_)} 이 {top} 에서 서로 너무 비슷하다 (평균 유사도 {means[top]:.2f}, 다른 속성 중앙 {mid:.2f})"
            " — 많지만 흩어짐이 없을 수 있다")


def listing(ideas: list[Idea], today: date, show_all: bool = False, vectors=None) -> list[str]:
    open_ = [i for i in ideas if i.status == "active"]
    total = sum(w for w in (i.weight() for i in open_) if w is not None)
    unconfirmed = sum(1 for i in open_ if i.weight() is None)
    lines = [f"열린 아이디어 {len(open_)} · 고민의 총량 {total}" + (f" (무게 미확인 {unconfirmed} 은 합에 넣지 않음)" if unconfirmed else "")
             + f" · 아카이브 {sum(1 for i in ideas if i.status == 'archived')}"]
    for i in ideas:
        if i.status != "active" and not show_all:
            continue
        w = i.weight()
        last = i.last_growth()
        idle = f"{(today - last).days}일 전" if last else "날짜 없음"
        empty = i.empty_facets()
        lines.append(f"  {i.path.name} [{i.status}] 무게 {w if w is not None else '미확인'} · 마지막 발전 {idle}"
                     + (f" · 빈칸 {', '.join(empty)}" if empty else "") + f" — {i.title}")
    if vectors is not None:
        b = overall_bias(ideas, vectors)
        if b:
            lines.append(b)
    return lines


def tidy(ideas: list[Idea], today: date, days: int = 30, apply: bool = False) -> list[str]:
    """Offer ideas idle for more than `days` for archiving; with apply, set status and the archive note only."""
    cands = [i for i in ideas if i.status == "active" and i.last_growth() and (today - i.last_growth()).days > days]
    lines = [f"{'아카이브' if apply else '미리보기'}: {days}일 넘게 발전이 없는 열린 아이디어 {len(cands)}"]
    for i in cands:
        idle = (today - i.last_growth()).days
        lines.append(f"  {i.path.name} — 마지막 발전 {i.last_growth()} ({idle}일) — {i.title}")
        if apply:
            text = i.path.read_text(encoding="utf-8")
            fm, _, body = split(text)
            fm["status"] = "archived"
            fm["archived"] = {"date": today.isoformat(), "reason": f"발전 없음 {idle}일"}
            i.path.write_text(join(fm, body), encoding="utf-8")
    if cands and not apply:
        lines.append("  --apply 로 상태만 archived 로 바꾼다(노트는 옮기거나 지우지 않는다)")
    return lines


def add_event(path: Path, kind: str, text: str, today: date) -> list[str]:
    """Append a growth event to the log; an archived note is reopened (DEC-2026-11-01-02)."""
    if kind not in EVENTS:
        raise ValueError(f"사건 종류 {kind} — {', '.join(EVENTS)} 중 하나")
    raw = path.read_text(encoding="utf-8")
    fm, _, body = split(raw)
    line = f"- {today.isoformat()} {kind} — {text}"
    m = re.search(rf"(?m)^##\s+{LOG}\s*$", body)
    if not m:
        body = body.rstrip("\n") + f"\n\n## {LOG}\n\n{line}\n"
    else:
        nxt = re.search(r"(?m)^##\s+", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        block = body[m.end():end].rstrip("\n")
        body = body[:m.end()] + block + ("\n" if block.strip() else "\n\n") + line + "\n" + ("\n" if nxt else "") + body[end:]
    out = [f"기록: {path.name} {line[2:]}"]
    if fm.get("status") == "archived":
        was = (fm.get("archived") or {}).get("date")
        fm["status"] = "active"
        fm.pop("archived", None)
        fm["reopened"] = today.isoformat()
        out.append(f"  다시 열림 (아카이브 {was or '?'} → active)")
    path.write_text(join(fm, body), encoding="utf-8")
    return out


def _record_pool(vault: Path, exclude_projects: set[str]) -> list[tuple[str, str, str]]:
    """(kind, title, vault-relative path) of records outside the idea's projects: decisions, reviews, patterns,
    retrospectives — work projects included, quoted with their source (DEC-2026-11-01-02)."""
    from kb.docrules import parse_frontmatter
    pool = []
    roots = [p for p in (vault / "projects").iterdir() if p.is_dir() and p.name not in exclude_projects] if (vault / "projects").is_dir() else []
    files = [f for r in roots for f in r.rglob("*.md")] + list((vault / "patterns").glob("*.md")) + list((vault / "retrospectives").glob("*.md"))
    for f in sorted(files):
        if f.name.startswith("_") or f.is_symlink():
            continue
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        kind = str(fm.get("type") or "")
        if kind in DRAW_TYPES or f.parent.name == "retrospectives":
            pool.append((kind or "retrospective", str(fm.get("title") or f.stem), str(f.relative_to(vault))))
    return pool


def draw(vault: Path, note: Path | None = None, count: int = 3, seed: int | None = None) -> list[str]:
    """Collision material drawn at random: records first, the constraint list when records run short. Shows the
    material and its source only — it does not make ideas."""
    exclude = set()
    if note:
        fm, _, _ = split(note.read_text(encoding="utf-8"))
        exclude = {str(p) for p in (fm.get("projects") or [])}
    rng = random.Random(seed)
    pool = _record_pool(vault, exclude)
    picks = [f"  기록 · {k} · {t} — {p}" for k, t, p in rng.sample(pool, min(count, len(pool)))]
    if len(picks) < count and CONSTRAINTS.is_file():
        data = json.loads(CONSTRAINTS.read_text(encoding="utf-8"))
        flat = [(cat, s) for cat, items in data.items() if not cat.startswith("_") for s in items]
        picks += [f"  제약 · {cat} · {s} — jwynia/agent-skills brainstorming constraints.json (MIT)"
                  for cat, s in rng.sample(flat, min(count - len(picks), len(flat)))]
    head = f"충돌 재료 {len(picks)}" + (f" (관련 프로젝트 {', '.join(sorted(exclude))} 밖)" if exclude else "")
    return [head, *picks, "  재료일 뿐이다 — 무엇과 부딪혀 무엇이 보이는지는 사용자가 적는다"]


MIN_PAIRS = 4
EMPTY = re.compile(r"^\s*(비어 있음|empty)?\s*$")


def facet_texts(idea: Idea) -> dict[str, str]:
    """The idea's non-empty facets, text stripped."""
    s = sections(idea.body)
    return {f: s[f].strip() for f in FACETS if f in s and not EMPTY.match(s[f].strip())}


def _quartiles(xs: list[float]) -> tuple[float, float]:
    import numpy as np
    return float(np.percentile(xs, 25)), float(np.percentile(xs, 75))


def near(ideas: list[Idea], target: Path, vectors) -> dict:
    """Facet similarities of `target` against every other idea, quartile thresholds per facet, relation kinds with
    their evidence and the neighbour bias. `vectors(texts) -> {text: unit vector}`."""
    import numpy as np
    target = Path(target).resolve()
    texts = {i.path.stem: facet_texts(i) for i in ideas}
    centre = next(i.path.stem for i in ideas if i.path.resolve() == target)
    vec = vectors(sorted({t for f in texts.values() for t in f.values()}))
    sim = lambda a, b, f: float(np.dot(vec[texts[a][f]], vec[texts[b][f]])) if f in texts[a] and f in texts[b] else None
    names = sorted(texts)
    bounds = {}
    for f in FACETS:
        xs = [x for i, a in enumerate(names) for b in names[i + 1:] if (x := sim(a, b, f)) is not None]
        bounds[f] = _quartiles(xs) if len(xs) >= MIN_PAIRS else None
    pairs = {o: {f: sim(centre, o, f) for f in FACETS} for o in names if o != centre}
    close = lambda o, f: bounds[f] is not None and pairs[o][f] is not None and pairs[o][f] >= bounds[f][1]
    far = lambda o, f: bounds[f] is not None and pairs[o][f] is not None and pairs[o][f] <= bounds[f][0]
    v = lambda o, f: f"{f} {pairs[o][f]:.2f}"
    relations = {}
    for o in pairs:
        rel = []
        if close(o, "문제") and far(o, "방법"):
            rel.append(("대안", f"{v(o, '문제')}, {v(o, '방법')}"))
        if close(o, "방법") and far(o, "문제"):
            rel.append(("전용", f"{v(o, '방법')}, {v(o, '문제')}"))
        if close(o, "의미"):
            rel.append(("묶음", v(o, "의미")))
        if close(o, "결과"):
            rel.append(("경쟁", v(o, "결과")))
        if rel:
            relations[o] = rel
    neighbours = {o: {f for f in FACETS if close(o, f)} for o in pairs}
    neighbours = {o: fs for o, fs in neighbours.items() if fs}
    only = set().union(*neighbours.values()) if neighbours else set()
    bias = (next(iter(only)), sorted(neighbours)) if len(neighbours) >= 2 and len(only) == 1 else None
    return {"centre": centre, "pairs": pairs, "bounds": bounds, "relations": relations, "bias": bias}


def near_lines(r: dict, top: int = 3) -> list[str]:
    lines = [f"{r['centre']} 와의 속성별 거리 (코사인 유사도, 1 에 가까울수록 가깝다 — 판정은 사용자)"]
    for f in FACETS:
        got = sorted(((x, o) for o, p in r["pairs"].items() if (x := p[f]) is not None), reverse=True)
        none = sorted(o for o, p in r["pairs"].items() if p[f] is None)
        b = r["bounds"][f]
        head = f"  {f}" + (f" (가까움 ≥ {b[1]:.2f} · 멂 ≤ {b[0]:.2f})" if b else f" (쌍 {MIN_PAIRS} 미만 — 판정 보류)")
        lines.append(head + (" — 가까운 순: " + ", ".join(f"{o} {x:.2f}" for x, o in got[:top]) if got else ""))
        if len(got) > top:
            lines.append("    가장 먼: " + ", ".join(f"{o} {x:.2f}" for x, o in got[-top:][::-1]))
        if none:
            lines.append(f"    {f} — 잴 수 없음: {', '.join(none)} (빈칸)")
    avg = sorted(((sum(xs) / len(xs), o) for o, p in r["pairs"].items() if (xs := [x for x in p.values() if x is not None])), reverse=True)
    if avg:
        lines.append("  합친 순위: " + ", ".join(f"{o} {x:.2f}" for x, o in avg))
    if r["relations"]:
        lines.append("  관계 후보:")
        lines += [f"    {o}: " + "; ".join(f"{k} ({ev})" for k, ev in rel) for o, rel in sorted(r["relations"].items())]
    elif not any(r["bounds"].values()):
        lines.append(f"  관계 후보: 판정 보류 — 속성마다 쌍이 {MIN_PAIRS} 개 이상이어야 사분위를 잡는다")
    links = [o for o in sorted(r["relations"])] + [o for _, o in avg[:top] if o not in r["relations"]][: max(top - len(r["relations"]), 0)]
    if links:
        lines.append("  링크 후보: " + ", ".join(f"[[{o}]] ({', '.join(k for k, _ in r['relations'][o])})" if o in r["relations"] else f"[[{o}]] (합친 순위)"
                                            for o in links)
                     + " — 노트에 쓰지 않는다. 고르면 링크를 더하고 `kb ideas event <노트> link` 로 남긴다")
    if r["bias"]:
        f, who = r["bias"]
        lines.append(f"  이웃 치우침: 가까운 이웃 {len(who)} 이 모두 {f} 에서만 가깝다 ({', '.join(who)}) — 다른 속성은 먼 것을 살펴볼 만하다")
    return lines


def near_command(vault: Path, target: Path, lookup, embed=None, on_embed=None, top: int = 3) -> list[str]:
    """`lookup(texts) -> {text: vec}` reads the cache; `embed(texts) -> {text: vec}` computes the rest when given."""
    ideas = all_ideas(vault)
    if not any(i.path.resolve() == Path(target).resolve() for i in ideas):
        return [f"{target} 는 {ideas_dir(vault)} 의 아이디어 노트가 아니다"]
    needed = sorted({t for i in ideas for t in facet_texts(i).values()})
    have = dict(lookup(needed))
    missing = [t for t in needed if t not in have]
    if missing and embed is None:
        return [f"임베딩 없는 속성 {len(missing)} / {len(needed)} — --embed 로 로컬 모델(bge-m3)이 채운다. 노트는 바꾸지 않는다"]
    if missing:
        have.update(embed(missing))
        if on_embed:
            on_embed(missing)
    return near_lines(near(ideas, target, lambda ts: {t: have[t] for t in ts}), top)


REL_COLORS = {"대안": "4", "전용": "6", "묶음": "5", "경쟁": "1"}
NODE_W, NODE_H, R_MIN, R_SCALE = 400, 240, 500, 1400


def write_map(vault: Path, target: Path, vectors, facet: str | None = None) -> Path:
    """The canvas for `target`; returns its path. Notes are only read."""
    import json
    import math
    if facet is not None and facet not in FACETS:
        facet = FACET_ALIASES.get(facet.lower(), facet)
        if facet not in FACETS:
            raise ValueError(f"속성 {facet} — {', '.join(FACETS)} 중 하나")
    ideas = all_ideas(vault)
    r = near(ideas, target, vectors)
    by_stem = {i.path.stem: i for i in ideas}
    rel = lambda i: str(i.path.relative_to(vault))
    centre = r["centre"]

    def score(o):
        p = r["pairs"][o]
        if facet:
            return p[facet]
        xs = [x for x in p.values() if x is not None]
        return sum(xs) / len(xs) if xs else None

    others = sorted(r["pairs"], key=lambda o: (score(o) is None, -(score(o) or 0), o))
    outer = R_MIN + R_SCALE * 2 + NODE_W
    nodes = [{"id": "c", "type": "file", "file": rel(by_stem[centre]), "x": -NODE_W // 2, "y": -NODE_H // 2,
              "width": NODE_W, "height": NODE_H, "color": "3"}]
    edges = []
    golden = math.pi * (3 - math.sqrt(5))
    for k, o in enumerate(others):
        x = score(o)
        radius = outer if x is None else R_MIN + R_SCALE * (1 - x)
        a = k * golden
        nid = f"n{k}"
        nodes.append({"id": nid, "type": "file", "file": rel(by_stem[o]),
                      "x": round(radius * math.cos(a)) - NODE_W // 2, "y": round(radius * math.sin(a)) - NODE_H // 2,
                      "width": NODE_W, "height": NODE_H})
        kinds = [kd for kd, _ in r["relations"].get(o, [])]
        label = ("잴 수 없음 (빈칸)" if x is None else f"{x:.2f}") + (f" · {', '.join(kinds)}" if kinds else "")
        if by_stem[o].status == "archived":
            label += " · 아카이브"
        e = {"id": f"e{k}", "fromNode": "c", "toNode": nid, "label": label}
        if kinds:
            e["color"] = REL_COLORS[kinds[0]]
        edges.append(e)
    legend = (f"{centre} — {'속성 ' + facet if facet else '다섯 속성 평균'} 거리 지도 (가운데에서 멀수록 멀다)\n"
              "선 색: 대안 초록 · 전용 보라 · 묶음 청록 · 경쟁 빨강. 바깥 고리는 잴 수 없음.\n"
              "생성물 — kb ideas map 이 다시 쓴다. 판정은 사용자.")
    top = min((n["y"] for n in nodes), default=-NODE_H // 2)
    nodes.append({"id": "legend", "type": "text", "text": legend, "x": -NODE_W, "y": top - NODE_H * 2,
                  "width": NODE_W * 2, "height": NODE_H})
    out = vault / "outputs" / "ideas" / (f"{centre}.{facet}.canvas" if facet else f"{centre}.canvas")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def _gather(vault: Path, lookup, embed=None):
    """(vectors function, message): cache first, the local model for the rest when `embed` is given."""
    ideas = all_ideas(vault)
    needed = sorted({t for i in ideas for t in facet_texts(i).values()})
    have = dict(lookup(needed))
    missing = [t for t in needed if t not in have]
    if missing and embed is None:
        return None, f"임베딩 없는 속성 {len(missing)} / {len(needed)} — --embed 로 로컬 모델(bge-m3)이 채운다. 노트는 바꾸지 않는다"
    if missing:
        have.update(embed(missing))
    return (lambda ts: {t: have[t] for t in ts}), None


def _store_vectors(vault: Path, model: str):
    """Cache lookup and fill on the vault store's embeddings table, keyed by sha256 of the facet text."""
    import hashlib
    import numpy as np
    from kb.store import open_store
    store = open_store()
    key = lambda t: hashlib.sha256(t.encode("utf-8")).hexdigest()

    def lookup(texts):
        out = {}
        for t in texts:
            row = store.conn.execute("SELECT vector FROM embeddings WHERE model = ? AND text_hash = ?", (model, key(t))).fetchone()
            if row:
                out[t] = np.frombuffer(row[0], dtype=np.float32)
        return out

    def embed(texts):
        from kb.embed import Embedder
        vecs = Embedder(model).encode(list(texts))
        store.put_embeddings(model, [(key(t), v) for t, v in zip(texts, vecs)])
        return {t: np.asarray(v, dtype=np.float32) for t, v in zip(texts, vecs)}
    return lookup, embed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb ideas", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list"); ls.add_argument("--all", action="store_true")
    sub.add_parser("check")
    t = sub.add_parser("tidy"); t.add_argument("--days", type=int, default=30); t.add_argument("--apply", action="store_true")
    e = sub.add_parser("event"); e.add_argument("note"); e.add_argument("kind", choices=EVENTS); e.add_argument("text")
    d = sub.add_parser("draw"); d.add_argument("--note"); d.add_argument("--count", type=int, default=3); d.add_argument("--seed", type=int)
    nr = sub.add_parser("near"); nr.add_argument("note"); nr.add_argument("--top", type=int, default=3); nr.add_argument("--embed", action="store_true")
    mp = sub.add_parser("map"); mp.add_argument("note"); mp.add_argument("--facet"); mp.add_argument("--embed", action="store_true")
    for p in (ls, t, e):
        p.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    today = getattr(a, "today", None) or date.today()

    def note_path(s: str) -> Path:
        p = Path(s)
        return p if p.is_file() else ideas_dir(vault) / (s if s.endswith(".md") else s + ".md")

    if a.cmd == "list":
        ideas = all_ideas(vault)
        vec = None
        try:   # the overall-bias line needs every facet in the cache; it never embeds here
            from kb.store import open_store
            lookup, _ = _store_vectors(vault, open_store().embedding_model() or "BAAI/bge-m3")
            vec, _msg = _gather(vault, lookup, None)
        except Exception:
            vec = None
        print("\n".join(listing(ideas, today, a.all, vectors=vec)))
        return 0
    if a.cmd == "check":
        ideas = all_ideas(vault)
        bad = [i for i in ideas if i.problems]
        print(f"아이디어 노트 {len(ideas)} · 문제 {len(bad)} — {ideas_dir(vault)}")
        for i in bad:
            for why in i.problems:
                print(f"  {i.path.name}: {why}")
        return 2 if bad else 0
    if a.cmd == "tidy":
        print("\n".join(tidy(all_ideas(vault), today, a.days, a.apply)))
        return 0
    if a.cmd == "event":
        p = note_path(a.note)
        if not p.is_file():
            print(f"노트 없음: {p}", file=sys.stderr)
            return 2
        print("\n".join(add_event(p, a.kind, a.text, today)))
        return 0
    if a.cmd == "map":
        p = note_path(a.note)
        if not any(i.path.resolve() == p.resolve() for i in all_ideas(vault)):
            print(f"{p} 는 {ideas_dir(vault)} 의 아이디어 노트가 아니다", file=sys.stderr)
            return 2
        from kb.store import open_store
        lookup, embed = _store_vectors(vault, open_store().embedding_model() or "BAAI/bge-m3")
        vec, msg = _gather(vault, lookup, embed if a.embed else None)
        if vec is None:
            print(msg)
            return 0
        try:
            out = write_map(vault, p, vec, a.facet)
        except ValueError as e:
            print(f"오류: {e}", file=sys.stderr)
            return 2
        print(f"지도: {out} — 옵시디언에서 열면 노드를 눌러 노트로 간다 (생성물, 다시 실행하면 덮어씀)")
        return 0
    if a.cmd == "near":
        p = note_path(a.note)
        if not p.is_file():
            print(f"노트 없음: {p}", file=sys.stderr)
            return 2
        from kb.store import open_store
        model = open_store().embedding_model() or "BAAI/bge-m3"
        lookup, embed = _store_vectors(vault, model)
        print("\n".join(near_command(vault, p, lookup, embed if a.embed else None, top=a.top)))
        return 0
    p = note_path(a.note) if a.note else None
    print("\n".join(draw(vault, p if p and p.is_file() else None, a.count, a.seed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
