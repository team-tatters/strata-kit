"""Order claims (MB-strata-kit-2026-009): before work on an order starts, the order file records which machine and
session holds it, and that one file is pushed at once — another machine pulls it at session start and stops.

  python3 -m kb order claim <order-id|dir|_order.yaml> [--session S] [--machine M] [--force] [--no-sync]
  python3 -m kb order release <ref> [--session S] [--machine M] [--force] [--no-sync]
  python3 -m kb order show <ref>

claim: free order or the same holder → claimed (status in-progress, claimed_by {machine, session, at}); another holder →
held (exit 3, nothing written) unless --force, which keeps the old holder under claimed_by.previous; a closed order →
exit 4. release removes claimed_by (status stays the order's). Machine defaults to STRATA_ENV, session to the newest
.strata/local/active/*.yaml stem in the working directory. Without --no-sync the vault is pulled first and only the
order file is committed and pushed (kb/legacy/vault_git.sh commit-push).
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

CLOSED = ("closed", "done", "cancelled", "withdrawn")
ID_RE = re.compile(r"^(\d{4}\.\d{2}\.\d{2})-(\d{2})$")


def find(vault: Path, ref: str) -> Path | None:
    p = Path(ref).expanduser()
    if p.is_dir() and (p / "_order.yaml").is_file():
        return p / "_order.yaml"
    if p.is_file():
        return p
    m = ID_RE.match(ref)
    if not m:
        return None
    hits = sorted(vault.glob(f"projects/*/tasks/{m.group(1)}/{m.group(2)}-*/_order.yaml"))
    return hits[0] if hits else None


def _flow(v: dict) -> str:
    return yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, sort_keys=False, width=10_000).strip()


def _set(text: str, key: str, value: str | None) -> str:
    """Replace, insert (after the order's status line) or remove (value None) a one-line field of the order block."""
    line = re.compile(rf"^  {key}:.*\n", re.M)
    if value is None:
        return line.sub("", text, count=1)
    new = f"  {key}: {value}\n"
    if line.search(text):
        return line.sub(lambda _m: new, text, count=1)
    status = re.compile(r"^  status:.*\n", re.M).search(text)
    at = status.end() if status else text.index("\n", text.index("order:")) + 1
    return text[:at] + new + text[at:]


def _holder(o: dict) -> dict | None:
    h = o.get("claimed_by")
    return h if isinstance(h, dict) else None


def claim(path: Path, machine: str, session: str, now: str | None = None, force: bool = False) -> dict:
    text = path.read_text(encoding="utf-8")
    o = (yaml.safe_load(text) or {}).get("order", {})
    if str(o.get("status", "")).lower() in CLOSED:
        return {"result": "closed", "status": o.get("status")}
    holder = _holder(o)
    same = holder and (holder.get("machine"), holder.get("session")) == (machine, session)
    if holder and not same and not force:
        return {"result": "held", "holder": holder}
    new = {"machine": machine, "session": session, "at": now or datetime.now().strftime("%Y-%m-%dT%H:%M")}
    if holder and not same:
        new["previous"] = {k: v for k, v in holder.items() if k != "previous"}
    text = _set(text, "status", '"in-progress"')
    text = _set(text, "claimed_by", _flow(new))
    path.write_text(text, encoding="utf-8")
    return {"result": "claimed", "claimed_by": new}


def release(path: Path, machine: str, session: str, force: bool = False) -> dict:
    text = path.read_text(encoding="utf-8")
    holder = _holder((yaml.safe_load(text) or {}).get("order", {}))
    if not holder:
        return {"result": "free"}
    if (holder.get("machine"), holder.get("session")) != (machine, session) and not force:
        return {"result": "held", "holder": holder}
    path.write_text(_set(text, "claimed_by", None), encoding="utf-8")
    return {"result": "released"}


def _default_session() -> str:
    active = sorted(Path(".strata/local/active").glob("*.yaml"), key=lambda p: p.stat().st_mtime)
    return active[-1].stem if active else "unknown"


def _vault() -> Path:
    from kb import vault_root
    v = vault_root()   # no silent default (MB-strata-kit-2026-048)
    if v is None:
        raise SystemExit("STRATA_VAULT is not set — orders live in the vault; set it to the vault path")
    return v


def _vault_git(*args: str) -> None:
    script = Path(__file__).resolve().parent / "legacy" / "vault_git.sh"
    subprocess.run(["sh", str(script), *args])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb order", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["claim", "release", "show"])
    ap.add_argument("ref")
    ap.add_argument("--session", default=None)
    ap.add_argument("--machine", default=os.environ.get("STRATA_ENV", "unknown"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-sync", action="store_true")
    a = ap.parse_args(argv)
    vault = _vault()
    sync = not a.no_sync and a.action != "show"
    if sync:
        _vault_git("pull")
    path = find(vault, a.ref)
    if not path:
        print(f"order not found: {a.ref}", file=sys.stderr)
        return 2
    if a.action == "show":
        print(_flow(_holder((yaml.safe_load(path.read_text(encoding='utf-8')) or {}).get("order", {})) or {}))
        return 0
    session = a.session or _default_session()
    r = (claim if a.action == "claim" else release)(path, a.machine, session, force=a.force)
    print(f"{r['result']}: {path}" + (f" — held by {_flow(r['holder'])}" if r.get("holder") else ""))
    if r["result"] in ("claimed", "released") and sync:
        rel = path.relative_to(vault) if path.is_relative_to(vault) else path
        _vault_git("commit-push", f"order {a.ref} {a.action}: {a.machine}/{session}", str(rel))
    return {"claimed": 0, "released": 0, "free": 0, "held": 3, "closed": 4}[r["result"]]


if __name__ == "__main__":
    raise SystemExit(main())
