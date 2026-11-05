"""Close and accept (spec AC11·AC12, DEC-2026-11-03-02, rec.data.soft-delete-only): closing an order marks it closed with
who, when and why and closes the (target, vulnerability) pairs it covered, so the next note shows them once under closed
items and never again; nothing is deleted. An accepted risk is a row in projects/<p>/security/accepted-risks.yaml with a
reason, a term and the person — without a term it is refused; inside the term the pair is filtered, after it the pair
shows again as expired.

  python3 -m kb security close <order-ref> --by NAME [--reason patched|not-affected|duplicate|superseded|accepted]
  python3 -m kb security accept --project P --target <target_ref> --vuln <id> --reason "..." --until YYYY-MM-DD --by NAME
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from kb.security import grade as G
from kb.security.store import Store, now_iso, store_path

REASONS = ("patched", "not-affected", "duplicate", "superseded", "accepted")


def load_order(vault: Path, ref: str) -> tuple[Path, str, dict]:
    p = (vault / ref) if not Path(ref).is_absolute() else Path(ref)
    if p.is_dir():
        p = p / "_order.yaml"
    head, body = p.read_text(encoding="utf-8").split("\n", 1)
    return p, head, yaml.safe_load(body)


def save_order(p: Path, head: str, doc: dict) -> None:
    p.write_text(head + "\n" + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")


def close_order(vault: Path, ref: str, by: str, reason: str, store: Store, day: date | None = None) -> Path:
    if reason not in REASONS:
        raise ValueError(f"reason 은 {', '.join(REASONS)} 중 하나")
    p, head, doc = load_order(vault, ref)
    o = doc["order"]
    d = (day or date.today()).isoformat()
    o["status"] = "closed"
    o["closed"] = {"at": now_iso(), "by": by, "reason": reason, "day": d}
    o.setdefault("history", []).append({"at": now_iso(), "event": "closed", "reason": reason, "by": by})
    save_order(p, head, doc)
    for t in o.get("targets") or []:
        store.set_closed(t["target_ref"], o["vuln_id"], d, str(p.relative_to(vault)))
    return p


def accept(vault: Path, project: str, target_ref: str, vuln_id: str, reason: str, until: str, by: str, at: str | None = None) -> Path:
    if not until:
        raise ValueError("기한(--until) 없는 수락은 받지 않는다 — 수용된 리스크는 기한을 가진다 (AC11)")
    date.fromisoformat(until)
    if not reason or not reason.strip():
        raise ValueError("사유(--reason)가 비었다")
    p = G.accepted_path(vault, project)
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else None
    doc = doc or {"version": "0.1", "accepted": []}
    doc["accepted"].append({"target_ref": target_ref, "vuln_id": vuln_id, "reason": reason, "until": until, "by": by, "at": at or now_iso(), "status": "active"})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# 수용된 리스크 — 명령으로만 늘어난다(python3 -m kb security accept). 지우지 않고 status 로 남긴다; 기한이 지나면 노트에 다시 뜬다 (AC11, soft-delete-only)\n"
                 + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("close"); c.add_argument("ref"); c.add_argument("--by", required=True); c.add_argument("--reason", default="patched", choices=REASONS)
    c.add_argument("--date", type=date.fromisoformat, default=None)
    a_ = sub.add_parser("accept")
    for k in ("--project", "--target", "--vuln", "--reason", "--until", "--by"):
        a_.add_argument(k, required=True)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    try:
        if a.cmd == "accept":
            p = accept(vault, a.project, a.target, a.vuln, a.reason, a.until, a.by)
            print(f"수용된 리스크 추가: {a.target} · {a.vuln} · until {a.until} (by {a.by}) → {p.relative_to(vault)}")
            return 0
        store = Store(store_path(vault))
        try:
            p = close_order(vault, a.ref, a.by, a.reason, store, a.date)
        finally:
            store.close()
        print(f"닫힘 ({a.reason}, by {a.by}) → {p.relative_to(vault)}")
        return 0
    except ValueError as e:
        print(e, file=sys.stderr)
        return 3
