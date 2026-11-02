# Skill packs

Packs that the kit ships live here as `skills/packs/<pack>/` (a `registry.yaml` with `stage` and `kind` per route, and
one directory per skill). A person installs one into the user layer with `python3 -m kb skills install <pack> --apply`
and makes the harness see it with `python3 -m kb skills link --harness claude|codex --apply`. The user layer
(`~/.strata/skills`: `packs/` from the kit, `local/` for the person's own skills) is read after the profile and before
the project and only adds; a local skill may replace a core skill only by naming it with `overrides:`, and the session
header shows it (DEC-2026-10-31-36). Packs carry the same checks as the core (i18n, evals); local skills do not.

Packs are not shipped in the Claude plugin or the Codex bundle; the user layer is the only way in. A route may list
`next:` candidates (`{skill, why, area, on_proposes}`), shown by `python3 -m kb skills next <skill>` in the order the
project's `standing` gives them, always with "do nothing" (DEC-2026-10-31-37).

- `ideation` — `ideation.shape` (stage ideation, kind procedure): organises an idea in one vault note with five facets,
  conditions and a confirmed weight, with `python3 -m kb ideas` for the notes (planning/ideation-pack, DEC-2026-10-31-38).
  Its constraint list comes from jwynia/agent-skills brainstorming v1.1 (MIT), see `ideation.shape/data/NOTICE.md`.
- `design` — `design.brief` (stage design, kind procedure): the person's design stage in any medium (document,
  physical object, image, post, screen) — a brief in the person's words, with what they reacted to in each reference.
  Independent of the frontend design contract, which takes a deliverable only at `design_ref` (planning/design-stage,
  DEC-2026-11-01-09). `design.taste` (stage design, kind procedure) keeps one taste note and one expression note per
  project or brand: signals in the person's words, inferences marked, promotion by the person after three different
  briefs; techniques as primitives and computed relations, checked with `python3 -m kb taste check · expression`
  (DEC-2026-11-01-10 · 11). The brief's purpose starts with what is being designed (its `category`), which picks the
  adapter in `design.brief/data/adapters.md`: slides, reports and infographics take the document adapter; web pages
  and app screens take a design skill the person already has, such as Taste Skill or Impeccable, or else a short
  fallback — never both (DEC-2026-11-01-12 · 13, see `design/NOTICE.md`). `python3 -m kb design check` is a contract-side tool, not part of the pack.

Domain skills that bind to a product (its screens, defect store, ledgers) live in that
project's own registry layer, which `using-strata` reads third, after the core and profile registries:

- embedded project: `<project>/.strata/skills/registry.yaml` and the skill directories next to it
- detached project: `vault/projects/<name>/strata/skills/registry.yaml` (Tier P), with local symlinks under the
  checkout's `.claude/skills/` and `.strata/skills` that git excludes

The `qa` pack (qa.extract-action-chains, qa.stage-measure, qa.triage, `_qa-shared/criteria-v1.md`, `qa-ledger.py`)
moved to the Tier P of the web project it served on 2026-10-28 (DEC-2026-10-28-16, superseding DEC-2026-10-28-06): it binds to the 3.0
screens, the maintenance-api defect store and the vault QA ledgers, which are product knowledge, not methodology.
Adapters (Claude plugin, Codex bundle) therefore ship core skills only; a project's skills are loaded from the project.
