"""Code-level patch: a dependency is raised to the fixed version in the repository's lockfile on a branch sec/<vuln>, and
committed there — never pushed (the person pushes and opens the pull request). No downtime: nothing is deployed."""
from __future__ import annotations

from pathlib import Path

from kb.security.executors import run_cmd

TOOLS = {
    "uv.lock": lambda pkg, ver: [["uv", "lock", "--upgrade-package", f"{pkg}=={ver}"]],
    "pnpm-lock.yaml": lambda pkg, ver: [["pnpm", "up", f"{pkg}@{ver}"]],
    "package-lock.json": lambda pkg, ver: [["npm", "install", f"{pkg}@{ver}"]],
    "go.sum": lambda pkg, ver: [["go", "get", f"{pkg}@{ver}"], ["go", "mod", "tidy"]],
}


def plan(lockfile: Path, package: str, from_version: str, to_version: str, vuln_id: str) -> dict:
    if lockfile.name == "go.sum" and not str(to_version).startswith("v"):
        to_version = "v" + str(to_version)          # Go module versions carry the v; OSV ranges do not
    cmds = TOOLS[lockfile.name](package, to_version)
    return {"executor": "lockfile_bump", "condition": "code-level", "downtime_expected": "none", "target_path": str(lockfile),
            "package": package, "from_version": from_version, "to_version": to_version, "branch": f"sec/{vuln_id.lower()}",
            "commands": [["git", "checkout", "-b", f"sec/{vuln_id.lower()}"], *cmds, ["git", "add", "-A", "--", "."], ["git", "commit", "-m", f"security: {package} {from_version} → {to_version} ({vuln_id})"]],
            "rollback": [["git", "checkout", "-"], ["git", "branch", "-D", f"sec/{vuln_id.lower()}"]],
            "note": "커밋까지만 — 푸시와 PR 은 사용자가(2026-09-04 커밋 정책). main 최신화 뒤 브랜치 분리"}


def execute(p: dict, runner=run_cmd) -> dict:
    cwd = Path(p["target_path"]).parent
    log = []
    for cmd in p["commands"]:
        rc, out = runner(cmd, cwd)
        log.append({"cmd": " ".join(cmd), "rc": rc, "out": out[-400:]})
        if rc != 0:
            return {"result": "failed", "downtime": "none", "log": log, "rollback": p["rollback"]}
    return {"result": "committed-on-branch", "downtime": "none", "log": log, "branch": p["branch"]}
