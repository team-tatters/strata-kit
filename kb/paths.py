"""Tier P resolver (placement profile) — canonical home is kb/legacy/strata_paths.py until the
decision writer moves; this module is the import path the rest of the engine uses."""
from __future__ import annotations

from kb.legacy.strata_paths import TierP, main_worktree, resolve_project_name, resolve_tier_p  # noqa: F401

__all__ = ["TierP", "resolve_tier_p", "resolve_project_name", "main_worktree"]
