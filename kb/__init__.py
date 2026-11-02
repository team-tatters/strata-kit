"""strata-kit kb — the knowledge-base engine.

One store contract (nodes · edges · chunks · baselines · revisions, see core/docs/*/kb-engine.md),
providers that fill it from sources (vault scanner, decision records, orders, code graph), the gates
(kb.gates), the generated views (kb.views, kb.build) and the session tools ported from strata (kb.legacy).
strata-kit is the canonical home of all of it (DEC-2026-10-29-11).

Layout
  kb/store.py              Store contract + SqliteStore (FTS5 + embeddings)
  kb/providers/            vault_scanner, decision_records, orders, code_graph
  kb/gates/                coverage, links, hygiene, grades
  kb/views/, kb/build.py   node pages and the build-index views
  kb/legacy/               session tools: decision, ledger, handoff, vault-git, hooks (naming, layer, stamp, pre-compact)
  kb/__main__.py           python3 -m kb <command>
"""
from __future__ import annotations

import os
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]


def kit_root() -> Path:
    """The strata-kit checkout: $STRATA_KIT when set, else the parent of this package."""
    env = os.environ.get("STRATA_KIT")
    return Path(os.path.expanduser(env)).resolve() if env else KIT_ROOT


def vault_root() -> Path | None:
    env = os.environ.get("STRATA_VAULT")
    return Path(os.path.expanduser(env)).resolve() if env else None
