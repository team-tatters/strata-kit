"""The daily run (spec AC8, Tech Spec G8; DEC-2026-11-03-03·04): inventory → collect → match → grade → note, one step after
another, each failure recorded in the run and the next step still taken. The run record is security/runs/<day>.yaml; a
day without a run gets the one-line "오늘은 보지 못했다" note when the next run notices the gap. With --commit the
generated files (notes, matches, runs, generated inventories) are committed and pushed the way views-publish does.

  python3 -m kb security daily [--date D] [--since D] [--commit] [--no-inventory-write]
Runs today in the librarian's daily job (launchd strata-librarian, before views-publish); the Quilt vault
piece takes it over when Quilt has scheduled jobs (adapters/quilt/REQUEST-2026-11-03.md).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

import yaml

from kb.security import collect as C, grade as G, inventory as I, match as M, note as N
from kb.security.store import Store, now_iso, store_path

KIT = Path(__file__).resolve().parents[2]
COMMIT_PATHS = ("security/notes", "security/matches", "security/runs")


def runs_dir(vault: Path) -> Path:
    return vault / "security" / "runs"


def run_path(vault: Path, day: str) -> Path:
    return runs_dir(vault) / f"{day}.yaml"


def missed_days(vault: Path, today: date, lookback: int = 14) -> list[str]:
    """Days before today, after the last run on file, that have neither a run record nor a note. Before the very first
    run there is nothing to have missed — no gap notes then."""
    if not any(runs_dir(vault).glob("*.yaml")):
        return []
    out = []
    for i in range(1, lookback + 1):
        d = (today - timedelta(days=i)).isoformat()
        if run_path(vault, d).is_file():
            break
        if not N.note_path(vault, d).is_file():
            out.append(d)
    return sorted(out)


def run(vault: Path, today: date, since: date | None = None, http=None, store: Store | None = None, write_inventory: bool = True,
        commit: bool = False, log=print) -> dict:
    own = store is None
    store = store or Store(store_path(vault))
    day = today.isoformat()
    rec = {"day": day, "started": now_iso(), "finished": None, "steps": {}, "layers": {}, "sources": {}, "counts": {}, "note_path": None, "missed_days": []}

    def step(name, fn):
        try:
            out = fn()
            rec["steps"][name] = {"status": "ok"}
            return out
        except Exception as e:   # noqa: BLE001 — AC8: one failed step, the rest still runs
            rec["steps"][name] = {"status": "failed", "error": f"{type(e).__name__}: {str(e)[:300]}"}
            log(f"  ! {name}: {rec['steps'][name]['error']}")
            return None

    # 0. gaps since the last run
    rec["missed_days"] = missed_days(vault, today)
    for d in rec["missed_days"]:
        N.write_gap(vault, d, "실행 기록 없음 — 정기 작업이 돌지 않았다")
    # 1. inventory (generated targets only; manual ones are checked)
    def _inventory():
        reg = I.load_registry(vault)
        links = I.manual_links(vault)
        lines, differs = [], 0
        for t in reg.get("targets") or []:
            try:
                ls, d = I.run_target(t, vault, links, write_inventory and t.get("kind") != "manual", today)
            except (FileNotFoundError, ValueError) as e:
                ls, d = [f"! {e}"], True
            lines += ls
            differs += int(bool(d))
        rec["counts"]["inventory_diffs"] = differs
        return lines
    step("inventory", _inventory)
    # 2. collect
    if since is None:
        last = store.last_success()
        since = date.fromisoformat(last[:10]) if last else today - timedelta(days=1)
    def _collect():
        res = C.collect(vault, since, today, http=http, store=store, log=log)
        rec["layers"], rec["sources"] = res["layers"], res["sources"]
        rec["counts"]["records"] = res["records"]
        return res
    step("collect", _collect)
    # 3. match
    def _match():
        res = M.run(vault, today, store)
        rec["counts"].update(res["counts"])
        rec["_blind"] = res["blind_targets"]
        M.write_matches(vault, res, store)
        return res
    mres = step("match", _match)
    # 4. grade
    def _grade():
        res = G.run(vault, today, store)
        rec["counts"].update(res["counts"])
        M.write_matches(vault, {"day": day, "matches": res["matches"], "blind_targets": rec.get("_blind", []), "counts": rec["counts"]}, store, graded=res["matches"])
        return res
    step("grade", _grade)
    # 5. run record (before the note, so the note can name the failed layers), then the note
    rec["finished"] = now_iso()
    store.save_run(day, rec["started"], rec["finished"], rec["layers"], rec["counts"], None)
    def _note():
        p = N.write(vault, day, store, rec.get("_blind"))
        rec["note_path"] = str(p.relative_to(vault))
        return p
    step("note", _note)
    store.save_run(day, rec["started"], rec["finished"], rec["layers"], rec["counts"], rec["note_path"])
    rec.pop("_blind", None)
    runs_dir(vault).mkdir(parents=True, exist_ok=True)
    run_path(vault, day).write_text("# 실행 기록 — 생성본(python3 -m kb security daily). AC8: 돌지 못한 날은 missed_days 와 notes/<날>.md 의 한 줄로 남는다\n"
                                    + yaml.safe_dump(rec, allow_unicode=True, sort_keys=False, width=160), encoding="utf-8")
    if commit:
        step("commit", lambda: commit_push(vault, day))
    if own:
        store.close()
    return rec


def commit_push(vault: Path, day: str) -> str:
    paths = list(COMMIT_PATHS) + [str(p.relative_to(vault)) for p in vault.glob("projects/*/security/inventory/*.yaml")
                                 if (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("origin") == "generated"]
    cmd = [sys.executable, str(KIT / "kb"), "vault-git", "commit-push", f"security daily {day}", *paths]
    out = subprocess.run(cmd, cwd=str(KIT), capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout)[-300:])
    return out.stdout[-200:]


def render(rec: dict) -> list[str]:
    steps = " · ".join(f"{k} {'ok' if v['status'] == 'ok' else '✗'}" for k, v in rec["steps"].items())
    c = rec["counts"]
    lines = [f"daily {rec['day']}: {steps}",
             f"  층: " + ", ".join(f"{k} {v}" for k, v in (rec["layers"] or {}).items()),
             f"  레코드 {c.get('records', 0)} · 후보 {c.get('candidates', 0)} · 긴급 {c.get('urgent', 0)} · 권고 {c.get('advisory', 0)} · 걸러냄 {c.get('filtered', 0)} · 눈 없는 대상 {c.get('blind_targets', 0)}"]
    if rec["missed_days"]:
        lines.append(f"  보지 못한 날: {', '.join(rec['missed_days'])} (한 줄 노트 생성)")
    if rec.get("note_path"):
        lines.append(f"  노트 → {rec['note_path']}")
    return lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security daily", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["daily"])
    ap.add_argument("--date", type=date.fromisoformat, default=None)
    ap.add_argument("--since", type=date.fromisoformat, default=None)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--no-inventory-write", action="store_true")
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    rec = run(vault, a.date or date.today(), a.since, write_inventory=not a.no_inventory_write, commit=a.commit, log=lambda m: print(m, flush=True))
    print("\n".join(render(rec)))
    return 0 if all(v["status"] == "ok" for v in rec["steps"].values()) else 1
