# Contributing to strata-kit

Thank you for looking. A few rules keep the kit consistent.

## Where things live

- **Rules live once, in `core/`.** A recommendation is a card (`core/cards/*.yaml`), a layer or naming rule is in
  `core/rules/`, a procedure is a skill (`skills/*/SKILL.md`). Do not restate a rule elsewhere; link to it.
- **Generated files are regenerated, never edited by hand:** the Claude Code plugin and Codex bundle (`tools/gen_*.py`),
  project guidance (`tools/wizard.py generate`), decision indexes and notes.
- **Six locales.** Cards carry `en ko ja zh es fr` in one file; skills and docs have one file per locale. English is
  canonical (`LOCALES.md`). If you change English text and cannot translate it, mark the other locales pending
  (`i18n/pending.yaml`) instead of leaving them silently stale.

## Changing behaviour

- A change that constrains future work (a new card, a changed rule, a new check grade) comes with a decision record:
  `python3 kb decision add --slug … --topic … --decision … --reason … --alternative "…: why it lost"`.
- A new check or a fixed defect comes with a test that fails without the change.
- Skills: if you change what a skill makes the agent do, add or update a pressure scenario in `skills/<skill>/evals/`
  that fails without the skill and passes with it.

## Before a pull request

```sh
python3 -m unittest discover -s kb/tests -t .
python3 -m unittest discover -s tools/tests
python3 tools/cards_check.py
python3 tools/i18n_check.py
```

Examples in docs, cards and tests use neutral names (`shop-api`, `shop-web`, `com.example`, `alice`). Do not put
names, paths or figures from your own employer's or clients' projects into the kit.
