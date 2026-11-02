"""Divergence judgement — plan versus implementation (planning/divergence-judgement, DEC-2026-10-31-35).

When a plan and the code disagree, a person decides which side is wrong; the agent only gathers the evidence and
queues the question. Requests live in one file per project, the vault's projects/<p>/_meta/divergence-inbox.yaml (a
file of record: people write judgements in it, and the gate's merge never drops one). Four judgements:

  consistent    no divergence after all (the file changed, the behaviour the plan describes did not)
  doc_stale     the code is right; bring the plan or the as-built specification up to the code
  plan_gap      the plan missed something; ask the plan's owner (front matter `owner`, else the user)
  impl_defect   the code is wrong; open a bug task

Judging sets the plan's implementation.reviewed to today, so the coverage gate stops asking to recheck it for the
code that changed before; implementation.status stays with the agent (strata.spec step 5), by the judgement.

  python3 -m kb divergence list   --project P [--all]
  python3 -m kb divergence add    --project P --planning PATH [--spec PATH] --diff TEXT [--evidence TEXT] [--source review]
  python3 -m kb divergence judge  --project P ID --as consistent|doc_stale|plan_gap|impl_defect --by NAME [--note TEXT]
  python3 -m kb divergence count  --project P
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from kb import vault_root

JUDGEMENTS = {
    "consistent": ("정합(차이 아님)", "기획 문서의 대조 날짜만 갱신된다. 할 일 없음"),
    "doc_stale": ("문서가 낡음", "기획·as-built 명세를 구현에 맞춘다 — strata.kb-update, strata.spec 5단계로 implementation.status 갱신"),
    "plan_gap": ("기획 누락", "기획 소유자 {owner} 에게 보완을 요청한다 — 답을 받으면 strata.spec 으로 기획을 고친다"),
    "impl_defect": ("구현 결함", "구현을 기획에 맞추는 버그 태스크를 연다 — strata.order"),
}
HEAD = ("# 어긋남 판정 Inbox (planning/divergence-judgement, DEC-2026-10-31-35) — 판정은 사람만 한다.\n"
        "# python3 -m kb divergence judge --project <p> <id> --as <판정> --by <이름> 으로 기록한다. 게이트가 덧써도 판정은 지우지 않는다.\n")
FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.S)


def inbox_path(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "_meta" / "divergence-inbox.yaml"


def load(vault: Path, project: str) -> dict:
    p = inbox_path(vault, project)
    d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else {}
    return {"project": project, "requests": list(d.get("requests") or [])}


def save(vault: Path, project: str, data: dict) -> Path:
    p = inbox_path(vault, project)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HEAD + yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    return p


def _next_id(reqs: list[dict]) -> str:
    n = max([int(str(r.get("id", "DV-0")).split("-")[-1]) for r in reqs if str(r.get("id", "")).startswith("DV-")] or [0])
    return f"DV-{n + 1}"


def add(vault: Path, project: str, planning: str, spec: str | None, diff: str, evidence: str = "", source: str = "review",
        paths: list[str] | None = None, today: str | None = None) -> tuple[dict, bool]:
    """Queue one request; a pending request for the same plan and specification is not queued twice."""
    data = load(vault, project)
    for r in data["requests"]:
        if r.get("status") == "pending" and r.get("planning") == planning and r.get("spec") == spec:
            return r, False
    r = {"id": _next_id(data["requests"]), "status": "pending", "source": source, "planning": planning, "spec": spec,
         "paths": sorted(paths or []), "diff": diff, "evidence": evidence, "queued": today or date.today().isoformat()}
    data["requests"].append(r)
    save(vault, project, data)
    return r, True


def from_gate(vault: Path, project: str, rows: list[dict], since: str, today: str | None = None) -> list[str]:
    """The coverage gate's recheck rows (a plan marked implemented whose code changed) become requests."""
    added = []
    for row in rows:
        if row.get("action") != "recheck":
            continue
        r, new = add(vault, project, row["planning"], row["spec"],
                     f"구현됨으로 표시된 기획의 코드가 {since} 이후 바뀜 — 기획과 맞는지 판정 필요",
                     "바뀐 경로: " + ", ".join(row.get("paths", [])[:5]), "gate", row.get("paths"), today)
        if new:
            added.append(r["id"])
    return added


def _owner(vault: Path, planning: str) -> str:
    p = vault / planning
    m = FM.match(p.read_text(encoding="utf-8")) if p.is_file() else None
    fm = (yaml.safe_load(m.group(1)) or {}) if m else {}
    return str(fm.get("owner") or "사용자")


def set_reviewed(vault: Path, planning: str, day: str) -> bool:
    """implementation.reviewed ← day in the plan's front matter, touching nothing else."""
    p = vault / planning
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    m = FM.match(text)
    if not m:
        return False
    fm = m.group(1)
    if re.search(r"^implementation:\s*$", fm, re.M):
        block = re.search(r"^implementation:\s*\n((?:[ \t]+.*\n?)*)", fm + "\n", re.M)
        body = block.group(1)
        if re.search(r"^[ \t]+reviewed:", body, re.M):
            body2 = re.sub(r"^([ \t]+reviewed:).*$", rf"\g<1> {day}", body, count=1, flags=re.M)
        else:
            indent = re.match(r"[ \t]+", body).group(0) if body.strip() else "  "
            body2 = body.rstrip("\n") + f"\n{indent}reviewed: {day}\n"
        fm2 = fm[:block.start(1)] + body2.rstrip("\n") + fm[block.end(1):].rstrip("\n")
    else:
        fm2 = fm.rstrip("\n") + f"\nimplementation:\n  reviewed: {day}"
    p.write_text(text[:m.start(1)] + fm2.rstrip("\n") + text[m.end(1):], encoding="utf-8")
    return True


def judge(vault: Path, project: str, rid: str, value: str, by: str, note: str = "", today: str | None = None) -> tuple[dict, str]:
    if value not in JUDGEMENTS:
        raise ValueError(f"판정은 {', '.join(JUDGEMENTS)} 중 하나 — {value!r}")
    if not by.strip():
        raise ValueError("판정한 사람(--by)이 필요하다 — 판정은 사람만 한다")
    day = today or date.today().isoformat()
    data = load(vault, project)
    r = next((x for x in data["requests"] if x.get("id") == rid), None)
    if r is None:
        raise ValueError(f"요청 {rid} 없음")
    label, nxt = JUDGEMENTS[value]
    nxt = nxt.format(owner=_owner(vault, r["planning"]))
    r.update({"status": "judged", "judgement": value, "by": by, "judged": day, "next": nxt, **({"note": note} if note else {})})
    save(vault, project, data)
    set_reviewed(vault, r["planning"], day)
    return r, f"{rid} 판정: {label} ({by}, {day}) — 다음: {nxt}"


def pending(vault: Path, project: str) -> list[dict]:
    return [r for r in load(vault, project)["requests"] if r.get("status") == "pending"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb divergence", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "add", "judge", "count"):
        s = sub.add_parser(name)
        s.add_argument("--project", required=True)
        s.add_argument("--vault", default=None)
        if name == "list":
            s.add_argument("--all", action="store_true")
        if name == "add":
            s.add_argument("--planning", required=True, help="vault 기준 경로 projects/<p>/planning/….md")
            s.add_argument("--spec", default=None)
            s.add_argument("--diff", required=True)
            s.add_argument("--evidence", default="")
            s.add_argument("--source", default="review")
        if name == "judge":
            s.add_argument("id")
            s.add_argument("--as", dest="value", required=True, choices=list(JUDGEMENTS))
            s.add_argument("--by", required=True)
            s.add_argument("--note", default="")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve() if a.vault else vault_root()
    if vault is None:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    if a.cmd == "count":
        print(len(pending(vault, a.project)))
    elif a.cmd == "list":
        rows = load(vault, a.project)["requests"] if a.all else pending(vault, a.project)
        for r in rows:
            j = f" → {JUDGEMENTS[r['judgement']][0]} ({r.get('by')}, {r.get('judged')})" if r.get("judgement") in JUDGEMENTS else ""
            print(f"{r['id']} [{r['status']}] {r['planning']} ↔ {r.get('spec') or '-'}: {r['diff']}{j}")
        print(f"대기 {len(pending(vault, a.project))} · 전체 {len(load(vault, a.project)['requests'])} — {inbox_path(vault, a.project)}")
    elif a.cmd == "add":
        r, new = add(vault, a.project, a.planning, a.spec, a.diff, a.evidence, a.source)
        print(("추가: " if new else "이미 대기 중: ") + r["id"])
    else:
        try:
            _, line = judge(vault, a.project, a.id, a.value, a.by, a.note)
        except ValueError as e:
            print(f"거부: {e}", file=sys.stderr)
            return 2
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
