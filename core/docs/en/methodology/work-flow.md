# Work flow — from an idea to operation and back

> Canonical: strata-kit `core/docs/en/methodology/work-flow.md` (2026-11-01, MB-strata-kit-2026-019, DEC-2026-11-01-03).

> One page for the whole flow: what each stage takes in, what it leaves, when the next stage can start, who does it, and where in the kit it lives. The kit does not enforce the order. When a skill ends it suggests what may follow (`python3 -m kb skills next <skill>`), with "do nothing" always on the list, and the person chooses; a project's `standing: {<area>: decides|proposes}` changes the order and the wording of the suggestions, never what is allowed (DEC-2026-10-31-37).

## Stages

| Stage | Takes in | Leaves | Next can start when | Role | Lives in | Now |
|---|---|---|---|---|---|---|
| Idea | the person's words, a hunch, a problem | one idea note (five facets, conditions, confirmed weight) | the person chooses — there is no threshold; an idea can be used at any stage | builder | pack `ideation` (`ideation.shape`, `kb ideas`) | exists |
| Planning | an idea note, or a planning source from outside (Notion, a ticket) | a planning bundle: the source (`source/`), evidence (`audit/`: fact list, crosswalk, defects, isolated rules, impact), refined documents (PRD, Logical Tech Spec) — only refined documents and decisions are injected | `kb planning check` shows no row without a destination, no double count, no code expression, and a fresh-context check ran | builder | core `strata.planning` | exists |
| Specification | a planning document | desired specification: goals, scope, testable criteria with evidence, constraints, difference list | every criterion names its evidence | builder | core `strata.spec` | exists |
| Design | a specification or request with something to design (document, physical object, image, post, screen) | the person's design brief (purpose, audience, medium, constraints, references with reactions, acceptance criteria, deliverable), leaning on the project's or brand's taste note and techniques with computed relations | the person judged the acceptance criteria and the deliverable is pointed at with `design_ref` — into a product, the frontend design contract (the implementation flow, independent of the pack) takes over | builder | pack `design` (`design.brief`, `design.taste`) | exists (pack) |
| Order | an approved specification (and contract) | an order and one task file per layer and worker | every task is complete enough to build without guessing | builder | core `strata.order` | exists |
| Build | one task file | code, tests, evidence | tests pass within the task's layer | worker | core `strata.build-task` | exists |
| Verify | a completion claim | evidence attached to the claim | the evidence is fresh and covers the claim | any | core `strata.verify` | exists |
| Review | a decision or change worth a second look | the reviewer's answer and what was done with it | the answer is acted on | reviewer | core `strata.review` | exists |
| Release | a verified change | a deployment with a pre-deploy note (facts, assumptions, rollback) | only what a local run cannot confirm is checked in the environment | operator | card `rec.deploy.only-for-env-specific-verification`, role operator — the deploy procedure differs per project, so the core keeps no skill (DEC-2026-11-01-17) | yes (card and role) |
| Operate | the running system: strata's own measurements, and the outputs of the product's own flows (a QA ledger, coverage test cases), read only | indicators over time; one signal note for each indicator that moved the worse way, with the destination a person chose | a person has chosen what to improve (a methodology backlog entry, a decision, an idea note, a planning document, or drop) and the receiving item exists | librarian (daily indicators and candidates), builder (with the person) | core `strata.signal`, `kb indicators` (the project's read-only commands in its Tier P `indicators.yaml`), `kb signals`. The kit never writes to the product's flows; product incidents and feedback are the product's own (DEC-2026-11-01-17) | yes |
| Retrospective | a period, a project or one decision | the person's learning note and candidates handed on | the person has explained in their own words | builder | core `strata.retro` | exists |

From the retrospective and from operation, the flow returns to ideas and the backlog.

## How the stages' outputs link

Each link is a field in a document and a check that reads it (DEC-2026-11-01-18). A check of the newer stages runs under the enforcement family `stages`, advisory unless the project raises it (`kb enforce run --family stages -- <check>`).

| From → to | Link | Check |
|---|---|---|
| Idea → planning | the bundle's `source/` keeps the idea note it came from | `kb planning check` (every fact has a destination) |
| Planning → existing work | `audit/impact.md`: specifications, code, decisions and other plans on the plan's topic nodes | `kb planning impact` |
| Planning ↔ specification | the specification's `sources:` names the plan; the plan's `implementation.spec` points back | `kb divergence` (a person judges plan against code) |
| Specification → design | the task's `design_ref` names the design artifact | `kb design check` |
| Specification → task | the task's `scope.docs_to_update` and the constraints filtered from the registry | strata.order validation |
| Specification ↔ code | `covers` (paths, symbols) | `kb coverage-gate` |
| Decision ↔ code | the decision's `affects` | `kb coverage-gate` recheck (advisory) |
| Operation → next work | an indicator's `nodes` reach its signal note; the note's `routed_to` names the backlog item, decision, idea or plan a person chose | `kb signals check` |
| Retrospective → next work | the learning note's candidates, each with where it went | strata.retro validation |

## Across every stage

These are not stages; any stage may need them.

| Skill | When |
|---|---|
| `strata.decision` | the moment a constraint on future work is decided or discovered |
| `strata.kb-update` | code a knowledge document owns has changed |
| `strata.handoff` | a session or task ends |
| `strata.distill` | a judgement holds beyond this project |
| `strata.translate` | a card, skill or document needs its other locales |
| `using-strata`, `strata.init-wizard` | entering a session; setting up a project |

## Where a stage lives

- **Core** — every session needs it, whatever the project: specification, order, build, verify, review, retrospective, planning (DEC-2026-11-01-03), and operations signals (DEC-2026-11-01-14).
- **Pack** — only people who choose it use it; installed into the user layer (`kb skills install`): ideation.
- **Profile card** — tied to a kind of project (frontend, backend): design contract.
- **Project layer** — tied to one product or domain (its screens, ledgers, defect store).

## Suggestions between stages

Each core skill has `next:` candidates in `skills/next.yaml`, beside the registry — the skill, a reason, and optionally an area and the wording to use when that area only proposes. They sit outside the registry so that routing at session start does not read them (DEC-2026-11-01-15); a pack or project layer may still put `next:` inside its routes. `kb skills next <skill>` prints them in order, with "do nothing" last, and exits 0 in every case. What the person picks is written in the active file and the handoff's judgement section; it is a decision record only when it settles an architecture question.

## Gaps, in the order they will be filled

No stage in the table is waiting to be filled. A plan's impact on existing work — the specifications, code, decisions and other plans on its topic nodes — is written to the bundle's `audit/impact.md` by `kb planning impact` (DEC-2026-11-01-16).
