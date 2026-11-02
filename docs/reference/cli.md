---
title: Commands
status: ready
generated: true
---

# Commands

> This page is generated from the sources — do not edit it by hand.

The kit's command-line tools. Each command's --help lists its options.

## python3 -m kb

```text
python3 -m kb <command> [args…]

  build-index        rebuild the store, then node pages · sortspecs · review inbox · manifest (block → exit 2)
  gen-node-pages     node pages from toc.yaml + the store (same flags; --db is the store)
  gen-decision-notes DEC notes from Tier P records (same flags)
  build-store        rebuild $STRATA_VAULT/.kb/store.sqlite from the providers
  store-stats        counts and the last revision of the store
  coverage           coverage resolver (resolve · nodes · unowned · docs-to-update · node), reads the store
  coverage-gate      session-end coverage gate (warnings only), reads the store; --covers-candidates writes the impact Inbox
  enforce            per-project enforcement grade around an existing checker: run --family F -- CMD · show
  link-check         link-currency gate (baseline in .kb/link-baseline.json), reads the store
  skills             the user skill layer (~/.strata/skills: kit packs + local): check · install <pack> · link --harness · next <skill>
  planning           planning bundles (source/ · audit/ · refined): check · boundary [--list] · impact
  design             contract-side check of screen tasks: design_ref · design_sync · waived until
  taste              design pack notes: check (taste notes, promotion candidates) · expression (computed relations)
  vault-init         a starter vault from core/templates/vault: <dir> [--project NAME] [--detached]
  export             the injection layer as a folder: knowledge · refined planning · decision notes · code-graph summary
  ideas              idea notes of the ideation pack ($STRATA_VAULT/ideas/): list · check · tidy · event · draw
  signals            operations signal notes (projects/<p>/signals/): list · check · candidates [--write] · route
  indicators         product-flow indicators from a project's read-only commands: collect [--write] · show
  divergence         plan-versus-code divergence requests: list · add · judge · count
  hygiene            vault hygiene report (history status vocabulary · toc gaps · covers gaps · broken references), read-only
  code               graph questions on the code provider: deps · impact · tests-for · symbol
  search             kb-search CLI (FTS · --semantic · --hybrid · --toc · --tags · --doc · --stats), reads the store
  embed              compute missing chunk embeddings (bge-m3, local) into the store
  search-eval        recall@k of fts · dense · hybrid against a query set (vault/_meta/search-eval.yaml)

  session tools (ported from strata/scripts, orders 2026.10.29-01 and -11):
  decision           decision record CLI: add · supersede · withdraw · regen-index · list · migrate · check-uncommitted
  ledger             shared session ledger: append · read · close · validate
  handoff            session handoff skeleton in the vault + gates + vault sync   (handoff <slug> [topic])
  vault-git          vault sync channel: pull · commit-push MSG [PATH...] (listed paths only)
  order              order claim before work starts: claim · release · show <order-id>
  views-publish      librarian, once a day: build-index, then commit-push only node pages and _index/review-needed.md
  retro-bundle       retrospective bundle for a period and project → $STRATA_VAULT/outputs/retro/
  sections           body section titles from the taxonomy (sections session)
  pre-compact        PreCompact hook: snapshot the active task into .strata/local/
  validate-naming    PreToolUse hook: naming rules from core/rules (stdin hook JSON or <file> [type])
  check-layer        PostToolUse hook: layer rules from core/rules + .strata/layer-map.yaml
  stamp              PostToolUse hook: stamp `updated` on vault knowledge docs and check frontmatter against the taxonomy
  atom-notify        hook: show the agent state on an M5Stack Atom Matrix LED over serial (always exit 0)

Run from any directory with `python3 "$STRATA_KIT/kb" <command>` (hooks keep the project cwd).
```

## tools/

| | |
|---|---|
| `tools/wizard.py` |  |
| `tools/doctor.py` |  |
| `tools/project_public.py` |  |
| `tools/gen_claude_plugin.py` |  |
| `tools/gen_codex_bundle.py` |  |
