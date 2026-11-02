"""_kit — where the ported strata tools find the kit (order 2026.10.29-01 task-03).

The tools call `python -m kb <command>` and read rules from core/rules and templates from core/templates.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
RULES = KIT / "core" / "rules"
VAULT_GIT = KIT / "kb" / "legacy" / "vault_git.sh"
VAULT_TAXONOMY_TEMPLATE = KIT / "core" / "templates" / "vault" / "_meta" / "taxonomy.yaml"   # fallback for body_sections


def kb_argv(*args: str) -> list[str]:
    """argv for a kit command run from any working directory (the caller's cwd is kept)."""
    return [sys.executable, "-m", "kb", *args]


def kb_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(KIT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env
