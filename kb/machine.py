"""Machine aliases (MB-strata-kit-2026-049): which machine wrote a record, and which pending work belongs to which machine.

The alias is STRATA_ENV, else ~/.strata/config.yaml machine.alias. The vault's env-config.yaml registers each alias
with a fingerprint — a short hash of the OS machine id (macOS IOPlatformUUID, Linux /etc/machine-id, Windows
MachineGuid), never the id itself — so a renamed alias, or one alias used on two machines, shows at session start.
Nothing here blocks a session; the session-document check is what a closing step refuses on.

  python3 -m kb machine show                 alias, fingerprint and the registry verdict
  python3 -m kb machine register [--alias A] [--description D] [--replace-fingerprint]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

SALT = "strata-kit:"
HEADER = ("# Strata Vault — environment registry (MB-strata-kit-2026-049).\n"
          "# One entry per machine alias. fingerprint is a short hash of the OS machine id, never the id itself;\n"
          "# former_aliases / former_fingerprints keep earlier names and ids. Paths live in each machine's\n"
          "# ~/.strata/config.yaml. Write with `python3 -m kb machine register`.\n\n")


def fingerprint(raw: str) -> str:
    return hashlib.sha256((SALT + raw.strip()).encode()).hexdigest()[:12]


def raw_machine_id(env: dict | None = None) -> str | None:
    """The OS machine id (STRATA_MACHINE_ID overrides, for tests and unusual hosts); None when it cannot be read."""
    env = os.environ if env is None else env
    if env.get("STRATA_MACHINE_ID"):
        return env["STRATA_MACHINE_ID"]
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=5).stdout
            m = re.search(r'"IOPlatformUUID" = "([^"]+)"', out)
            return m.group(1) if m else None
        if system == "Linux":
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if Path(p).is_file() and Path(p).read_text().strip():
                    return Path(p).read_text().strip()
            return None
        if system == "Windows":
            out = subprocess.run(["reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography", "/v", "MachineGuid"],
                                 capture_output=True, text=True, timeout=5).stdout
            m = re.search(r"MachineGuid\s+REG_SZ\s+(\S+)", out)
            return m.group(1) if m else None
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def current_fingerprint(env: dict | None = None) -> str | None:
    raw = raw_machine_id(env)
    return fingerprint(raw) if raw else None


def current_alias(env: dict | None = None, config: Path | None = None) -> tuple[str | None, str | None]:
    """(alias, note). STRATA_ENV wins; note names a ~/.strata/config.yaml alias that disagrees with it."""
    env = os.environ if env is None else env
    config = config or Path("~/.strata/config.yaml").expanduser()
    cfg_alias = None
    try:
        if config.is_file():
            cfg_alias = ((yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("machine") or {}).get("alias")
    except (yaml.YAMLError, OSError, AttributeError):
        cfg_alias = None
    env_alias = (env.get("STRATA_ENV") or "").strip() or None
    if env_alias:
        note = f"~/.strata/config.yaml says '{cfg_alias}'" if cfg_alias and cfg_alias != env_alias else None
        return env_alias, note
    return (str(cfg_alias) if cfg_alias else None), None


def registry_path(vault: Path) -> Path:
    return vault / "env-config.yaml"


def load_registry(vault: Path | None) -> dict:
    p = registry_path(vault) if vault else None
    if not p or not p.is_file():
        return {}
    try:
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("environments") or {}
    except yaml.YAMLError:
        return {}


@dataclass
class Verdict:
    status: str
    message: str


def check(reg: dict, alias: str | None, fp: str | None) -> Verdict:
    if not alias:
        return Verdict("no-alias", "no machine alias — set STRATA_ENV (or machine.alias in ~/.strata/config.yaml)")
    holder = next((a for a, e in reg.items() if fp and fp == (e or {}).get("fingerprint")), None)
    if alias not in reg:
        current = next((a for a, e in reg.items() if alias in ((e or {}).get("former_aliases") or [])), None)
        if current:
            return Verdict("former-alias", f"'{alias}' is a former alias of '{current}' — set STRATA_ENV={current}")
        if holder:
            return Verdict("renamed", f"this machine is registered as '{holder}' — a rename? register the new alias")
        return Verdict("unregistered", f"'{alias}' is not in env-config.yaml")
    e = reg[alias] or {}
    if not e.get("fingerprint"):
        return Verdict("fingerprint-pending", f"'{alias}' has no fingerprint yet")
    if fp is None:
        return Verdict("ok", "fingerprint unreadable here, alias registered")
    if fp == e["fingerprint"]:
        return Verdict("ok", "registered")
    if fp in (e.get("former_fingerprints") or []):
        return Verdict("ok", "registered (former fingerprint)")
    if holder:
        return Verdict("alias-on-other-machine", f"this machine is registered as '{holder}', not '{alias}'")
    return Verdict("alias-on-other-machine", f"'{alias}' is registered with another fingerprint — another machine, or this one's id changed")


def header_line(reg: dict, alias: str | None, fp: str | None, note: str | None = None) -> str:
    v = check(reg, alias, fp)
    tail = f" · {note}" if note else ""
    if v.status == "ok":
        return f"machine: {alias} ({v.message}){tail} — records and pending items carry this alias"
    fix = {"unregistered": "python3 -m kb machine register --description '…'",
           "fingerprint-pending": "python3 -m kb machine register",
           "renamed": f"python3 -m kb machine register --alias {alias}",
           "alias-on-other-machine": "pick another alias, or python3 -m kb machine register --replace-fingerprint if this machine's id changed",
           "former-alias": "update STRATA_ENV",
           "no-alias": "set STRATA_ENV"}[v.status]
    return f"machine: {alias or '(none)'} — WARN {v.message}{tail} → {fix} (never blocks)"


def register(vault: Path, alias: str, fp: str | None, description: str | None = None, os_name: str | None = None,
             today: str | None = None, replace_fingerprint: bool = False) -> dict:
    """Add or update one entry. A fingerprint held under another alias renames that entry (old alias → former);
    an alias held by another fingerprint is refused unless replace_fingerprint (old one kept as former)."""
    p = registry_path(vault)
    reg = load_registry(vault)
    today = today or _dt.date.today().isoformat()
    holder = next((a for a, e in reg.items() if fp and fp == (e or {}).get("fingerprint") and a != alias), None)
    if holder:
        e = reg.pop(holder) or {}
        e["former_aliases"] = sorted(set((e.get("former_aliases") or []) + [holder]))
        merged = {**e, **(reg.get(alias) or {})}
        reg[alias] = merged
    e = reg.setdefault(alias, {}) or {}
    reg[alias] = e
    if fp and e.get("fingerprint") and e["fingerprint"] != fp:
        if not replace_fingerprint:
            raise ValueError(f"'{alias}' is registered with another fingerprint — another machine holds this alias")
        e["former_fingerprints"] = sorted(set((e.get("former_fingerprints") or []) + [e["fingerprint"]]))
    if fp:
        e["fingerprint"] = fp
    if description:
        e["description"] = description
    e["os"] = os_name or e.get("os") or platform.system().lower()
    e["last_active"] = today
    for a in list(reg):   # an alias that is now someone's former alias is not also an entry
        if a != alias and a in (e.get("former_aliases") or []):
            reg.pop(a)
    p.write_text(HEADER + yaml.safe_dump({"environments": reg}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return e


UNRECORDED = "(unrecorded)"  # head_value of a committed session doc that has no machine field (written before the field existed)


def session_machine_problem(fm: dict, current: str | None, head_value: str | None) -> str | None:
    """A session document's machine must be this machine's alias, unless the value is the one already committed
    (editing a handoff another machine wrote). A handoff committed without the field may stay without it:
    the gate never asks for a value nobody recorded. None when there is nothing to judge."""
    if not isinstance(fm, dict) or fm.get("type") != "session" or not current:
        return None
    value = fm.get("machine")
    value = str(value) if value is not None else None
    if value == current or (head_value is not None and value == head_value):
        return None
    if value is None and head_value == UNRECORDED:
        return None
    return (f"machine '{value}' ≠ this machine '{current}' — a session record names the machine it was written on "
            f"(STRATA_ENV); keep another machine's value only when editing its handoff")


_PENDING = re.compile(r"```ya?ml\s*\n(in_progress:.*?)```", re.S)


def pending_by_machine(text: str, current: str | None) -> tuple[int, dict[str, list[str]]]:
    """(items for this machine or for any, {other alias: [descriptions]}) from a handoff's in_progress block."""
    m = _PENDING.search(text)
    if not m:
        return 0, {}
    try:
        items = (yaml.safe_load(m.group(1)) or {}).get("in_progress") or []
    except yaml.YAMLError:
        return 0, {}
    here, others = 0, {}
    for it in items:
        if not isinstance(it, dict):
            continue
        mach = it.get("machine")
        if mach and mach != current:
            others.setdefault(str(mach), []).append(str(it.get("description", ""))[:60])
        else:
            here += 1
    return here, others


def head_value(path: Path) -> str | None:
    """The machine value of this file as committed: None for a new file or outside git, UNRECORDED when the
    committed file has no machine field."""
    try:
        rel = subprocess.run(["git", "-C", str(path.parent), "ls-files", "--full-name", path.name],
                             capture_output=True, text=True).stdout.strip()
        if not rel:
            return None
        out = subprocess.run(["git", "-C", str(path.parent), "show", f"HEAD:{rel}"], capture_output=True, text=True)
        if out.returncode:
            return None
        t = out.stdout
        fm = t.split("---", 2)[1] if t.startswith("---") else ""
        v = (yaml.safe_load(fm) or {}).get("machine")
        return str(v) if v is not None else UNRECORDED
    except (OSError, yaml.YAMLError, IndexError):
        return None


def main(argv: list[str]) -> int:
    from kb import vault_root
    ap = argparse.ArgumentParser(prog="python3 -m kb machine", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    r = sub.add_parser("register")
    r.add_argument("--alias")
    r.add_argument("--description")
    r.add_argument("--replace-fingerprint", action="store_true")
    c = sub.add_parser("check-session", help="exit 1 when a session document's machine is not this machine's")
    c.add_argument("file")
    a = ap.parse_args(argv)
    vault = vault_root()
    alias, note = current_alias()
    fp = current_fingerprint()
    if a.cmd == "show":
        print(header_line(load_registry(vault), alias, fp, note))
        print(f"  fingerprint here: {fp or '(unreadable)'} · registry: {registry_path(vault) if vault else '(STRATA_VAULT unset)'}")
        return 0
    if a.cmd == "register":
        if not vault:
            print("STRATA_VAULT unset", file=sys.stderr)
            return 2
        target = a.alias or alias
        if not target:
            print("no alias — pass --alias or set STRATA_ENV", file=sys.stderr)
            return 2
        try:
            e = register(vault, target, fp, a.description, replace_fingerprint=a.replace_fingerprint)
        except ValueError as ex:
            print(f"refused: {ex}", file=sys.stderr)
            return 1
        print(f"registered {target}: {e} → {registry_path(vault)} (commit it with the session's vault paths)")
        if a.alias and alias and a.alias != alias:
            print(f"  set STRATA_ENV={a.alias} (now '{alias}')")
        return 0
    path = Path(a.file).resolve()
    t = path.read_text(encoding="utf-8")
    fm = yaml.safe_load(t.split("---", 2)[1]) if t.startswith("---") else {}
    problem = session_machine_problem(fm or {}, alias, head_value(path))
    if problem:
        print(f"{path.name}: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
