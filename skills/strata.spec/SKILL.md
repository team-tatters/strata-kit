---
name: strata.spec
description: Use when a feature or change needs its requirements, acceptance criteria and constraints written or revised before planning; when a planning document exists but has no desired specification; when the user says what to build, acceptance criteria, requirements, or asks whether the current behaviour matches the plan.
---

# strata.spec

```yaml
skill:
  id: strata.spec
  version: '0.2'
  owner: builder
  triggers:
  - a feature or change is requested and no desired specification exists
  - a planning document needs acceptance criteria
  - the user asks whether as-built matches the plan
  inputs:
  - planning source (user words, planning document, ticket)
  - current as-built knowledge documents for the touched area
  - applicable cards (must + should) from the registry
  outputs:
  - 'desired specification: goals, scope, acceptance criteria, constraints, open questions'
  - difference list between desired and as-built
  - candidate constraints for the registry
  - 'the planning document''s implementation block: status, reviewed, spec'
  required_context:
  - rec.spec.desired-vs-as-built
  - the project's constraint registry
  allowed_tools:
  - read
  - write(planning document)
  validation:
  - every acceptance criterion is testable and names its evidence
  - the as-built difference list exists, even if empty
  - open questions are listed with who answers them
  - each planning document written or changed has an implementation status other than unreviewed and a spec link, or a difference line saying no specification owns that code
  failure_modes:
  - 'the request contradicts a must card: stop and explain the card'
  - 'requirements cannot be stated without a decision from the user: stop and ask one question'
```

## Overview

Produces the desired specification for a change: what must be true when it is done, stated so that each criterion can be verified, and how it differs from what the system does today.

## When to use

A change is requested and no desired specification exists; a planning document lacks acceptance criteria; the user asks whether the plan and the current behaviour agree. Not for pure refactors with no behaviour change. Answering whether the plan and the behaviour agree is read-only; writing or revising a specification raises the session to single-session (DEC-2026-11-01-18).

## Process

1. Read the planning source and the as-built documents the change touches. Evidence: the list of documents read.
2. Write goals, scope (in and out), acceptance criteria (each with the evidence that will prove it), constraints from applicable cards, open questions with the person who answers each. Evidence: the planning document section.
3. List the differences between desired and as-built, one line each. Evidence: the difference list.
4. Flag any criterion that would need a new architecture decision; do not decide it here. Evidence: the flagged items.
5. Close with the implementation review of every planning document written or changed in this session. Set `implementation.status` from what steps 1 and 3 found (implemented, partial, diverged, not-implemented or superseded; never leave it unreviewed), `reviewed` to today, and `spec` to the as-built specification whose covers own the code that realises the plan. When no specification owns that code, write it as a difference line ("no specification owns <path>") instead of leaving `spec` out silently. The coverage gate follows `spec` from changed code back to the plan; a plan without it is invisible to the gate. Evidence: the implementation block. When the review finds the plan and the code disagree, queue a judgement request (`python3 -m kb divergence add`, or the gate's recheck rows with `kb coverage-gate --divergence-inbox`) and ask the person; never pick the judgement yourself (document-format planning rules, DEC-2026-10-31-35).

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The user already explained it in chat." | Chat is not a durable artifact. Write it into the planning document or the next session will not have it. |
| "Acceptance criteria can come after implementation." | Then they describe what was built, not what was wanted. Write them first. |
| "The difference list is obvious." | Write it anyway; the convergence gate reads it, not your memory. |
| "The implementation status can be reviewed later." | Later rarely comes: most imported plans stay unreviewed. Review the ones this session touched, now, while the code is open. |

## Red flags

- A criterion with no named evidence.
- A specification that changes an as-built document directly.
- 'Implement as discussed' with no document.
- A planning document closed as unreviewed, or with no `spec` and no difference line explaining why.

## Verification

- Every criterion names its evidence.
- The difference list exists.
- Open questions name their owner.
- Each planning document touched has its implementation block (status, reviewed, spec or the missing-spec difference line).
