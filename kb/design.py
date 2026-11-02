"""kb design check — design fields of screen tasks (planning/design-stage, DEC-2026-11-01-07 · 09).

A task is a screen task when its inputs carry a design_ref, or its order (_order.yaml beside it) declares an
entry_point. For each screen task the check reports:
  no-design-ref     the order declares an entry_point but the task has no inputs.design_ref
  none-no-reason    design_ref.kind is none with no reason
  no-sync           completion.status is completed but completion.design_sync is missing
  stale             completed while design_sync is stale (stale cannot be declared complete)
  bad-sync          design_sync is not one of aligned · stale · waived · none
  waived-no-until   waived without a reason and an 'until YYYY-MM-DD'
  waived-expired    waived past its until date
Tasks that are not screen tasks are not read further. Fields: methodology/task-spec-schema.

A contract-side tool (DEC-2026-11-01-09): the design pack's briefs and other markdown are never read.

  python3 -m kb design check <task file | order folder | tasks folder>... [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

SYNC = ("aligned", "stale", "waived", "none")
LABEL = {"no-design-ref": "design_ref 없음 (오더가 entry_point 를 선언함)",
         "none-no-reason": "design_ref.kind: none 인데 사유 없음",
         "no-sync": "완료인데 design_sync 없음",
         "stale": "design_sync: stale 인 채로 완료 — 정합 회복 전에는 완료가 아니다",
         "bad-sync": "design_sync 값이 aligned·stale·waived·none 이 아님",
         "waived-no-until": "waived 인데 사유나 'until YYYY-MM-DD' 가 없음",
         "waived-expired": "waived 만료가 지남"}


def _load(p: Path) -> dict:
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return d if isinstance(d, dict) else {}


def task_files(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(p.rglob("task-*.yaml")))
    return out


def check_task(path: Path, today: date) -> list[str]:
    t = _load(path)
    order = _load(path.parent / "_order.yaml").get("order") or {}
    ref = (t.get("inputs") or {}).get("design_ref")
    if not ref and not order.get("entry_point"):
        return []                                             # not a screen task
    out = []
    if not ref:
        return ["no-design-ref"]
    ref = ref if isinstance(ref, dict) else {}
    if ref.get("kind") == "none" and not str(ref.get("reason") or "").strip():
        out.append("none-no-reason")
    comp = t.get("completion") or {}
    if not isinstance(comp, dict) or comp.get("status") != "completed":
        return out
    sync = comp.get("design_sync")
    if not sync:
        out.append("no-sync")
    elif sync not in SYNC:
        out.append("bad-sync")
    elif sync == "stale":
        out.append("stale")
    elif sync == "waived":
        reason = str(comp.get("design_sync_reason") or "")
        m = re.search(r"until\s+(\d{4}-\d{2}-\d{2})", reason)
        if not m or not reason.replace(m.group(0), "").strip(" .,;:—-"):
            out.append("waived-no-until")
        elif date.fromisoformat(m.group(1)) < today:
            out.append("waived-expired")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb design", description="contract-side check of screen tasks (DEC-2026-11-01-09)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    c.add_argument("--today", help="YYYY-MM-DD (default today)")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    paths = [Path(p) for p in a.paths]
    files = task_files([p for p in paths if p.suffix != ".md"])   # markdown (briefs) is never read
    problems = 0
    screen = 0
    for f in files:
        r = check_task(f, today)
        t = _load(f)
        is_screen = bool((t.get("inputs") or {}).get("design_ref") or (_load(f.parent / "_order.yaml").get("order") or {}).get("entry_point"))
        screen += is_screen
        for k in r:
            print(f"{f}: {LABEL[k]}")
        problems += len(r)
    print(f"태스크 {len(files)} · 화면 태스크 {screen} · 문제 {problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
