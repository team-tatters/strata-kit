---
name: strata.signal
description: Use when an indicator got worse — a trend in strata's own measurement table, or a product-flow indicator the project reads from its own flows (kb indicators) — or when open signal notes from the librarian's daily job wait for a destination; when the user says signal, indicator got worse, metrics got worse. Writes one signal note with its evidence, shows where it could go, and records the destination the person chooses; never files a backlog item or idea on its own and never writes to the product's own flows. Keywords - operations signal, indicator, metrics trend, route.
---

# strata.signal

```yaml
skill:
  id: strata.signal
  version: '0.2'
  owner: builder
  triggers:
  - the measurement table or the indicator history shows an indicator that moved the worse way
  - open signal notes from the librarian's daily job are waiting for a destination
  - '`kb signals check` lists signals open longer than 14 days'
  inputs:
  - the measurement table (projects/<p>/measurements/strata-metrics.yaml) and the indicator history (measurements/indicators.yaml), through `python3 -m kb signals candidates`
  - open signal notes in $STRATA_VAULT/projects/<p>/signals/
  outputs:
  - one signal note per indicator change, with observation, evidence and destination sections
  - the destination the person chose, recorded in the note with who chose it and when
  - the receiving item (backlog entry, idea note, planning document, decision) written in words the person approved, only after they approved
  required_context:
  - rec.process.confirm-before-state-change
  - rec.verify.evidence-not-impression
  - DEC-2026-11-01-17 (operations are indicators; the product's own flows are read, never written; signals are indicator changes only; a person chooses the destination)
  allowed_tools:
  - read
  - bash(python3 -m kb signals list|check|candidates|route, python3 -m kb indicators show)
  - write(a backlog entry, only with text the person approved)
  validation:
  - every signal note has evidence — the measured value with its comparison basis (previous revision or collection, threshold)
  - no note is routed without decided_by, and the person named there is the one who chose
  - every routed_to points at an item that exists (the check passes), written in approved words
  - nothing was written to the product's own flows (QA ledger, defect store, coverage reports)
  - '`python3 -m kb signals check --project <p>` exits 0'
  failure_modes:
  - 'the person reports a product incident, alert or user feedback: that belongs to the product''s own features (its defect store, its QA flow) — point there; do not write a signal note for it'
  - 'a product-flow indicator would help but the project has none: say which output could be read, and leave writing the read-only command in the project''s indicators.yaml to that project''s session'
  - 'the measurement table and indicator history are missing: run tools/metrics.py collect <repo> --write or kb indicators collect --write first'
```

## Overview

The operations stage shows indicators; it does not take over the product's flows. Two kinds feed it: strata's own measurements (kit revision, sessions, verification, handoffs, git) and product-flow indicators a project reads, read only, from flows it already has — a QA ledger, coverage test cases. When one moves the worse way, this skill keeps it as one note with its evidence and hands the choice to the person: it shows what the change could lead to and why, then records what the person picked.

## When to use

When the librarian's daily report lists new open signals, when the check lists stale ones, or when the person sees an indicator get worse and wants it kept. Not for a product incident, alert or user feedback — those belong to the product's own features. Not for deciding a rule (strata.decision). Writing a note raises a read-only session to single-session.

## Process

1. **Find the change.** Run `python3 -m kb signals candidates --project <p>` and show the candidates; `python3 -m kb indicators show --project <p>` shows the product-flow indicators against the collection before. Write the candidates with `--write` once the person agrees (the librarian's daily job writes them on its own, with no destination). Evidence: the candidate list or the note paths.
2. **Check the evidence.** Each note's evidence section holds the measured value with its basis — previous revision or collection, and the threshold. If a candidate rests on too little (one session, a single collection), say so in the note. Evidence: the note's evidence section.
3. **Show where it could go, and ask.** For each open signal give the candidates with one reason each: a methodology backlog entry (a gap in how we work or in the kit), an idea note (worth growing but not yet clear, ideation.shape), a planning document (work to plan, strata.planning), a decision (strata.decision, when it settles a rule), or drop it (noise, already handled). Improving the product's own flow is planned work like any other — it starts from the person's choice, not from this skill writing into that flow. Do not choose. Evidence: the candidates and the question.
4. **Make the receiving item, then record the choice.** Write the receiving item only with text the person approved: show the backlog entry before adding it; hand an idea to ideation.shape and planning to strata.planning. Then run `python3 -m kb signals route --project <p> <note> --to <item id or vault path> --by <person>`. For a drop, `--drop "<reason>" --by <person>`. The command refuses a target that does not exist yet. Evidence: the route output.
5. **Check the notes.** Run `python3 -m kb signals check --project <p>`. Fix every problem it lists; show signals open longer than 14 days to the person as a question, not as a decision you make. Evidence: the command output and exit code.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The trend is obvious; I'll add the backlog item directly." | Then nobody chose it, and the next reader cannot see where it came from. Write the signal, show the candidates, let the person pick. |
| "The person is busy; I'll pick the most likely destination." | The destination is the person's (DEC-2026-11-01-17). Leave it open and ask; an open signal costs nothing, a wrong item costs a cleanup. |
| "The QA indicator got worse; I'll register the defect or fix the ledger." | The QA ledger and defect store are the product's own flow. The kit reads them; changing them is planned work the person chooses. |
| "This incident report is important; I'll keep it as a signal too." | Incidents and feedback have a home in the product's features. A second copy here splits the record. |

## Red flags

- A backlog entry, idea note or decision created from a signal with no approval from the person.
- A routed note whose decided_by is the agent or the librarian.
- A note without the comparison basis in its evidence.
- Any write to the product's own flows (ledger, defect store, coverage reports) made from this skill.

## Verification

- Each new note sits in projects/<p>/signals/ and its evidence has the value and its basis.
- Every routed note names the person who chose, and its target exists.
- Nothing was written to the product's own flows.
- `python3 -m kb signals check --project <p>` exits 0, and stale signals were put to the person.
