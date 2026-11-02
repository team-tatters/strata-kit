---
title: Cards
status: ready
generated: true
---

# Cards

> This page is generated from the sources — do not edit it by hand.

Every recommendation card. `must` is not negotiated, `should` can be switched off with a recorded reason, `may` is advice.

| Card | Strength | Claim | Applies when |
|---|---|---|---|
| `rec.architecture.no-layer-violation` | must | Depend only in the declared layer direction; never argue around a checker's block. | The project profile declares a layer-map |
| `rec.data.soft-delete-only` | must | Never physically delete domain data; mark it deleted and exclude it by default. | Persistent domain entities |
| `rec.decision.orchestrator-decisions-flow-to-records` | must | Decisions made through an orchestrator (relay, approval, flow) are recorded by the owning session with the relay or approval id as source. | Sessions running under Quilt or another orchestrator; cross-model reviews |
| `rec.decision.record-immediately` | must | Record architecture decisions in the same session with the decision CLI; never hand-edit the index. | Any choice that constrains future code: layering, contracts, data placement, policies |
| `rec.deploy.only-for-env-specific-verification` | must | Never deploy to check what a local run can check; before deploying, report purpose, facts vs assumptions and rollback. | Shared environments: dev, stage, prod |
| `rec.handoff.pending-has-blocker` | must | Every pending handoff item carries blocker and unblocked_by. | Every handoff and ledger close |
| `rec.kb.covers-owner` | must | Changed code that a contract depends on has one owning document (covers); update it or declare doc_change: none with a reason. | Projects with a knowledge base and covers declarations |
| `rec.kb.generated-views` | must | Never hand-edit generated views (indexes, DEC notes, node pages, search index); fix the source or the generator. | Every generated path listed in the share policy's generated_paths and the index manifest |
| `rec.kb.link-currency` | must | Link by file name to current documents only; a new link violation beyond the baseline blocks session close. | Every vault document with wikilinks |
| `rec.kb.session-records-in-vault` | must | Handoffs, ledgers, tasks, orders and relay packets go to the vault, never into a code repository. | Every session on every project |
| `rec.naming.follow-convention` | must | Follow the profile's naming convention; explain any deviation. | The profile ships a naming-convention file |
| `rec.placement.minimal-strata-in-code-repo` | must | A code repository holds only CI-run enforcement and the .strata/profile.yaml pointer; guidance, hooks and records stay outside unless the team adopted the kit. | Shared code repositories (work domain), and any repository another person commits to |
| `rec.process.confirm-before-state-change` | must | Before any state change (files, commits, deploys, deletes, external calls) show purpose, impact and rollback and get confirmation; reads are exempt. | Every session, every execution mode |
| `rec.session.state-in-files` | must | A session that changes state keeps its active task, progress and handoff in files (local active, vault); a read-only session leaves none. | A session that changes files or external state (single-session, multi-session or orchestration mode) |
| `rec.verify.evidence-not-impression` | must | Report done only with evidence (test output, exit codes, paths); state what was not verified. | Every task completion report |
| `rec.workflow.worktree-only-with-consent` | must | Work sequentially in one checkout; create a worktree only after the person accepts a proposal. | Every mode, including automatic mode |
| `rec.backend.cqrs-layers` | should | Code depends only downward through L1 → LM1 → L2 → LM2 → L3 → Route. Commands and queries are separate paths; a REST DTO never crosses into a lower layer. Same-layer references are allowed only within the declared meaning. | Kotlin or Java services on Spring with more than one aggregate |
| `rec.context.entry-view-budget` | should | What every session reads before acting (AGENTS.md, CLAUDE.md index, must cards summary) stays under 12 KB. Decision indexes, registries and node pages load on demand through the entry view's links. | Every project |
| `rec.decision.extract-constraint` | should | When a recorded decision adds a rule that code must follow (a forbidden call, a required pattern, a layer boundary), the same session extracts it into the project's constraint registry with the decision id as its source, so the rule reaches task specifications and reviews instead of staying inside the decision text. | A decision record whose decision text names a rule for code |
| `rec.frontend.design-contract` | should | Colors, type, spacing, radius and motion are referenced through design tokens; components expose named variants instead of ad-hoc props; a deterministic checker flags literal values in UI code. | A design system or shared UI package exists |
| `rec.frontend.layered-surfaces` | should | UI code depends only upward through Foundation → Contract → DataState → Primitive UI → Semantic Component → Feature Block → Route Surface → App Shell. Data fetching lives in DataState; route surfaces compose feature blocks and own nothing else. | Apps with more than a handful of screens or a shared component set |
| `rec.kb.document-roles` | should | A knowledge document describes the as-built shape and is updated in place; a planning document holds the desired shape and its implementation review; an archive document (session, task, relay) is evidence and is never edited after the fact; an index (MOC, node page, decision note) is generated. A document never mixes roles. | Every vault document |
| `rec.kb.update-in-place` | should | A knowledge document is corrected where it stands: the relevant section changes, updated and sources are set, and the previous state lives in git history. New dated copies, appended changelogs inside the document, and date stamps without a content check are not updates. | Knowledge documents (as-built) |
| `rec.session.split-at-task-boundary` | should | A session is split when a task completes or its shape changes, after the handoff is written; trimming starts at about 75% of the context, keeping the task, the active error and the file being edited, and dropping failed attempts to their conclusion. Two signals bring the split forward without cutting a unit in half: when the conversation passes the warning line (about 400,000 tokens by default, with a limit of about 600,000; starting values with no measurement behind them; session.restart_tokens and session.restart_limit in the user config), finish the unit at hand and split at the next task boundary, before the limit at the latest; when attempts are blocked twice, do not look for a third workaround — stop and report the measured facts and the options. Two failures on one hypothesis means two fixes built on the same presumed cause that fail with the same symptom. The handoff then separates confirmed facts, unconfirmed assumptions and discarded hypotheses. | Long sessions and multi-task work |
| `rec.spec.desired-vs-as-built` | should | Requirements and acceptance criteria live in a desired specification (planning); the current behaviour lives in knowledge documents (as-built). A future requirement is never written into an as-built document as if implemented. Done means the two converge, and the convergence check is the gate. | Any feature work with a planning document |
| `rec.structure.prepaid` | should | Structure that offsets the cost of change is put in place from the start; layers are not reduced because the project is small today. The three boundaries a layer cannot cover (data ownership, cross-domain writes, cross-domain reads) are declared explicitly. | Expected lifetime of a year or more, or more than one domain writing data |
