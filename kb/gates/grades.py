"""Check grades (order 2026.10.29-02, MB-strata-kit-2026-003): every gate, hook and verify finding carries one grade.

  block     the work cannot go on; no override
  default   fails unless an override with a reason and an expiry date covers it
  advisory  reported, never fails

Overrides live in a tracked file — the checked project's Tier P gate-overrides.yaml, or the vault's
_meta/gate-overrides.yaml for vault gates:

  overrides:
  - {check: verify, key: budget_with_inherited, reason: "...", until: 2026-11-05, by: alice}

`key` is an fnmatch pattern over the finding key; an override past its `until` has no effect and is listed as expired.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from datetime import date
from pathlib import Path

GRADES = ("block", "default", "advisory")


@dataclass(frozen=True)
class Finding:
    check: str
    key: str
    grade: str
    message: str

    def __post_init__(self):
        if self.grade not in GRADES:
            raise ValueError(f"unknown grade {self.grade!r} (one of {', '.join(GRADES)})")


def load_overrides(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    import yaml
    rows = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("overrides") or []
    return [{**r, "until": str(r.get("until", ""))} for r in rows if isinstance(r, dict)]


def evaluate(findings: list[Finding], overrides: list[dict], today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    out = {"blocked": [], "unresolved": [], "overridden": [], "advisory": [], "expired": [], "invalid": []}
    for f in findings:
        if f.grade == "advisory":
            out["advisory"].append(f)
            continue
        if f.grade == "block":
            out["blocked"].append(f)
            continue
        match = [o for o in overrides if o.get("check") == f.check and fnmatch.fnmatchcase(f.key, str(o.get("key", "")))]
        # an override is a reasoned, dated exception: without both it has no effect (order 2026.10.31-04)
        bad = [o for o in match if not str(o.get("reason") or "").strip() or not str(o.get("until") or "").strip()]
        out["invalid"] += [(f, o) for o in bad]
        match = [o for o in match if o not in bad]
        live = [o for o in match if o["until"] >= today]
        if live:
            out["overridden"].append((f, live[0]))
        else:
            out["unresolved"].append(f)
            out["expired"] += [(f, o) for o in match]
    out["rc"] = 2 if out["blocked"] or out["unresolved"] else 0
    return out


def render(r: dict) -> list[str]:
    L = [f"BLOCK  {f.check} {f.key} — {f.message}" for f in r["blocked"]]
    L += [f"FAIL   {f.check} {f.key} — {f.message} (default: 사유·기한으로 덮어쓸 수 있음)" for f in r["unresolved"]]
    L += [f"       └ 기한 지난 덮어쓰기: {o.get('reason')} (~{o['until']})" for _f, o in r["expired"]]
    L += [f"       └ 무효 덮어쓰기(사유·기한 필수): key {o.get('key')!r} reason {o.get('reason')!r} until {o.get('until') or '-'}"
          for _f, o in r.get("invalid", [])]
    L += [f"pass   {f.check} {f.key} — 덮어씀: {o.get('reason')} (~{o['until']})" for f, o in r["overridden"]]
    L += [f"note   {f.check} {f.key} — {f.message}" for f in r["advisory"]]
    return L
