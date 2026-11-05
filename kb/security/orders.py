"""Orders (spec AC6, Tech Spec G6, DEC-2026-11-03-02·04): every urgent item becomes one order — one file per
(vulnerability, host or repository), listing the targets it covers — at projects/<attributed>/tasks/<YYYY.MM.DD>/NN-sec-<id>/,
attributed to infra by default. The same pair never gets a second order while one is open; its last_seen moves instead.
Advisories never become orders on their own: a person promotes one. A person can also move an order to another project.

  python3 -m kb security order [--date D]                      urgent items without an order → orders
  python3 -m kb security promote <match-id> --by NAME [--to P]  an advisory becomes an order
  python3 -m kb security assign <order-ref> --to P --by NAME    attribution changes (file stays, history grows)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from kb.security import grade as G
from kb.security.store import Store, now_iso, store_path

DEFAULT_PROJECT = "infra"   # DEC-2026-11-03-04


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", s).strip("-").lower()[:60]


def open_orders(vault: Path) -> dict[tuple[str, str], Path]:
    """(host-or-repo, vuln_id) → _order.yaml of every open security order."""
    out = {}
    for p in vault.glob("projects/*/tasks/*/*-sec-*/_order.yaml"):
        doc = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("order") or {}
        if doc.get("kind") == "security-patch" and doc.get("status") in ("open", "in-progress"):
            out[(doc.get("host"), doc.get("vuln_id"))] = p
    return out


def next_dir(vault: Path, project: str, day: str, vuln_id: str) -> Path:
    d = vault / "projects" / project / "tasks" / day.replace("-", ".")
    n = len([x for x in d.glob("*/_order.yaml")]) + 1 if d.is_dir() else 1
    return d / f"{n:02d}-sec-{slug(vuln_id)}"


def due_for(vault: Path, project: str, record: dict, day: date) -> str:
    g = G.load_grading(vault, project)
    dd = g["default"].get("due_days") or {}
    days = int(dd.get("kev", 3)) if record.get("kev") else int(dd.get("urgent", 14))
    return (day + timedelta(days=days)).isoformat()


def build_order(day: str, host: str, vuln_id: str, rows: list[dict], record: dict, project: str, due: str, promoted_by: str | None = None) -> dict:
    g = rows[0]
    return {"order": {
        "id": f"{day.replace('-', '.')}-sec-{slug(vuln_id)}", "kind": "security-patch", "title": f"{vuln_id} — {host}: {(record.get('title') or '')[:80]}",
        "date": day, "project": project, "attributed_to": project, "status": "open", "host": host, "vuln_id": vuln_id,
        "grade": g.get("grade"), "promoted_by": promoted_by, "priority": g.get("sort_key"), "due": due,
        "targets": [{"target_ref": r["target_ref"], "version": (r.get("detail") or {}).get("target_version"), "fixed": (r.get("detail") or {}).get("fixed"),
                     "match_id": r["id"]} for r in rows],
        "evidence": {"source_url": record.get("source_url"), "record_id": g["record_id"], "match_ref": f"security/matches/{day}.yaml#{g['id']}",
                     "scores": record.get("scores"), "kev": record.get("kev"), "epss": record.get("epss"), "reason": g.get("reason"),
                     "severity": g.get("severity"), "severity_from": g.get("severity_from"), "threshold": g.get("threshold")},
        "acceptance": ["패치 또는 수용된 리스크 뒤 다음 노트의 미조치 절에서 빠지고 닫힌 항목 절에 한 번 나온다 (AC12)"],
        "patch_plan": None, "acceptance_record": None, "execution": [], "history": [{"at": now_iso(), "event": "created", "by": promoted_by or "kb security order"}],
        "first_seen": g.get("first_seen") or day, "last_seen": day,
    }}


def write_order(path: Path, doc: dict) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    f = path / "_order.yaml"
    f.write_text("# 보안 오더 — 생성본(python3 -m kb security order|promote). 귀속·수락·실행 기록은 명령으로만 바꾼다 (DEC-2026-11-03-02·04)\n"
                 + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    return f


def host_of(target_ref: str) -> str:
    parts = target_ref.split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else target_ref


def create_orders(vault: Path, day: date, store: Store, only_grade: str = "urgent", match_ids: list[str] | None = None, by: str | None = None,
                  to_project: str | None = None) -> list[Path]:
    d = day.isoformat()
    matches = store.matches_on(d)
    rows = [m for m in matches if (match_ids and m["id"] in match_ids) or (not match_ids and m.get("grade") == only_grade)]
    existing = open_orders(vault)
    groups: dict[tuple[str, str], list[dict]] = {}
    for m in rows:
        groups.setdefault((host_of(m["target_ref"]), m["vuln_id"]), []).append(m)
    made = []
    for (host, vid), grp in groups.items():
        rec = store.record(grp[0]["record_id"]) or {}
        if (host, vid) in existing:
            p = existing[(host, vid)]
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            doc["order"]["last_seen"] = d
            p.write_text(p.read_text(encoding="utf-8").split("\n", 1)[0] + "\n" + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
            ref = str(p.relative_to(vault))
        else:
            project = to_project or DEFAULT_PROJECT
            p = write_order(next_dir(vault, project, d, vid), build_order(d, host, vid, grp, rec, project, due_for(vault, project, rec, day), by))
            ref = str(p.relative_to(vault))
            made.append(p)
        for m in grp:
            store.set_order_ref(m["target_ref"], vid, ref)
    return made


def assign(vault: Path, ref: str, to_project: str, by: str) -> Path:
    p = (vault / ref) if not Path(ref).is_absolute() else Path(ref)
    if p.is_dir():
        p = p / "_order.yaml"
    head, body = p.read_text(encoding="utf-8").split("\n", 1)
    doc = yaml.safe_load(body)
    before = doc["order"].get("attributed_to")
    doc["order"]["attributed_to"] = to_project
    doc["order"]["history"].append({"at": now_iso(), "event": "assigned", "from": before, "to": to_project, "by": by})
    p.write_text(head + "\n" + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("order"); o.add_argument("--date", type=date.fromisoformat, default=None)
    pr = sub.add_parser("promote"); pr.add_argument("match_id"); pr.add_argument("--by", required=True); pr.add_argument("--to"); pr.add_argument("--date", type=date.fromisoformat, default=None)
    asg = sub.add_parser("assign"); asg.add_argument("ref"); asg.add_argument("--to", required=True); asg.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    if a.cmd == "assign":
        p = assign(vault, a.ref, a.to, a.by)
        print(f"귀속 → {a.to} (by {a.by}) · {p.relative_to(vault)}")
        return 0
    day = a.date or date.today()
    store = Store(store_path(vault))
    try:
        if a.cmd == "order":
            made = create_orders(vault, day, store)
        else:
            day_of = a.match_id.split(":", 1)[0]
            made = create_orders(vault, date.fromisoformat(day_of), store, match_ids=[a.match_id], by=a.by, to_project=a.to)
            if not made:
                print("오더가 만들어지지 않았다 — 대조 id 가 그날의 matches 에 없거나 이미 열린 오더가 있다", file=sys.stderr)
                return 3
    finally:
        store.close()
    print(f"오더 {len(made)}건" + ("".join(f"\n  {p.relative_to(vault)}" for p in made) if made else " — 새로 만든 것 없음(열린 오더는 last_seen 갱신)"))
    return 0
