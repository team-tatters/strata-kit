"""Security vulnerability subscription and patch core (planning/security-vuln-subscription; DEC-2026-11-03-02·03·04·05).

Files (DEC-2026-11-03-05): what runs daily lives at $STRATA_VAULT/security/ — registry.yaml (what inventory is built
from), sources.yaml (the four source layers and the manual links of targets without an identifier), notes/, matches/,
runs/; what belongs to a target lives at projects/<p>/security/ — inventory/<env>.yaml, grading.yaml,
accepted-risks.yaml. The collected records live in .kb/security.sqlite (not in git).

  python3 -m kb security inventory [--project P --env E | --all] [--write]      order 2026.11.03-01
  python3 -m kb security collect [--since D] [--layer L] [--source S] [--no-enrich]   order 2026.11.03-02
  python3 -m kb security match|grade|note [--date D] · grading show|set · daily [--commit]        order 2026.11.03-02
  python3 -m kb security order [--date D] · promote <match> --by · assign <ref> --to --by          order 2026.11.03-03
  python3 -m kb security patch plan|run <ref> · close <ref> --by · accept --project --target --vuln --reason --until --by
"""
from __future__ import annotations

import sys

COMMANDS = {"inventory": "kb.security.inventory", "collect": "kb.security.collect", "match": "kb.security.match", "grade": "kb.security.grade", "grading": "kb.security.grade", "note": "kb.security.note", "daily": "kb.security.daily", "order": "kb.security.orders", "promote": "kb.security.orders", "assign": "kb.security.orders", "patch": "kb.security.patch", "close": "kb.security.close", "accept": "kb.security.close"}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    mod = COMMANDS.get(cmd)
    if not mod:
        print(f"kb security: 모르는 명령 {cmd!r} — {', '.join(COMMANDS)}", file=sys.stderr)
        return 2
    import importlib
    return importlib.import_module(mod).main([cmd, *rest])
