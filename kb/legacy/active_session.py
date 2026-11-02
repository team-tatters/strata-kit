"""Which active file is this session's (planning/active-file-and-compact-hooks, DEC-2026-08-19-05, DEC-2026-10-31-08).

Per-session files live in .strata/local/active/. A file is this session's when its name is the harness session id
(`<session_id>.yaml`) or its `harness_session_id` field holds that id (a string or a list — a resumed session adds its
new id). Files are named for people (session-2026-10-31-spec-questions.yaml), so the field is the usual link; the
agent writes it from CLAUDE_CODE_SESSION_ID when it creates the file.

- compact: only this session's file. Another session's file is never the restore target; its count is told.
- otherwise (startup, resume, clear, or a hand run with no session id): this session's file if there is one, else the
  newest file, named, as now. The single legacy active-task.yaml is read only when no per-session file exists.

The snapshot hook (pre_compact_snapshot.py) and the start header (tools/wizard.py) both pick through here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Pick:
    path: Path | None   # the file to read, or None
    label: str          # where it came from, for the header line: "active/x.yaml", "legacy active-task.yaml", ...
    own: bool           # the file is this session's
    others: int         # per-session files that are not the picked one


def _ids(path: Path) -> set[str]:
    try:
        a = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    v = a.get("harness_session_id") if isinstance(a, dict) else None
    return {str(x) for x in (v if isinstance(v, list) else [v]) if x}


def pick(local: Path, session_id: str | None = None, source: str | None = None) -> Pick:
    """local is <project>/.strata/local."""
    d = local / "active"
    files = sorted(d.glob("*.yaml"), key=lambda f: f.stat().st_mtime, reverse=True) if d.is_dir() else []
    if session_id:
        own = [f for f in files if f.stem == session_id or session_id in _ids(f)]
        if own:
            n = len(files) - 1
            return Pick(own[0], f"active/{own[0].name}" + (f", {n} other" if n else ""), True, n)
        if source == "compact" and files:
            return Pick(None, "no active file for this session" + (f", {len(files)} other session file(s) not used" if files else ""),
                        False, len(files))
    if files:
        n = len(files) - 1
        return Pick(files[0], f"active/{files[0].name}" + (f", {n} older" if n else ""), False, n)
    legacy = local / "active-task.yaml"
    if legacy.is_file():
        return Pick(legacy, "legacy active-task.yaml", False, 0)
    return Pick(None, "no active file", False, 0)
