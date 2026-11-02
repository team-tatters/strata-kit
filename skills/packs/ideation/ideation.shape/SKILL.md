---
name: ideation.shape
description: Use when the person brings an idea to organise or grow, a hunch that is not concrete yet, or is stuck producing the same ideas; when the user says idea, I have a thought, brainstorm, what if, I'm stuck. Gives questions and process, never the idea itself; keeps one vault note per idea with five facets, conditions and a confirmed weight. Keywords - idea, ideation, hunch, brainstorm, seed, stuck, organise.
---

# ideation.shape

```yaml
skill:
  id: ideation.shape
  version: '0.1.1'
  owner: builder
  triggers:
  - the person brings an idea, a problem they want to attack, or a hunch they want to make concrete
  - the person is stuck and every option feels like a variation
  - the person wants to return to an open idea note
  inputs:
  - the person's words
  - open idea notes and the load of thought (`python3 -m kb ideas list`)
  - references found with `python3 -m kb search` (ideas, decisions, failures — work projects included, with their source)
  - collision material from `python3 -m kb ideas draw`
  - facet distances, relation and link candidates from `python3 -m kb ideas near`, and the canvas from `python3 -m kb ideas map`
  outputs:
  - questions, one at a time
  - one idea note in $STRATA_VAULT/ideas/ written in the person's words, empty facets left empty
  - growth events recorded with `python3 -m kb ideas event`
  - next-flow candidates from `python3 -m kb skills next ideation.shape`, chosen by the person
  required_context:
  - rec.process.confirm-before-state-change
  - rec.data.soft-delete-only
  - README "Principles the kit encodes" (in ideation the agent gives questions and process, not ideas)
  allowed_tools:
  - read
  - bash(python3 -m kb ideas, python3 -m kb search, python3 -m kb skills next)
  - write(idea notes in $STRATA_VAULT/ideas/, only with the person's words or text they approved)
  validation:
  - every facet sentence in the note is the person's words or text they approved line by line
  - the weight is written only after the person confirmed or corrected the agent's estimate
  - empty facets stay marked empty; nothing is filled in to make the note look complete
  - the session ends with candidates from `kb skills next`, including "do nothing", and the person's choice
  failure_modes:
  - 'the person asks the agent for ideas: give collision material and a question about it; offer an example only when asked twice, labelled as the agent''s, and never write it into the note as theirs'
  - 'the vault has no references: say so, draw from the constraint list, and keep going'
```

## Overview

An idea is useful long before it is finished. This skill helps the person organise an idea until it can be used — in planning, a specification, a decision or a retrospective — without making the idea for them. Each idea is one note with five facets (origin, problem, method, outcome, meaning). Empty facets are allowed; they are the next questions. The agent estimates how many conditions and orders the idea still needs and asks the person to confirm it; the confirmed number is the idea's weight, and the weights of all open ideas are the load of thought the person is carrying. Ideas may grow without limit; an idea left without growth for more than 30 days is offered for archiving, never deleted.

The question method and the stuck-state toolkit follow jwynia/agent-skills `brainstorming` v1.1 (MIT): states described as signals, questions and interventions; its divergence protocol is a tool here, not the backbone.

## When to use

When the person brings an idea, a problem they want to attack, a hunch, or is stuck. Not for writing requirements (strata.spec) or recording a decision already made (strata.decision) — those are next-flow candidates. Not for generating ideas on the person's behalf. The conversation alone is read-only; writing or growing an idea note raises the session to single-session (DEC-2026-11-01-18).

## Process

1. **Bring it out.** Run `python3 -m kb ideas list` and search for similar open ideas and existing approaches (`python3 -m kb search "<the person's words>" --hybrid`). Show what exists and the load of thought, then ask: "What could this build on that already exists?" Offer three choices: a new note, add to an existing note, or strengthen what is already open and only jot this down. Evidence: the list and the person's choice.
2. **Nature.** Ask whether the idea attacks a clear problem or phenomenon, or tries to make an unclear intuition concrete. A problem idea starts from the problem, then outcome and method; an intuition starts from meaning and origin. Evidence: `nature` in the note.
3. **Five facets.** Ask one at a time: what does it solve (problem), what does it want to gain (outcome), what does the person find meaningful in it (meaning), what does it do to get there (method), where did it start (origin). Write the person's words. A facet the person cannot answer yet is written "비어 있음". If the method is filled while problem or outcome is empty, the idea is locked to a form: ask "What must this accomplish? Is this method one way of doing it?" Evidence: the note's facet sections.
4. **Conditions and weight.** Estimate the conditions that must be true for the idea to work and how many orders it would take; a minimum experiment can be a condition. Show the estimate and ask the person to correct or confirm it. Only then write `conditions`, `orders_expected` and `weight_confirmed`. Evidence: the person's confirmation.
5. **Widen, narrow, eliminate.** Use the empty facets as search terms for references; show each with its source. If candidates pile up, group them by approach and ask for one representative and a minimum experiment per group. The person chooses to widen or narrow the target and how to eliminate: hard elimination (remove what is unclear and focus on what remains) or soft elimination (organise everything, then compress through the links). Do not evaluate while facets are being filled; eliminate only when the person chooses to. Write eliminated cases and their reasons in the note. Among ideas, `python3 -m kb ideas near <note> [--embed]` shows facet by facet how close the other ideas are, relation candidates (alternative, exaptation, bundle, competition) with their values, link candidates and a neighbour-bias line; `python3 -m kb ideas map <note> [--facet F]` writes an Obsidian canvas centred on the idea. Neither writes the note: add only the links the person picks, each with a `link` event. Evidence: the eliminated-cases section.
6. **When stuck.** If every option is a variation, diagnose the state from its signals and use only the matching tool: convergence blindness → list the obvious options first; function lock → separate what from how; axis collapse → rotate who, when, scale or method; domain imprisonment → draw collision material with `python3 -m kb ideas draw --note <note>` (records outside the idea's projects first, the constraint list when records run short). Ask what the material collides with; the person writes what they see. Evidence: the material shown and the person's words.
7. **Record growth and close.** For each facet filled, link added, use in another flow or condition met, run `python3 -m kb ideas event <note> facet|link|use|condition "<what>"` (an archived note reopens). Then run `python3 -m kb skills next ideation.shape` and show the candidates as they are, "do nothing" included; the person chooses. Record the choice in the active file and the handoff's judgement section. Evidence: the event lines and the choice.

## Note format

`$STRATA_VAULT/ideas/<YYYY-MM-DD>-<slug>.md`, checked by `python3 -m kb ideas check`:

```markdown
---
title: "<the idea in the person's words>"
type: idea
created: YYYY-MM-DD
nature: problem | intuition
status: active | archived
projects: [<related projects>]
conditions:
  - {text: "<condition>", met: false}
orders_expected: 2
orders_done: 0
weight_confirmed: YYYY-MM-DD
---

# <title>

## 발단
## 문제
## 방법
## 결과
## 의미
## 소거한 사례
## 발전 기록

- YYYY-MM-DD facet — <what grew>
```

Archiving (`python3 -m kb ideas tidy --apply`, preview by default) only sets `status: archived` and `archived: {date, reason}`; the note stays where it is.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "A few example ideas would get them started." | Then the note holds your ideas. Give material and a question; the person writes what they see. |
| "The empty facet is obvious; I'll fill it in." | An empty facet is the next question. Filling it hides the gap the person should look at. |
| "The weight is just an estimate; I'll write it." | Only a confirmed weight counts in the load of thought. Ask first. |
| "This idea is clearly the next step to plan." | The flow is a suggestion. Show the candidates with "do nothing" and let the person choose. |
| "That idea has gone nowhere; delete it." | Archive, never delete. A half-baked hunch can meet its missing piece later. |

## Red flags

- A facet sentence the person did not say or approve.
- Evaluating ideas while facets are still being filled.
- A weight with no `weight_confirmed`.
- Novelty that does not serve the problem or the outcome.
- Ideation from scratch when existing approaches were not looked up.
- Treating "the opposite" as divergence — it stays on the same axis.

## Verification

- The note passes `python3 -m kb ideas check`.
- Every facet sentence and the weight trace back to the person's words in this session.
- Growth events were recorded for what changed.
- The person chose the next flow from the candidates.
