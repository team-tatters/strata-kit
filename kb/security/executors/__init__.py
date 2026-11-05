"""Patch executors. Each returns an execution record; they run only through kb.security.patch after the condition is judged.
The runner is injectable so tests never call pnpm, uv, go or git for real."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    out = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return out.returncode, (out.stdout + out.stderr)[-2000:]
