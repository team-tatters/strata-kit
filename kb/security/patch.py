"""Conditional patch (spec AC7, DEC-2026-11-03-02): the core patches only when one of three conditions holds — the change is
code level or has no downtime, the swap takes minutes, or the person recorded an acceptance of the downtime. `plan`
names the executor and the condition and writes the plan into the order; `run` refuses without a holding condition
(exit 3) and refuses a user-accepted run without a recorded acceptance (exit 4); every run leaves an execution record.

  python3 -m kb security patch plan <order-ref>
  python3 -m kb security patch run <order-ref> [--accepted-by NAME --accepted-text "..."] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from kb.security import close as CL, inventory as I
from kb.security.collect import inventory_items
from kb.security.executors import compose_tag, lockfile_bump
from kb.security.store import Store, now_iso, store_path

LOCKFILES = ("uv.lock", "pnpm-lock.yaml", "package-lock.json", "go.sum")


def _item(items: list[dict], target_ref: str) -> dict | None:
    return next((i for i in items if i["target_ref"] == target_ref), None)


def _repo_lockfile(vault: Path, project: str, environment: str) -> Path | None:
    for t in (I.load_registry(vault).get("targets") or []):
        if t.get("project") == project and t.get("environment") == environment and t.get("kind") == "lockfile":
            for s in t.get("sources") or []:
                p = I.resolve(s, vault)
                if p.name in LOCKFILES:
                    return p
    return None


def _latest_release(store: Store, repo: str) -> str | None:
    recs = store.records("source_id='github-releases' AND id LIKE ?", (f"github-releases:{repo}:%",))
    recs = [r for r in recs if r.get("severity_label") != "prerelease" and r.get("version")]
    recs.sort(key=lambda r: r.get("published") or "", reverse=True)
    return recs[0]["version"] if recs else None


def make_plan(vault: Path, order: dict, store: Store, items: list[dict] | None = None) -> dict:
    items = items if items is not None else inventory_items(vault)
    t0 = (order.get("targets") or [{}])[0]
    it = _item(items, t0.get("target_ref", "")) or {}
    kind = it.get("kind")
    project, env = (t0.get("target_ref", "//").split("/") + ["", ""])[:2]
    if kind == "library":
        lock = _repo_lockfile(vault, project, env)
        fixed = t0.get("fixed") or next((t.get("fixed") for t in order.get("targets") or [] if t.get("fixed")), None)
        if lock is None or not fixed:
            return {"executor": "none", "condition": "none", "reason": "잠금 파일 또는 고친 버전을 알 수 없음", "downtime_expected": "unknown"}
        return lockfile_bump.plan(lock, it["name"], str(it.get("version")), str(fixed), order["vuln_id"])
    if kind == "image":
        link = I.manual_links(vault).get(t0.get("target_ref", ""))
        repo = link.split(":", 1)[1] if link and ":" in link else None
        to = t0.get("fixed") or (_latest_release(store, repo) if repo else None)
        if not to:
            return {"executor": "none", "condition": "none", "reason": "고친 릴리스를 알 수 없음(수동 연결 없음 또는 릴리스 미수집)", "downtime_expected": "unknown"}
        return compose_tag.plan(it["name"], it.get("image") or it["name"], str(it.get("version")), str(to).lstrip("v") if not str(it.get("version")).startswith("v") else str(to),
                                bool(it.get("critical")))
    # OS packages, desktops, ECS tasks: not the core's to run — the order ends with a pre-deploy skeleton (deploy card)
    return {"executor": "none", "condition": "none", "downtime_expected": "unknown",
            "reason": f"종류 {kind or '?'} 는 실행기가 없다 — 서버 패키지(apt)·데스크탑·배포는 사용자의 일",
            "pre_deploy_note": {"확인하려는 것": f"{order['vuln_id']} 가 {order.get('host')} 에서 닫힘 — fixed 버전으로 올라갔는지", "확정": [f"설치 {t.get('version')} → 고침 {t.get('fixed')}" for t in order.get("targets") or []][:5],
                                "추정": ["업그레이드가 다른 서비스에 닿지 않음(검증 필요)"], "되돌림": "패키지는 apt 로 이전 버전 고정(apt-mark hold)·커널은 이전 커널로 부팅", "실행 뒤": "dpkg-query 다시 받아 inventory --write → close --reason patched"}}


def cmd_plan(vault: Path, ref: str, store: Store) -> dict:
    p, head, doc = CL.load_order(vault, ref)
    plan = make_plan(vault, doc["order"], store)
    doc["order"]["patch_plan"] = plan
    doc["order"].setdefault("history", []).append({"at": now_iso(), "event": "planned", "executor": plan.get("executor"), "condition": plan.get("condition")})
    CL.save_order(p, head, doc)
    return plan


def cmd_run(vault: Path, ref: str, store: Store, accepted_by: str | None = None, accepted_text: str | None = None, dry_run: bool = False, runner=None,
            day: date | None = None) -> tuple[int, dict]:
    p, head, doc = CL.load_order(vault, ref)
    o = doc["order"]
    plan = o.get("patch_plan") or make_plan(vault, o, store)
    o["patch_plan"] = plan
    cond = plan.get("condition")
    if accepted_by and accepted_text:
        o["acceptance_record"] = {"by": accepted_by, "at": now_iso(), "text": accepted_text, "downtime_expected": plan.get("downtime_expected")}
    if cond == "none":
        if o.get("acceptance_record"):
            cond = "user-accepted"           # the person accepted the downtime: the third condition (DEC-02)
        else:
            o.setdefault("history", []).append({"at": now_iso(), "event": "run-refused", "why": "condition none — 오더까지만"})
            CL.save_order(p, head, doc)
            return 3, {"refused": "조건 없음 — 세 조건(코드 수준·다운타임 없음 / 수 분 내 교체 / 기록된 수락) 중 어느 것도 성립하지 않아 오더까지만. 수락하려면 --accepted-by/--accepted-text"}
    if cond == "user-accepted" and not o.get("acceptance_record"):
        o.setdefault("history", []).append({"at": now_iso(), "event": "run-refused", "why": "acceptance_record 없음"})
        CL.save_order(p, head, doc)
        return 4, {"refused": "사용자 수락이 기록되지 않았다 — 오더의 acceptance_record 또는 --accepted-by/--accepted-text"}
    if dry_run:
        o.setdefault("history", []).append({"at": now_iso(), "event": "dry-run", "condition": cond})
        CL.save_order(p, head, doc)
        return 0, {"dry_run": True, "condition": cond, "plan": plan}
    ex = {"lockfile_bump": lockfile_bump, "compose_tag": compose_tag}.get(plan.get("executor"))
    if ex is None:
        return 3, {"refused": "실행기 없음"}
    result = ex.execute(plan, runner) if runner else ex.execute(plan)
    entry = {"at": now_iso(), "by": accepted_by or "kb security patch", "executor": plan["executor"], "condition": cond, "from": plan.get("from_version"),
             "to": plan.get("to_version"), **result}
    o.setdefault("execution", []).append(entry)
    o.setdefault("history", []).append({"at": now_iso(), "event": "executed", "result": result.get("result")})
    CL.save_order(p, head, doc)
    if result.get("result") == "committed-on-branch":
        CL.close_order(vault, str(p.relative_to(vault)), accepted_by or "kb security patch", "patched", store, day)
    return (0 if result.get("result") in ("committed-on-branch", "awaiting-server") else 1), entry


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security patch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["patch"])
    ap.add_argument("sub", choices=["plan", "run"])
    ap.add_argument("ref")
    ap.add_argument("--accepted-by"); ap.add_argument("--accepted-text"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    store = Store(store_path(vault))
    try:
        if a.sub == "plan":
            plan = cmd_plan(vault, a.ref, store)
            print(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False))
            return 0
        rc, info = cmd_run(vault, a.ref, store, a.accepted_by, a.accepted_text, a.dry_run)
        print(yaml.safe_dump(info, allow_unicode=True, sort_keys=False))
        return rc
    finally:
        store.close()
