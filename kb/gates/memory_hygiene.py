"""memory hygiene — cleanup candidates in one agent memory directory (planning/memory-hygiene, DEC-2026-10-31-13~19·34).

Read-only. The memory lives outside the vault: Claude Code keeps it in ~/.claude/projects/<project path with every
character that is not a letter or digit turned into '-'>/memory/, an index MEMORY.md and one file per fact. The tool
leans on what the harness documents (the directory, MEMORY.md) and uses the front matter fields when they are there
(name, description, type, modified — at the top or under metadata); a file without front matter is shown as an
unknown format. Codex memory is out of scope for the first version (DEC-2026-10-31-13).

Reasons a fact becomes a candidate — rules only, the person judges:
  stale        verified (else modified) older than memory.stale_days (default 60) in ~/.strata/config.yaml
  no date      neither verified nor modified
  status words the text matches a progress-state expression; shown as a match, never as a verdict
  unknown      no front matter
Pairs of feedback facts that share topic words but differ in polarity are shown as possible contradictions, and
the index is compared with the files. Output is names, reasons and evidence (line numbers, matched words, dates),
never the body.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import yaml

STALE_DAYS = 60
INDEX_BUDGET = 12 * 1024   # the kit's always-loaded budget (DEC-2026-10-31-19): a warning, never a failure
STATUS_WORDS = ("다음은", "다음 세션", "다음 할 일", "미커밋", "진행 중", "남은 것", "아직 ", "오늘", "이번 주", "현재 ",
                "TODO", "WIP", "next step", "in progress", "pending", "not yet")
NEGATIVE = ("않", "금지", "말고", "말 것", "never", "don't", "do not", "avoid")
STOP = {"the", "and", "for", "with", "this", "that", "있다", "한다", "없다", "때", "것", "수", "및", "등"}
FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.S)
LINK = re.compile(r"\]\(([^)]+\.md)\)")


def memory_dir_for(project: Path, home: Path | None = None) -> Path:
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(project.resolve()))
    return (home or Path.home()) / ".claude" / "projects" / slug / "memory"


def stale_days() -> int:
    p = Path(os.environ.get("STRATA_USER_CONFIG") or Path.home() / ".strata" / "config.yaml")
    try:
        v = ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("memory") or {}).get("stale_days") if p.is_file() else None
        return int(v) if v else STALE_DAYS
    except Exception:
        return STALE_DAYS


def _field(fm: dict, key: str):
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    return fm.get(key) if fm.get(key) is not None else meta.get(key)


def read_fact(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = FM.match(text)
    fm = {}
    if m:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
    body_start = text[:m.start(2)].count("\n") + 1 if m else 1
    return {"file": path.name, "known": bool(m and isinstance(fm, dict) and fm.get("name")),
            "name": (fm.get("name") if isinstance(fm, dict) else None) or path.stem,
            "type": _field(fm, "type") if isinstance(fm, dict) else None,
            "description": str(_field(fm, "description") or "") if isinstance(fm, dict) else "",
            "verified": str(_field(fm, "verified") or "")[:10] if isinstance(fm, dict) else "",
            "modified": str(_field(fm, "modified") or "")[:10] if isinstance(fm, dict) else "",
            "body": m.group(2) if m else text, "body_start": body_start}


def _words(f: dict) -> set[str]:
    raw = re.split(r"[\s\-_/·,.()「」'\"`:;]+", f"{f['name']} {f['description']}".lower())
    return {w for w in raw if len(w) >= 2 and w not in STOP and not w.isdigit()}


def _negative(f: dict) -> bool:
    t = f"{f['description']} {f['body']}".lower()
    return any(n in t for n in NEGATIVE)


def report(mem: Path, today: date | None = None, days: int | None = None) -> dict:
    today = today or date.today()
    days = days or stale_days()
    out = {"dir": str(mem), "exists": mem.is_dir(), "facts": 0, "index_bytes": 0, "index_over_budget": False,
           "stale_days": days, "candidates": [], "pairs": [], "index_only": [], "file_only": []}
    if not mem.is_dir():
        return out
    index = mem / "MEMORY.md"
    linked: list[str] = []
    if index.is_file():
        it = index.read_text(encoding="utf-8", errors="replace")
        out["index_bytes"] = len(it.encode("utf-8"))
        out["index_over_budget"] = out["index_bytes"] > INDEX_BUDGET
        linked = LINK.findall(it)
    facts = [read_fact(p) for p in sorted(mem.glob("*.md")) if p.name != "MEMORY.md"]
    out["facts"] = len(facts)
    names = {f["file"] for f in facts}
    out["index_only"] = sorted(set(linked) - names)
    out["file_only"] = sorted(names - set(linked))
    for f in facts:
        reasons = []
        if not f["known"]:
            reasons.append({"kind": "unknown", "evidence": "머리말 없음(형식 모름)"})
        when = f["verified"] or f["modified"]
        if not when:
            reasons.append({"kind": "no_date", "evidence": "verified·modified 없음"})
        else:
            try:
                age = (today - date.fromisoformat(when)).days
                if age > days:
                    reasons.append({"kind": "stale", "evidence": f"{'verified' if f['verified'] else 'modified'} {when} ({age}일)"})
            except ValueError:
                reasons.append({"kind": "no_date", "evidence": f"날짜 형식 모름: {when}"})
        hits: dict[str, list[int]] = {}
        for i, line in enumerate(f["body"].splitlines(), start=f["body_start"]):
            hit = next((w for w in STATUS_WORDS if w.lower() in line.lower()), None)
            if hit:
                hits.setdefault(hit.strip(), []).append(i)
        if hits:   # a match, never a verdict: a rule that names a state ("if uncommitted files remain, …") matches too
            reasons.append({"kind": "status_words", "evidence": "; ".join(
                f"{'·'.join(map(str, ls))}행 '{w}'" for w, ls in hits.items()) + " 표현 일치"})
        if reasons:
            out["candidates"].append({"name": f["name"], "file": f["file"], "type": f["type"], "reasons": reasons})
    fb = [f for f in facts if f["type"] == "feedback"]
    for i, a in enumerate(fb):
        for b in fb[i + 1:]:
            shared = sorted(_words(a) & _words(b))
            if len(shared) >= 2 and _negative(a) != _negative(b):
                out["pairs"].append({"a": a["name"], "b": b["name"], "shared": shared[:6]})
    return out


LABEL = {"stale": "오래됨", "no_date": "날짜 없음", "status_words": "상태성 표현", "unknown": "형식 모름"}


def counts(r: dict) -> dict:
    c = {k: 0 for k in LABEL}
    for x in r["candidates"]:
        for k in {y["kind"] for y in x["reasons"]}:
            c[k] += 1
    return c


def render(r: dict, top: int = 20) -> list[str]:
    if not r["exists"]:
        return [f"메모리 — {r['dir']}: 없음"]
    c = counts(r)
    L = [f"메모리 — {r['dir']} (vault 밖, Claude Code 프로젝트 메모리; 읽기만 한다)",
         f"  항목 {r['facts']} · 인덱스 {r['index_bytes']}B" + (f" — 경고: kit 예산 {INDEX_BUDGET}B 초과" if r["index_over_budget"] else "")
         + " · 후보: " + ", ".join(f"{LABEL[k]} {v}" for k, v in c.items()) + f" · 반대 피드백 후보 {len(r['pairs'])}"
         + f" (오래됨 기준 {r['stale_days']}일)"]
    for x in r["candidates"][:top]:
        L.append(f"  - {x['name']} [{x['type'] or '?'}]: " + "; ".join(f"{LABEL[y['kind']]} — {y['evidence']}" for y in x["reasons"]))
    if len(r["candidates"]) > top:
        L.append(f"  … 그 밖 {len(r['candidates']) - top}건")
    for p in r["pairs"][:top]:
        L.append(f"  ⇄ {p['a']} · {p['b']} — 겹친 주제어: {', '.join(p['shared'])}")
    if r["index_only"]:
        L.append("  인덱스에만 있음: " + ", ".join(r["index_only"]))
    if r["file_only"]:
        L.append("  파일만 있음(인덱스에 없음): " + ", ".join(r["file_only"]))
    L.append("  정리는 사람이 항목마다 승인한 것만: 진행 상태는 핸드오프로 옮기고, 지울 것은 _archive/ 로 옮겨 retired·retired_reason 을 적고 인덱스 줄을 뺀다 (DEC-2026-10-31-17·34)")
    return L
