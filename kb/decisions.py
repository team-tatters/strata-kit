"""Decision records — status derivation shared by the DEC-note generator and the decision writer.

Record = (path, body) where body is the `decision:` mapping of one DEC-*.yaml. This module is the canonical
derive_status (DEC-2026-09-30-03 for the rule); the decision writer kb.legacy.decision still keeps its own copy.
"""
from __future__ import annotations

from pathlib import Path



import re

DEC_ID_RE = re.compile(r"DEC-\d{4}-\d{2}-\d{2}-\d{2}")


def _dec_ids(value) -> list[str]:
    """ids named by a supersedes field — a list, or a legacy free string; never the string's characters."""
    if not value:
        return []
    out: list[str] = []
    for item in (value if isinstance(value, list) else [value]):
        for m in DEC_ID_RE.findall(str(item)):
            if m not in out:
                out.append(m)
    return out

def derive_status(records: list[tuple[Path, dict]]) -> dict[str, tuple[str, list[str]]]:
    """id → (status, superseded_by). status ∈ active | superseded | withdrawn.

    superseded 는 다른 레코드의 supersedes 로부터 유도한다 (대체된 쪽 파일은 고치지 않는다).
    withdrawn 은 레코드에 명시된 경우만. 둘 다 해당하면 superseded 가 우선한다.
    """
    by: dict[str, list[str]] = {}
    for _, body in records:
        if str(body.get("status") or "").strip() == "withdrawn":
            continue   # a withdrawn record retires nothing (same rule as kb/legacy/decision.py)
        for old in _dec_ids(body.get("supersedes")):
            by.setdefault(str(old).strip(), []).append(str(body["id"]))
    out: dict[str, tuple[str, list[str]]] = {}
    for _, body in records:
        rid = str(body["id"])
        if rid in by:
            out[rid] = ("superseded", sorted(by[rid]))
        elif str(body.get("status") or "").strip() == "withdrawn":
            out[rid] = ("withdrawn", [])
        else:
            out[rid] = ("active", [])
    return out
