---
name: strata.retro
description: Use when the person wants to look back on past work to understand it better: why a decision went the way it did, whether a better one existed, what background knowledge sat under it; when the user says retrospective, look back, why did we decide, what would I do differently. Builds a retrospective bundle and asks questions; never hands over conclusions. Keywords - retrospective, look back, learn from past decisions, NotebookLM bundle.
---

# strata.retro

```yaml
skill:
  id: strata.retro
  version: '0.1'
  owner: builder
  triggers:
  - the person asks to look back on a period, a project or a decision
  - the person asks why something was decided, or whether a better choice existed
  - a period or project closes and the person wants to learn from it
  inputs:
  - period, project, and optionally a node or a search term (chosen with the person)
  - the retrospective bundle from `python3 -m kb retro-bundle` ($STRATA_VAULT/outputs/retro/<name>/)
  outputs:
  - questions, and sources pointed at once the person has explained in their own words
  - with the person's consent, a learning note in $STRATA_VAULT/retrospectives/ written in the person's words
  - candidates handed on with the person's consent: a lesson to distil, a backlog entry, a decision to supersede
  required_context:
  - rec.process.confirm-before-state-change
  - README "Principles the kit encodes" (in retrospectives the agent gives questions and process, not conclusions or ideas)
  allowed_tools:
  - read
  - bash(python3 -m kb retro-bundle, python3 -m kb search)
  - write(one learning note in retrospectives/, only after the person agrees)
  validation:
  - the first substantive turn is a question, not a verdict or a summary of what went wrong
  - every pointer to a record names the bundle file and heading it came from
  - the learning note's understanding section is the person's words, or text the person approved line by line
  - every candidate handed on was confirmed by the person and went to the skill that owns it
  failure_modes:
  - 'the person asks for the agent''s verdict: give the evidence on both sides and ask what they make of it; state an opinion only when asked twice, labelled as one'
  - 'the bundle is empty for the conditions: say so and widen the period or drop the filter with the person'
```

## Overview

A retrospective is for the person's understanding, not the agent's efficiency. The agent prepares the material and asks; the person explains in their own words; the agent then points at what the records say and where they are silent. The result is a note the person wrote, plus anything worth carrying into the methodology or the decisions, each handed to the skill that owns it.

## When to use

When the person wants to look back: at a week, an order, a project phase, or one decision and its chain. Not for checking whether work is finished (strata.verify) or for an independent review of a change (strata.review). The work mode is read-only until the person agrees to write a note; writing it raises the session to single-session.

## Process

1. **Agree the material and build the bundle.** Settle with the person either a period and project, or one decision to start from (its supersede chain and the reviews and sessions that name it — a smaller bundle when a whole period is too much), and any node or search term. Run `python3 -m kb retro-bundle --project P --from D --to D [--node N] [--query Q]` or `python3 -m kb retro-bundle --project P --decision DEC-id`. Tell the person the folder and the counts from `00-목차.md`, and that the folder can go to NotebookLM as it is. Evidence: the folder path and counts.
2. **Let the person choose what to look at.** Show the item list from the bundle's `00-목차.md` as it is: each decision, review and session with the facts from its record (date, nodes, supersede relation, linked reviews or decisions). Ask which to start with. If the person asks what an item says, quote its conclusion section from the bundle word for word, with file and heading. Do not summarize, rank, or say which went badly. Evidence: the person's choice.
3. **Ask before saying anything about it.** For the chosen item, ask one question at a time: what the premise was, why the alternatives lost, what is known now that was not then, what they would choose today and why. Wait for the person's answer in their own words. Evidence: the questions asked.
4. **Point at the records after the person has explained.** Where the explanation and the records differ, or the records are silent (no alternatives, no background, a reversal in the session's judgement section), quote the bundle with file and heading and ask about the gap. Give no verdicts such as "that was a good decision". Evidence: each pointer with its source.
5. **Write the learning note, with consent.** Ask whether to keep a note. If yes, say the session is moving to single-session and write `$STRATA_VAULT/retrospectives/<YYYY-MM-DD>-<topic>.md` with frontmatter `title`, `type: reference`, `created`, `tags: [retrospective, project/<p>]`, `source` (the bundle conditions), and three sections: **What was looked at** (bundle conditions and the items chosen), **Understanding in my words** (the person's words, or text they approved line by line), **Candidates to hand on** (each with where it goes and its status). Evidence: the note path.
6. **Hand on the candidates the person confirms.** A lesson that holds beyond this project → strata.distill. A gap in the method → a backlog entry. A decision the person would now make differently → strata.decision with supersede. Each one only after the person says yes. Evidence: the skill invoked per candidate, or "none" with the reason.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "I can see what went wrong; saying it saves time." | Saving time is not the goal here. The person's own explanation is what builds understanding; your conclusion replaces it. |
| "A short summary of the decisions first will help." | A summary is a verdict on what mattered. Show the items with their record facts, quote a conclusion word for word when asked, and let the person choose. |
| "I'll draft the understanding section and they can edit it." | Then the note is yours. Write their words, or what they approved line by line. |
| "This candidate is obviously a backlog item; I'll file it." | Filing changes state. Ask first, then hand it to the owning skill. |

## Red flags

- A first reply that evaluates, ranks or summarizes the period.
- A pointer to a record without the bundle file and heading.
- A learning note whose understanding section reads like the agent's prose.
- A backlog entry, distilled pattern or superseding decision the person did not confirm.

## Verification

- The bundle was built with the agreed conditions and its counts were shown.
- Questions came before any pointer, and every pointer named its source.
- If a note was written: the person agreed, it sits in retrospectives/, and its three sections are filled as described.
- Every candidate handed on was confirmed and went to its owning skill.
