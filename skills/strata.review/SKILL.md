---
name: strata.review
description: Use when a non-trivial decision or change needs an independent check: building a review packet (level 0 to 4) with the decision, evidence and a bounded request, sending it to a fresh-context reviewer, and acting on the answer; when the user says review, second opinion, cross-check, send to Codex, doubt. Keywords - review packet, cross review, reviewer, second opinion, level.
---

# strata.review

```yaml
skill:
  id: strata.review
  version: '0.1'
  owner: builder
  triggers:
  - a decision or change is non-trivial and deserves an independent check
  - the user asks for a review or second opinion
  - a worker finished a task that touches a contract
  inputs:
  - the decision or diff
  - evidence paths with line ranges
  - the reviewer session or relay target
  outputs:
  - a review packet (level, decision anchor, evidence, request, open questions)
  - the reviewer's answer attached verbatim
  - 'a triage: accept, revise, escalate, with reasons'
  required_context:
  - rec.verify.evidence-not-impression
  allowed_tools:
  - read
  - bash(relay or hub_send)
  - write(packet record)
  validation:
  - the packet names level, decision, evidence and a bounded request
  - one round trip per packet; no automatic back-and-forth
  - the triage result and reasons are recorded
  failure_modes:
  - 'the packet has no evidence or no request: do not send it'
  - 'the reviewer edits code: reject the answer and re-send with the rule'
```

## Overview

Gets an independent check from a fresh context without sharing the whole conversation: a structured packet with the decision, pointer-first evidence and a bounded request, one round trip, and a recorded triage of the answer.

## When to use

For non-trivial decisions, contract-touching changes, or on request. Not for every edit; the packet costs a reviewer context.

## Process

1. Choose the level (0 pointer, 1 summary, 2 decision + evidence, 3 diff, 4 full) by what the reviewer needs. Evidence: the level and reason.
2. Write the packet: decision anchor, evidence as path:lines, request limited to one or two gaps, open questions. Evidence: the packet file.
3. Send to a reviewer session that is not the working session; one round trip. Evidence: the relay record.
4. Attach the answer verbatim and triage: accept, revise, escalate. When the review came from outside the working session (another model, a person, a cross review), also write a review record in the vault at projects/<project>/reviews/<date>-<slug>.md, type review, with review_of (the revision reviewed), received and source: a 'response summary' section (accepted, rebutted, findings the report missed, user decisions, resulting decisions and orders) and the 'original' section verbatim (DEC-2026-10-30-03). Evidence: the triage with reasons and the review record path.
5. If the answer changed a decision, record it with strata.decision.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "I will just ask in my own context." | Your context carries your assumptions. The point is a fresh one. |
| "Send the whole conversation so nothing is missed." | Whole conversations bury the question. Pointer-first evidence, bounded request. |
| "The reviewer agreed, done." | Record the triage. Agreement without a record is not evidence. |

## Red flags

- A packet with no request.
- Multiple automatic rounds.
- Reviewer output edited before attaching.

## Verification

- Packet complete.
- One round trip.
- Triage recorded.
