#!/usr/bin/env python3
"""Test-time evidence for strata.verify (rec.verify.evidence-not-impression).

Evidence is written when a test, checker or build runs, and compared when completion is claimed:

  record  runs the command in the project, prints its output, and appends an entry to
          .strata/local/verify/<session>.yaml: command, exit code, time, the tail of the output, the HEAD
          commit (for reference) and a fingerprint of the task's files (content hash of each file or
          directory given). A commit after the test does not make the evidence stale; a content change does.
  check   recomputes the fingerprint for the latest entry of each command and says whether the evidence
          is still fresh (no task file changed since) and passing. An entry whose files changed while its
          command ran is marked unstable and never counts as fresh.

The fingerprint covers only the task's files, not the whole checkout: several sessions may edit the
same checkout at once, and their edits must not make this task's evidence stale.

Usage:
  python3 tools/verify_evidence.py record [--project DIR] [--session NAME] --files PATH [PATH ...] -- CMD [ARG ...]
  python3 tools/verify_evidence.py check  [--project DIR] [--session NAME]

Exit codes: record returns the command's exit code. check returns 0 when every latest entry is fresh and
passed, 1 when any is stale, 2 when any failed or there is no evidence.
"""
from __future__ import annotations
import argparse, hashlib, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".gradle", "build", "dist"}
TAIL_LINES = 20

def session_name(project: Path, given: str | None) -> str:
    """The given name, else the newest per-session active file (DEC-2026-08-19-05), else 'default'."""
    if given:
        return given
    d = project / ".strata" / "local" / "active"
    files = sorted(d.glob("*.yaml"), key=lambda f: f.stat().st_mtime, reverse=True) if d.is_dir() else []
    return files[0].stem if files else "default"

def evidence_path(project: Path, session: str) -> Path:
    return project / ".strata" / "local" / "verify" / f"{session}.yaml"

def _head(project: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        return r.stdout.strip() or "none"
    except OSError:
        return "none"

def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def file_hashes(project: Path, paths: list[str]) -> dict[str, str]:
    """Content hash per given path; a directory hashes every file under it (sorted, build dirs skipped)."""
    out: dict[str, str] = {}
    for rel in paths:
        p = (project / rel)
        if p.is_file():
            out[rel] = _hash_file(p)
        elif p.is_dir():
            h = hashlib.sha256()
            for f in sorted(x for x in p.rglob("*") if x.is_file() and not (set(x.relative_to(p).parts) & SKIP_DIRS)):
                h.update(str(f.relative_to(p)).encode()); h.update(b"\0"); h.update(_hash_file(f).encode())
            out[rel] = "dir:" + h.hexdigest()
        else:
            out[rel] = "absent"
    return out

def fingerprint(hashes: dict[str, str]) -> str:
    h = hashlib.sha256()
    for k in sorted(hashes):
        h.update(f"\n{k}={hashes[k]}".encode())
    return h.hexdigest()

def _load(path: Path) -> dict:
    if not path.is_file():
        return {"entries": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("entries", [])
    return data

def record(project: Path, session: str, files: list[str], cmd: list[str]) -> int:
    before = file_hashes(project, files)   # a file that changes while the command runs was not what it checked
    proc = subprocess.run(cmd, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    sys.stdout.write(proc.stdout)
    head = _head(project)
    hashes = file_hashes(project, files)
    unstable = sorted(k for k in hashes if before.get(k) != hashes[k])
    path = evidence_path(project, session)
    data = _load(path)
    data["session"] = session
    data["entries"].append({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "head": head,
        "files": hashes,
        "fingerprint": fingerprint(hashes),
        **({"unstable": unstable} if unstable else {}),
        "output_tail": "\n".join(proc.stdout.rstrip("\n").splitlines()[-TAIL_LINES:]),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000), encoding="utf-8")
    print(f"evidence: {path} (exit {proc.returncode})", file=sys.stderr)
    if unstable:
        print(f"evidence: unstable — changed while the command ran: {', '.join(unstable)}; run it again", file=sys.stderr)
    return proc.returncode

def check(project: Path, session: str) -> tuple[int, list[dict]]:
    """Latest entry per command, each marked fresh/stale and passed/failed."""
    entries = _load(evidence_path(project, session))["entries"]
    latest: dict[str, dict] = {}
    for e in entries:
        latest[e["command"]] = e
    rows = []
    for e in latest.values():
        hashes = file_hashes(project, list(e.get("files", {})))
        changed = [k for k, v in hashes.items() if e["files"].get(k) != v]
        unstable = e.get("unstable", [])
        rows.append({"command": e["command"], "exit_code": e["exit_code"], "at": e["at"],
                     "fresh": fingerprint(hashes) == e["fingerprint"] and not unstable, "changed": changed or unstable,
                     **({"unstable": unstable} if unstable else {})})
    if not rows or any(r["exit_code"] != 0 for r in rows):
        return 2, rows
    return (0 if all(r["fresh"] for r in rows) else 1), rows

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd: list[str] = []
    if "--" in argv:
        i = argv.index("--"); argv, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["record", "check"])
    ap.add_argument("--project", default=".")
    ap.add_argument("--session")
    ap.add_argument("--files", nargs="+", default=[])
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    session = session_name(project, a.session)
    if a.action == "record":
        if not cmd or not a.files:
            ap.error("record needs --files PATH [PATH ...] and -- CMD")
        return record(project, session, a.files, cmd)
    rc, rows = check(project, session)
    if not rows:
        print(f"no evidence for session {session} ({evidence_path(project, session)})")
    for r in rows:
        state = ("fresh" if r["fresh"] else "stale: " + ", ".join(r["changed"]))
        print(f"{'passed' if r['exit_code'] == 0 else 'failed (exit %d)' % r['exit_code']} · {state} · {r['at']} · {r['command']}")
    return rc

if __name__ == "__main__":
    sys.exit(main())
