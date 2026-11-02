"""python3 -m kb <command> [args…]

  build-index        rebuild the store, then node pages · sortspecs · review inbox · manifest (block → exit 2)
  gen-node-pages     node pages from toc.yaml + the store (same flags; --db is the store)
  gen-decision-notes DEC notes from Tier P records (same flags)
  build-store        rebuild $STRATA_VAULT/.kb/store.sqlite from the providers
  store-stats        counts and the last revision of the store
  coverage           coverage resolver (resolve · nodes · unowned · docs-to-update · node), reads the store
  coverage-gate      session-end coverage gate (warnings only), reads the store; --covers-candidates writes the impact Inbox
  enforce            per-project enforcement grade around an existing checker: run --family F -- CMD · show (DEC-2026-10-29-17)
  link-check         link-currency gate (baseline in .kb/link-baseline.json), reads the store
  skills             the user skill layer (~/.strata/skills: kit packs + local): check · install <pack> · link --harness · next <skill> (DEC-2026-10-31-36·37)
  planning           planning bundles (source/ · audit/ · refined): check · boundary [--list] · impact (DEC-2026-11-01-04·05·16)
  design             contract-side check of screen tasks: design_ref · design_sync · waived until (DEC-2026-11-01-09)
  taste              design pack notes: check (taste notes, promotion candidates) · expression (computed relations) (DEC-2026-11-01-11)
  vault-init         a starter vault from core/templates/vault: <dir> [--project NAME] [--detached] (MB-strata-kit-2026-048)
  export             the injection layer as a folder: knowledge · refined planning · decision notes · code-graph summary (DEC-2026-11-01-06)
  ideas              idea notes of the ideation pack ($STRATA_VAULT/ideas/): list · check · tidy · event · draw (DEC-2026-10-31-38)
  signals            operations signal notes (projects/<p>/signals/): list · check · candidates [--write] · route (DEC-2026-11-01-14·17)
  indicators         product-flow indicators from a project's read-only commands: collect [--write] · show (DEC-2026-11-01-17)
  divergence         plan-versus-code divergence requests: list · add · judge · count (a person judges; DEC-2026-10-31-35)
  hygiene            vault hygiene report (history status vocabulary · toc gaps · covers gaps · broken references), read-only
  code               graph questions on the code provider: deps · impact · tests-for · symbol (DEC-2026-10-28-05)
  search             kb-search CLI (FTS · --semantic · --hybrid · --toc · --tags · --doc · --stats), reads the store
  embed              compute missing chunk embeddings (bge-m3, local) into the store
  search-eval        recall@k of fts · dense · hybrid against a query set (vault/_meta/search-eval.yaml)

  session tools (ported from strata/scripts, orders 2026.10.29-01 and -11):
  decision           decision record CLI: add · supersede · withdraw · regen-index · list · migrate · check-uncommitted
  ledger             shared session ledger: append · read · close · validate
  handoff            session handoff skeleton in the vault + gates + vault sync   (handoff <slug> [topic])
  vault-git          vault sync channel: pull · commit-push MSG [PATH...] (listed paths only)
  order              order claim before work starts: claim · release · show <order-id>  (MB-strata-kit-2026-009)
  views-publish      librarian, once a day: build-index, then commit-push only node pages and _index/review-needed.md (DEC-2026-10-29-04)
  retro-bundle       retrospective bundle for a period and project → $STRATA_VAULT/outputs/retro/ (DEC-2026-10-30-05)
  sections           body section titles from the taxonomy (sections session)
  pre-compact        PreCompact hook: snapshot the active task into .strata/local/
  validate-naming    PreToolUse hook: naming rules from core/rules (stdin hook JSON or <file> [type])
  check-layer        PostToolUse hook: layer rules from core/rules + .strata/layer-map.yaml
  stamp              PostToolUse hook: stamp `updated` on vault knowledge docs and check frontmatter against the taxonomy
  atom-notify        hook: show the agent state on an M5Stack Atom Matrix LED over serial (always exit 0)

Run from any directory with `python3 "$STRATA_KIT/kb" <command>` (hooks keep the project cwd).
"""
from __future__ import annotations

import sys
from pathlib import Path

if not __package__:   # run as a directory (`python3 "$STRATA_KIT/kb" …`): make the kit importable, keep the caller's cwd
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _run_legacy(module_name: str, argv: list[str]) -> int:
    import importlib
    mod = importlib.import_module(f"kb.legacy.{module_name}")
    sys.argv = [module_name, *argv]
    rc = mod.main()
    return int(rc or 0)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "build-index":
        from kb.build import main as build_main
        return build_main(rest)
    if cmd == "gen-node-pages":
        from kb.views.node_pages import main as pages_main
        return pages_main(rest)
    if cmd == "gen-decision-notes":
        return _run_legacy("gen_decision_notes", rest)
    legacy = {"decision": "decision", "ledger": "session_ledger", "pre-compact": "pre_compact_snapshot",
              "validate-naming": "validate_naming", "check-layer": "check_layer_violation", "atom-notify": "atom_notify"}
    if cmd in legacy:
        return _run_legacy(legacy[cmd], rest)
    if cmd in ("handoff", "vault-git"):
        import subprocess
        script = Path(__file__).resolve().parent / "legacy" / ("session_handoff.sh" if cmd == "handoff" else "vault_git.sh")
        return subprocess.run(["bash" if cmd == "handoff" else "sh", str(script), *rest]).returncode
    if cmd == "views-publish":   # DEC-2026-10-29-04: the one writer of generated views; sessions never commit them
        import subprocess
        from datetime import date
        from kb.build import main as build_main
        rc = build_main(rest)
        if rc:
            return rc
        from kb import vault_root
        script = Path(__file__).resolve().parent / "legacy" / "vault_git.sh"
        v = vault_root()
        paths = [":(glob)projects/*/nodes/**"] + [p for p in ("_index/review-needed.md",) if v and (v / p).is_file()]   # a missing path fails the whole add
        return subprocess.run(["sh", str(script), "commit-push", f"views {date.today()}: 노드 페이지·리뷰 목록 (librarian, DEC-2026-10-29-04)",
                               *paths]).returncode
    if cmd == "enforce":
        from kb.gates.enforce import main as enforce_main
        return enforce_main(rest)
    if cmd == "retro-bundle":
        from kb.retro import main as retro_main
        return retro_main(rest)
    if cmd == "order":
        from kb.orders import main as order_main
        return order_main(rest)
    if cmd == "stamp":
        from kb.legacy.frontmatter_stamp import main as stamp_main
        return int(stamp_main(["stamp", *rest]) or 0)
    if cmd == "sections":
        from kb.legacy.kb_sections import main as sections_main
        return int(sections_main(["kb_sections", *rest]) or 0)
    if cmd == "coverage":
        from kb.gates.coverage import main_resolver
        return main_resolver(rest)
    if cmd == "coverage-gate":
        from kb.gates.coverage import main_gate
        return main_gate(rest)
    if cmd == "embed":
        from kb.embed import main as embed_main
        return embed_main(rest)
    if cmd == "search-eval":
        from kb.evals.search_eval import main as eval_main
        return eval_main(rest)
    if cmd == "search":
        from kb.search import main as search_main
        return search_main(rest)
    if cmd == "code":
        from kb.code import main as code_main
        return code_main(rest)
    if cmd == "skills":
        from kb.skills_layer import main as skills_main
        return skills_main(rest)
    if cmd == "design":
        from kb.design import main as design_main
        return design_main(rest)
    if cmd == "vault-init":
        from kb.vault_init import main as vault_init_main
        return vault_init_main(rest)
    if cmd == "export":
        from kb.export import main as export_main
        return export_main(rest)
    if cmd == "planning":
        from kb.planning import main as planning_main
        return planning_main(rest)
    if cmd == "taste":
        from kb.taste import main as taste_main
        return taste_main(rest)
    if cmd == "ideas":
        from kb.ideas import main as ideas_main
        return ideas_main(rest)
    if cmd == "indicators":
        from kb.indicators import main as indicators_main
        return indicators_main(rest)
    if cmd == "signals":
        from kb.signals import main as signals_main
        return signals_main(rest)
    if cmd == "divergence":
        from kb.gates.divergence import main as divergence_main
        return divergence_main(rest)
    if cmd == "hygiene":
        from kb.gates.hygiene import main as hygiene_main
        return hygiene_main(rest)
    if cmd == "link-check":
        from kb.gates.links import main as links_main
        return links_main(rest)
    if cmd in ("build-store", "store-stats"):
        from kb.engine import main as engine_main
        return engine_main([cmd, *rest])
    print(f"unknown command: {cmd}\n\n{__doc__.strip()}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
