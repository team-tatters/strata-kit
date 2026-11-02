"""Operations signals (planning/operations-signal; DEC-2026-11-01-14, narrowed by DEC-2026-11-01-17).

The core's operations stage shows indicators; a signal is an indicator that moved the worse way — a trend in strata's
own measurement table (kit revision, sessions, verification, handoffs, git) or a product-flow indicator a project reads
from its own flows (kb indicators). Product incidents, alerts and feedback belong to the product's own features and are
not taken here. Each signal is one note: $STRATA_VAULT/projects/<p>/signals/<YYYY-MM-DD>-<slug>.md with what moved and
its evidence; where it goes (a methodology backlog item, a decision, an idea note, a planning document, or nowhere) is
chosen by a person and written back to the note.

  python3 -m kb signals list       --project P [--all]
  python3 -m kb signals check      --project P [--stale-days 14]
  python3 -m kb signals candidates --project P [--write] [--threshold 0.10]
  python3 -m kb signals route      --project P <note> --to <target> --by <person>
  python3 -m kb signals route      --project P <note> --drop <reason> --by <person>

Frontmatter: type: signal · source (metrics | indicator) · observed · status (open | routed | dropped) · candidate
(kind@basis, so the same candidate is not written twice) · after a person chooses: routed_to (backlog item id, DEC id
or a vault path to an idea note or planning document) or dropped_reason, with decided_by and decided.
Body: 관찰 · 근거 · 행선지.

`candidates` reads the measurement table (tools/metrics.py → measurements/strata-metrics.yaml) and the indicator
history (kb indicators → measurements/indicators.yaml) and prints candidates only; with --write it writes them as open
notes with no destination. It never routes: the destination is the person's. `route` records a destination that
already exists — the receiving item is written separately, in words the person approved.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

SOURCES = ("metrics", "indicator")   # DEC-2026-11-01-17: indicator changes only
STATUSES = ("open", "routed", "dropped")
SECTIONS = ("관찰", "근거", "행선지")
SECTION_ALIASES = {"observation": "관찰", "evidence": "근거", "destination": "행선지"}
STALE_DAYS = 14          # 사용자 답 2026-11-01
THRESHOLD = 0.10         # 진입 경로 바이트·첫 수정까지 토큰, 앞 판 대비 (사용자 답 2026-11-01)
MIN_SESSIONS = 2         # 첫 수정까지 토큰: 최근 판과 앞 판들 양쪽에 첫 수정이 있는 세션이 이만큼 있어야 비교한다
BASELINE_SESSIONS = 5    # 앞 판들에서 기준으로 삼는 최근 세션 수
EMPTY = re.compile(r"^\s*(비어 있음|empty|-)?\s*$")
PLACEHOLDER = re.compile(r"^\s*(비어 있음|empty)\b", re.I)   # the destination placeholder, removed once a person chooses
EXTERNAL = ("notion:", "http://", "https://")


def signals_dir(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "signals"


def metrics_path(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "measurements" / "strata-metrics.yaml"


def split(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                fm = {}
            return (fm if isinstance(fm, dict) else {}), text[end + 4:]
    return {}, text


def join(fm: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---" + body


def sections(body: str) -> dict[str, str]:
    out, cur = {}, None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            cur = SECTION_ALIASES.get(name.lower(), name)
            out[cur] = ""
        elif cur is not None:
            out[cur] += line + "\n"
    return out


def _day(v) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


@dataclass
class Signal:
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

    def age(self, today: date) -> int | None:
        d = _day(self.fm.get("observed"))
        return (today - d).days if d else None


def target_exists(vault: Path, project: str, target: str) -> bool | None:
    """True/False when the destination can be checked; None for an external one (notion:, http) taken as given."""
    t = str(target).strip()
    if t.startswith(EXTERNAL):
        return None
    if t.endswith(".md") or "/" in t:
        p = Path(t)
        cands = [p] if p.is_absolute() else [vault / t, vault / "projects" / project / t]
        return any(c.is_file() for c in cands)
    if re.match(r"^DEC-\d{4}-\d{2}-\d{2}-\d+$", t):
        return any((vault / "projects").glob(f"*/decisions/{t}.md"))
    pat = re.compile(rf"^\s*-?\s*id:\s*[\"']?{re.escape(t)}[\"']?\s*$", re.M)
    for f in (vault / "projects").glob("*/backlog/*.yaml"):
        if pat.search(f.read_text(encoding="utf-8", errors="replace")):
            return True
    return False


def load(path: Path, vault: Path, project: str) -> Signal:
    fm, body = split(path.read_text(encoding="utf-8"))
    s = Signal(path, fm, body)
    bad = s.problems.append
    if fm.get("type") != "signal":
        bad(f"type {fm.get('type') or '없음'} — signal 이어야 한다")
    if fm.get("source") not in SOURCES:
        bad(f"source {fm.get('source') or '없음'} — {', '.join(SOURCES)} 중 하나")
    if not _day(fm.get("observed")):
        bad(f"observed {fm.get('observed') or '없음'} — 본 날짜 YYYY-MM-DD")
    if fm.get("status") not in STATUSES:
        bad(f"status {fm.get('status') or '없음'} — {', '.join(STATUSES)} 중 하나")
    sec = sections(body)
    missing = [n for n in SECTIONS if n not in sec]
    if missing:
        bad(f"절 없음: {', '.join(missing)}")
    if "근거" in sec and EMPTY.match(sec["근거"].strip()):
        bad("근거가 비었다 — 측정값과 비교 기준(앞 판·앞 수집·문턱)을 적는다")
    st = fm.get("status")
    if st in ("routed", "dropped"):
        if not fm.get("decided_by"):
            bad(f"{st} 인데 decided_by 없음 — 행선지는 사람이 고른다")
        if not _day(fm.get("decided")):
            bad(f"{st} 인데 decided(고른 날짜) 없음")
    if st == "routed":
        to = fm.get("routed_to")
        if not to:
            bad("routed 인데 routed_to 없음")
        elif target_exists(vault, project, str(to)) is False:
            bad(f"routed_to {to} — 그 백로그 항목·결정·노트를 찾지 못했다")
    if st == "dropped" and not str(fm.get("dropped_reason") or "").strip():
        bad("dropped 인데 dropped_reason 없음")
    return s


def all_signals(vault: Path, project: str) -> list[Signal]:
    d = signals_dir(vault, project)
    return [load(p, vault, project) for p in sorted(d.glob("*.md")) if not p.name.startswith(("_", "."))] if d.is_dir() else []


def check(signals: list[Signal], today: date, stale_days: int = STALE_DAYS) -> tuple[list[str], int]:
    """Lines and exit code: 2 when a note is malformed; a signal open longer than stale_days is shown, not failed."""
    bad = [s for s in signals if s.problems]
    stale = [s for s in signals if s.status == "open" and (s.age(today) or 0) > stale_days]
    lines = [f"신호 노트 {len(signals)} · 문제 {len(bad)} · 오래 열림({stale_days}일 초과) {len(stale)}"]
    for s in bad:
        lines += [f"  {s.path.name}: {why}" for why in s.problems]
    for s in stale:
        lines.append(f"  오래 열림: {s.path.name} — {s.age(today)}일째 행선지 없음 — {s.title}")
    if stale:
        lines.append("  행선지는 사람이 고른다: kb signals route … --to <대상> --by <사람> 또는 --drop <이유> --by <사람>")
    return lines, 2 if bad else 0


def listing(signals: list[Signal], today: date, show_all: bool = False) -> list[str]:
    n = {st: sum(1 for s in signals if s.status == st) for st in STATUSES}
    lines = [f"열린 신호 {n['open']} · 행선지 정함 {n['routed']} · 버림 {n['dropped']}"]
    for s in signals:
        if s.status != "open" and not show_all:
            continue
        tail = (f" → {s.fm.get('routed_to')}" if s.status == "routed" else
                f" — 버림: {s.fm.get('dropped_reason')}" if s.status == "dropped" else
                f" · {s.age(today)}일째" if s.age(today) is not None else "")
        lines.append(f"  {s.path.name} [{s.status}] {s.fm.get('source') or '?'}{tail} — {s.title}")
    return lines


# --- candidates from the measurement table ---------------------------------------------------------------------

@dataclass
class Candidate:
    kind: str
    basis: str
    title: str
    observation: str
    evidence: list[str]
    nodes: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.kind}@{self.basis}"


def _collections(data: dict) -> tuple[dict | None, dict | None]:
    """(previous, latest) collection summaries; a file without history has only a latest."""
    hist = data.get("history") or []
    if hist:
        return (hist[-2] if len(hist) > 1 else None), hist[-1]
    latest = {k: data.get(k) for k in ("collected", "evidence", "handoffs", "violations", "git")}
    return None, (latest if data.get("collected") else None)


def _per_handoff(h: dict | None) -> float | None:
    if not h or not h.get("handoffs"):
        return None
    return h.get("pending_items", 0) / h["handoffs"]


def candidates(data: dict, source: str, threshold: float = THRESHOLD) -> list[Candidate]:
    out: list[Candidate] = []
    prev, last = _collections(data)
    at = str((last or {}).get("collected") or "?")
    base = f"앞 수집 {prev.get('collected')}" if prev else "앞 수집 없음(이력이 쌓이기 전)"
    if last:
        ev, pev = last.get("evidence") or {}, (prev or {}).get("evidence") or {}
        for k, label in (("failed", "실패"), ("unstable", "불안정")):
            now, before = ev.get(k), pev.get(k, 0) if prev else 0
            if isinstance(now, int) and now > before:
                out.append(Candidate(f"evidence-{k}", at, f"검증 증거 {label} {now}건",
                                     f"검증 증거 기록에 {label}로 남은 명령이 {now}건이다(앞 수집 {before if prev else '없음'}).",
                                     [f"evidence.{k} = {now} (수집 {at})", f"비교 기준: {base}, {k} {before if prev else '—'} · 문턱 0 초과",
                                      f"원천: {source}"]))
        now, before = _per_handoff(last.get("handoffs")), _per_handoff((prev or {}).get("handoffs"))
        if now is not None and before is not None and now > before:
            h, ph = last["handoffs"], prev["handoffs"]
            out.append(Candidate("handoff-pending", at, f"핸드오프 한 장당 미결 {before:.1f} → {now:.1f}",
                                 "핸드오프 한 장당 평균 미결 항목이 앞 수집보다 늘었다. 미결 수는 누계라 장당 평균으로 본다.",
                                 [f"handoffs {h.get('handoffs')} · pending_items {h.get('pending_items')} → 장당 {now:.2f} (수집 {at})",
                                  f"비교 기준: {base}, handoffs {ph.get('handoffs')} · pending_items {ph.get('pending_items')} → 장당 {before:.2f}",
                                  f"원천: {source}"]))
        g, pg = last.get("git") or {}, (prev or {}).get("git") or {}
        if prev and isinstance(g.get("reverts"), int) and isinstance(pg.get("reverts"), int) and g["reverts"] > pg["reverts"] \
                and g.get("since") == pg.get("since"):
            out.append(Candidate("reverts", at, f"되돌림 {pg['reverts']} → {g['reverts']}",
                                 f"앞 수집 뒤 되돌림 커밋이 {g['reverts'] - pg['reverts']}건 생겼다.",
                                 [f"git.reverts = {g['reverts']} (since {g.get('since')}, 수집 {at})",
                                  f"비교 기준: {base}, reverts {pg['reverts']}", f"원천: {source}"]))
    revs = [(k, v) for k, v in (data.get("revisions") or {}).items() if isinstance(v, dict) and v.get("entry_path_bytes")]
    if len(revs) >= 2:
        (pk, pv), (lk, lv) = revs[-2], revs[-1]
        a, b = pv["entry_path_bytes"], lv["entry_path_bytes"]
        if a and (b - a) / a > threshold:
            out.append(Candidate("entry-path-bytes", f"{pk}..{lk}", f"진입 경로 {a:,}B → {b:,}B (+{(b - a) / a:.0%})",
                                 f"세션 시작 때 읽는 진입 경로가 앞 판보다 {(b - a) / a:.0%} 커졌다.",
                                 [f"revisions.{lk}.entry_path_bytes = {b} ({lv.get('date')})",
                                  f"비교 기준: 앞 판 {pk} = {a} ({pv.get('date')}) · 문턱 {threshold:.0%}", f"원천: {source}"]))
    # every session counts for the order (the latest revision is the one the newest session ran on); "+dirty" is the same
    # revision with local edits. The latest revision's sessions with a first edit (at least MIN_SESSIONS) are compared
    # with the newest BASELINE_SESSIONS such sessions on earlier revisions (at least MIN_SESSIONS) — a revision rarely
    # gathers many sessions, so the baseline pools the revisions before it instead of taking only the one before.
    rev = lambda r: str(r.get("kit_revision") or "").split("+", 1)[0]
    rows = [r for r in (data.get("sessions") or {}).values() if isinstance(r, dict) and rev(r)]
    if rows:
        first: dict[str, str] = {}
        for r in rows:
            first[rev(r)] = min(first.get(rev(r), "~"), str(r.get("start") or "~"))
        lk = max(first, key=first.get)
        tok = "output_tokens_before_first_edit"
        eb = [r[tok] for r in rows if rev(r) == lk and r.get(tok) is not None]
        earlier = sorted((r for r in rows if rev(r) != lk and r.get(tok) is not None and first[rev(r)] < first[lk]),
                         key=lambda r: str(r.get("start") or ""))[-BASELINE_SESSIONS:]
        ea = [r[tok] for r in earlier]
        if len(ea) >= MIN_SESSIONS and len(eb) >= MIN_SESSIONS:
            a, b = statistics.median(ea), statistics.median(eb)
            revs = sorted({rev(r) for r in earlier}, key=first.get)
            if a and (b - a) / a > threshold:
                out.append(Candidate("first-edit-tokens", lk, f"첫 수정까지 출력 토큰 {a:,.0f} → {b:,.0f} (+{(b - a) / a:.0%})",
                                     f"이 판의 세션이 첫 파일 수정까지 쓴 출력 토큰의 중앙값이 앞 판들의 최근 세션보다 {(b - a) / a:.0%} 늘었다.",
                                     [f"kit {lk}: 중앙값 {b:,.0f} (첫 수정이 있는 세션 {len(eb)})",
                                      f"비교 기준: 앞 판 {', '.join(revs)} 의 최근 세션 {len(ea)}: 중앙값 {a:,.0f} · 문턱 {threshold:.0%} · 양쪽 세션 {MIN_SESSIONS} 이상",
                                      "한계: Bash 로 고친 세션은 첫 수정이 늦게 잡힌다(tools/metrics.py 머리말)", f"원천: {source}"]))
    return out


def indicator_candidates(data: dict, source: str) -> list[Candidate]:
    """A product-flow indicator that moved the worse way past its threshold since the collection before (kb indicators)."""
    from kb.indicators import worse
    hist = data.get("history") or []
    if len(hist) < 2:
        return []
    last, prev = hist[-1], hist[-2]
    out = []
    for iid, meta in (data.get("indicators") or {}).items():
        now, before = (last.get("values") or {}).get(iid), (prev.get("values") or {}).get(iid)
        if now is None or before is None:
            continue
        rel = worse(meta, before, now)
        if rel is None:
            continue
        label = meta.get("label") or iid
        out.append(Candidate(f"indicator.{iid}", str(last.get("collected")), f"{label} {before} → {now}",
                             f"제품 흐름 지표 '{label}' 이 앞 수집보다 나빠졌다({meta.get('better')} 이 좋음).",
                             [f"{iid} = {now} (수집 {last.get('collected')})",
                              f"비교 기준: 앞 수집 {prev.get('collected')} = {before} · 문턱 {float(meta.get('threshold', THRESHOLD)):.0%}"
                              + (" (0 에서 나빠짐)" if not before else f" · 변화 {rel:.0%}"),
                              f"원천: {source}"], list(meta.get("nodes") or [])))
    return out


def fresh(cands: list[Candidate], signals: list[Signal]) -> tuple[list[Candidate], list[tuple[Candidate, str]]]:
    """Drop a candidate already written (any status, same kind@basis) or open under the same kind."""
    keep, skipped = [], []
    for c in cands:
        same = next((s for s in signals if s.fm.get("candidate") == c.key), None)
        open_ = next((s for s in signals if s.status == "open" and str(s.fm.get("candidate") or "").split("@")[0] == c.kind), None)
        if same or open_:
            skipped.append((c, (same or open_).path.name))
        else:
            keep.append(c)
    return keep, skipped


def slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()
    return s[:48].strip("-") or "signal"


def write_note(vault: Path, project: str, *, source: str, title: str, observation: str, evidence: list[str] | str,
               observed: date, today: date, candidate: str | None = None, name: str | None = None,
               nodes: list[str] | None = None) -> Path:
    ev = evidence if isinstance(evidence, list) else [evidence]
    if not any(str(e).strip() for e in ev):
        raise ValueError("근거가 비었다 — 측정값과 비교 기준, 또는 로그 위치나 피드백 원문이 있어야 신호가 된다")
    if source not in SOURCES:
        raise ValueError(f"source {source} — {', '.join(SOURCES)} 중 하나")
    d = signals_dir(vault, project)
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{observed.isoformat()}-{slug(name or title)}"
    path, n = d / f"{stem}.md", 2
    while path.exists():
        path, n = d / f"{stem}-{n}.md", n + 1
    fm = {"title": title, "type": "signal", "project": project, "source": source, "observed": observed.isoformat(),
          "status": "open", "created": today.isoformat()}
    if candidate:
        fm["candidate"] = candidate
    if nodes:
        fm["nodes"] = list(nodes)   # the node page joins the signal to the topic (DEC-2026-11-01-18)
    body = (f"\n\n# {title}\n\n## 관찰\n\n{observation.strip() or '비어 있음'}\n\n## 근거\n\n"
            + "\n".join(f"- {e}" for e in ev if str(e).strip())
            + "\n\n## 행선지\n\n비어 있음 — 사람이 고른다(방법론 백로그, 결정, 아이디어, 기획, 버림)\n")
    path.write_text(join(fm, body), encoding="utf-8")
    return path


def route(path: Path, vault: Path, project: str, *, by: str, today: date, to: str | None = None,
          drop: str | None = None) -> list[str]:
    """Record the person's choice. The destination must already exist (it is written separately, in approved words)."""
    if not by.strip():
        raise ValueError("--by 가 비었다 — 행선지를 고른 사람을 적는다")
    if bool(to) == bool(drop):
        raise ValueError("--to 와 --drop 중 하나만")
    fm, body = split(path.read_text(encoding="utf-8"))
    if fm.get("type") != "signal":
        raise ValueError(f"{path.name} 은 신호 노트가 아니다")
    if to:
        ok = target_exists(vault, project, to)
        if ok is False:
            raise ValueError(f"{to} 를 찾지 못했다 — 받는 쪽(백로그 항목·아이디어 노트·기획)을 사람이 승인한 문장으로 먼저 만든다")
        fm.update(status="routed", routed_to=to)
        fm.pop("dropped_reason", None)
        line = f"- {today.isoformat()} {by} 가 고름 → {to}" + (" (외부 대상, 존재는 확인하지 않음)" if ok is None else "")
    else:
        fm.update(status="dropped", dropped_reason=drop)
        fm.pop("routed_to", None)
        line = f"- {today.isoformat()} {by} 가 버림 — {drop}"
    fm.update(decided_by=by, decided=today.isoformat())
    m = re.search(r"(?m)^##[ \t]+(행선지|destination)[ \t]*$", body, re.I)
    if not m:
        body = body.rstrip("\n") + f"\n\n## 행선지\n\n{line}\n"
    else:
        nxt = re.search(r"(?m)^##\s+", body[m.end():])
        end = m.end() + nxt.start() if nxt else len(body)
        block = "\n".join(l for l in body[m.end():end].strip("\n").splitlines() if not PLACEHOLDER.match(l))
        body = body[:m.end()] + "\n\n" + (block + "\n" if block.strip() else "") + line + "\n" + ("\n" if nxt else "") + body[end:]
    path.write_text(join(fm, body), encoding="utf-8")
    return [f"기록: {path.name} {line[2:]}"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb signals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list"); ls.add_argument("--all", action="store_true")
    ck = sub.add_parser("check"); ck.add_argument("--stale-days", type=int, default=STALE_DAYS)
    cd = sub.add_parser("candidates"); cd.add_argument("--write", action="store_true"); cd.add_argument("--threshold", type=float, default=THRESHOLD)
    rt = sub.add_parser("route"); rt.add_argument("note"); rt.add_argument("--to"); rt.add_argument("--drop"); rt.add_argument("--by", required=True)
    for p in (ls, ck, cd, rt):
        p.add_argument("--project", required=True)
        p.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    today = a.today or date.today()
    try:
        if a.cmd == "list":
            print("\n".join(listing(all_signals(vault, a.project), today, a.all)))
            return 0
        if a.cmd == "check":
            lines, rc = check(all_signals(vault, a.project), today, a.stale_days)
            print("\n".join(lines))
            return rc
        if a.cmd == "candidates":
            from kb.indicators import history_path
            mp, ip = metrics_path(vault, a.project), history_path(vault, a.project)
            if not mp.is_file() and not ip.is_file():
                print(f"측정 표·지표 이력 없음: {mp.parent} — tools/metrics.py collect <repo> --write 또는 kb indicators collect --write 먼저")
                return 0
            cands, srcs = [], []
            if mp.is_file():
                srcs.append(str(mp.relative_to(vault)))
                cands += candidates(yaml.safe_load(mp.read_text(encoding="utf-8")) or {}, srcs[-1], a.threshold)
            if ip.is_file():
                srcs.append(str(ip.relative_to(vault)))
                cands += indicator_candidates(yaml.safe_load(ip.read_text(encoding="utf-8")) or {}, srcs[-1])
            keep, skipped = fresh(cands, all_signals(vault, a.project))
            print(f"신호 후보 {len(keep)}" + (f" · 이미 노트가 있어 뺌 {len(skipped)}" if skipped else "") + f" — {', '.join(srcs)}")
            for c in keep:
                print(f"  {c.key}: {c.title}")
                print("\n".join(f"    {e}" for e in c.evidence))
            for c, note in skipped:
                print(f"  뺌 {c.key} — {note}")
            if a.write:
                for c in keep:
                    p = write_note(vault, a.project, source="indicator" if c.kind.startswith("indicator.") else "metrics", title=c.title, observation=c.observation,
                                   evidence=c.evidence, observed=today, today=today, candidate=c.key, name=c.kind, nodes=c.nodes)
                    print(f"  씀: {p.relative_to(vault)} (status open, 행선지는 사람이 고른다)")
            elif keep:
                print("  미리보기 — --write 로 열린 노트를 쓴다(행선지는 비워 둔다)")
            return 0
        p = Path(a.note)
        if not p.is_file():
            p = signals_dir(vault, a.project) / (a.note if a.note.endswith(".md") else a.note + ".md")
        if not p.is_file():
            print(f"노트 없음: {p}", file=sys.stderr)
            return 2
        print("\n".join(route(p, vault, a.project, by=a.by, today=today, to=a.to, drop=a.drop)))
        return 0
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
