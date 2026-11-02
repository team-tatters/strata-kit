---
name: strata.planning
description: Use when an outside planning source (a Notion plan, meeting notes, a ticket, an idea note) must become planning documents; when the user says turn this into a plan, organise the planning, PRD, planning document, fact list; before strata.spec when the source is raw. Splits the source into facts, gives every fact a destination, and keeps only the refined documents and decisions in the injected layer. Keywords - planning, PRD, fact list, crosswalk, source, refined.
---

# strata.planning

```yaml
skill:
  id: strata.planning
  version: '0.2'
  owner: builder
  triggers:
  - an outside planning source must become planning documents
  - an idea note is ready to become a plan
  - a planning bundle needs its crosswalk checked
  inputs:
  - the planning source (Notion page, meeting notes, ticket, idea note), kept as it came
  - decisions and constraints that already bind the area
  outputs:
  - 'a bundle projects/<p>/planning/<bundle>/: source/ (the original), audit/ (fact list, crosswalk, defects, isolated rules), refined documents (PRD, Logical Tech Spec, terms, tree)'
  - questions for the person on conflicts, gaps and the tree
  - decision records for anything that binds architecture
  - audit/impact.md — specifications, code, dependents, decisions and other planning on the plan's topic nodes (DEC-2026-11-01-16)
  required_context:
  - core/docs/<locale>/methodology/work-flow.md (the planning row)
  - the project's decision records for the area
  allowed_tools:
  - read
  - write(planning bundle)
  - 'run(python3 -m kb planning check · boundary · impact)'
  validation:
  - kb planning check on the bundle shows no row without a destination, no double count, no hand-off the receiver lacks
  - the refined documents carry no code or architecture expression, or each one shown is moved to a 'code' row
  - the check was run in a context other than the one that wrote the bundle (strata.review packet)
  - tree, isolations and defect handling were decided by the person, not by the agent
  failure_modes:
  - 'the source contradicts a decision record: stop and raise it as a question'
  - 'the person has not confirmed the tree: do not write the refined documents yet'
```

## Overview

The planning stage is a filter (DEC-2026-11-01-04). A raw plan mixes undecided talk, code and rules; if it is injected as it is, every later reader (a search, an injection tool such as Onyx, a teammate) reads garbage. So the source is never summarised straight away. It is split into facts, one per row, and every row gets a destination. Only the refined documents — the PRD (rules a person can observe) and the Logical Tech Spec (guarantees that survive a change of implementation) — and decision records are injected and shared. The source and the work tables stay as evidence. **Planning documents carry no code and no architecture**: tables, columns, classes, services, API paths, HTTP codes, frameworks and vendors go to the 'code' destination and become material for a specification, an order or a decision.

## When to use

An outside planning source arrives; an idea note (ideation.shape) is ready to become a plan; an existing bundle needs its crosswalk checked. Not for writing acceptance criteria of a plan that is already refined (strata.spec), and not for architecture choices (strata.decision). The work mode is read-only while the source is only being read; writing the bundle raises it to single-session, and a bundle that takes more than one session is multi-session — a handoff at each session end (DEC-2026-11-01-18).

## Process

1. **Source to fact list.** Put the source untouched under `source/` (or mark it `category: source`). In `audit/facts.md`, write one fact per row — rules, permissions, state transitions, exceptions, data, screens, acceptance criteria, decisions, assumptions, dependencies, revision history. Columns, in this order: `# | source location | type | content (one sentence that keeps the source's meaning) | role (planning · spec · code · background · duplicate) | axes | subtopic`. Axes are the five questions a rule must answer: identity, time, derivation, expiry, conflict; write `n/a` when none applies. Evidence: the fact list.
2. **Tree and decisions.** Group subtopics into a tree draft and get the person's confirmation before writing any body. Conflicts between sources, or with later decisions, become questions; an answer that binds architecture is recorded with strata.decision. Evidence: the confirmed tree, the questions and their answers.
3. **Write the refined documents and give every row a destination.** In `audit/coverage.md` (`# | source location | destination | note`), each fact gets exactly one of seven destinations: `<document> R<n>` (reflected in a refined document), `isolated:<group>`, `defect:<what>`, `code`, `background`, `duplicate:#<n>`, `out of scope:<bundle>` (the receiving bundle's crosswalk holds the same row). Contradictions and gaps go to `audit/defects.md` with how the refined documents handled them. Mark the PRD and Tech Spec with `planning_doc: prd` / `tech-spec`. Evidence: the crosswalk.
4. **Complexity review.** When a feature's policy outgrows what a person can hold (the check reports a PRD over 800 words or 10 rules, a Tech Spec over 1,200 words), build a policy table per state and propose isolating stages or states. Isolation changes the policy, so the person decides; moved rules go to `audit/isolated.md`. Evidence: the proposal and the decision.
5. **Check, in a fresh context.** Run `python3 -m kb planning check <bundle>`: rows without a destination, double counts, hand-offs the receiver lacks, rule rows with no axis, limits, code expressions in refined documents (only there — source and audit may name anything). Fix and rerun. Then send the bundle to strata.review for a check-only pass; the context that wrote the bundle is lenient with it. Evidence: the check output and the review answer.
6. **Impact.** Run `python3 -m kb planning impact <bundle>`. From the topic nodes in the refined documents' frontmatter it writes `audit/impact.md` (generated, evidence only): the specifications on those nodes, the code they cover, the code one hop away and its tests (`--depth` for more), the decisions on the nodes, and other planning on the same nodes. Show the person the summary line and anything that conflicts — a current decision the plan contradicts, another plan on the same node. Whether to change a specification or supersede a decision is the person's call. With no nodes, ask which topic nodes the plan belongs to. Evidence: the summary line.
7. **Next.** `python3 -m kb skills next strata.planning`: strata.spec for acceptance criteria, strata.decision, or nothing. **Decision shortcut:** when the source is only an agenda for a decision, skip the refined documents and go from the fact list straight to strata.spec or strata.decision.

## Injection boundary

Injected and shared: refined documents and decisions. Evidence only: `source/`, `audit/` and anything marked `category: source` or `audit`. The boundary holds by path and by category (DEC-2026-11-01-05): knowledge search skips the evidence; `python3 -m kb planning boundary` prints the exclusion paths for a GitHub connector and the share.yaml `never` lines; `--list` prints the refined documents an injection tool may read. Notion is outside the kit: keep the page for refined documents apart from the page for sources, and point the connector at the refined side.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The source is short; a summary is enough." | A summary decides silently what to drop. The fact list shows every drop as a row with a destination. |
| "The table name makes the rule clearer." | It ties the plan to one implementation and leaks into injection. Move it to a 'code' row. |
| "I wrote it, I can check it." | The writing context is lenient. Check in a fresh one. |
| "The conflict is obvious; I'll pick the newer source." | That is a policy choice. Record it as a defect and ask. |

## Red flags

- A refined document written before the person confirmed the tree.
- A fact list with fewer rows than the source has rules.
- A crosswalk row with no destination, or the same row counted twice.
- A refined document naming a table, a class, an API path or a vendor.
- The source edited in place.

## Verification

- `kb planning check` shows no missing destination, double count, broken hand-off or code expression.
- The tree, isolations and defect handling name the person's answer.
- A fresh-context review ran on the bundle.
- The source sits under `source/`, untouched.
