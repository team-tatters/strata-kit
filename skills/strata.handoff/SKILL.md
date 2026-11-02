---
name: strata.handoff
description: Use when a session ends, when the task boundary is reached, before a context split or compaction, or when the user says handoff, wrap up, end session, save state. Keywords - handoff, ledger close, wrap up, end of session, pending, blocker.
---

# strata.handoff

```yaml
skill:
  id: strata.handoff
  version: '0.2'
  owner: builder
  triggers:
  - the session is ending or splitting
  - a task boundary is reached
  - the user asks for a handoff
  inputs:
  - this session's completed work, pending items, decisions, changed files
  - the latest ledger and active-task file
  outputs:
  - handoff document with completed, in_progress (blocker + unblocked_by), decisions_made, warnings, next_session
  - 'spine edges: orders, kb_updates'
  - distillation candidates (ids or none with reason)
  - publish step with explicit path list
  required_context:
  - rec.handoff.pending-has-blocker
  - rec.session.state-in-files
  allowed_tools:
  - read
  - write(handoff)
  - bash(handoff script, ledger close)
  validation:
  - every pending item has blocker and unblocked_by
  - decisions_made lists DEC ids recorded this session
  - the publish step staged only the listed paths
  - distillation candidates or 'none' with a reason are present
  - progress-state facts this session wrote to memory were proposed for the handoff; any removal was approved per fact and archived, not deleted
  - under an orchestrator (Quilt relays, approvals, flows), decisions_made cites the relay or approval id as each record's source, or says none (rec.decision.orchestrator-decisions-flow-to-records)
  failure_modes:
  - 'uncommitted decision records exist in an embedded project: warn and list them'
  - 'the coverage gate reports new divergence: fix or declare doc_change before closing'
  - 'the coverage gate grade is unresolved (FAIL or BLOCK): no-go — write the specification or a reasoned, dated override before closing'
```

## Overview

Writes the handoff that lets the next session continue without this conversation: what was done with evidence, what is pending and why, which decisions were recorded, what to watch, and what to distil into the personal core. Then records, verifies and publishes as three separate steps.

## When to use

At the end of a session, at a task boundary, before a split or compaction, or on request. How much to write depends on the work mode (using-strata): read-only writes no handoff; single-session writes one only when pending items remain; multi-session and orchestration write one at every session end.

## Process

1. Record: write completed (with files and evidence), in_progress (blocker and unblocked_by for each), decisions_made (DEC ids), the judgement trail (what the person was asked and answered, judgements that were reversed and why, in a few lines, under the section of that name — DEC-2026-10-30-03), facts and hypotheses (confirmed facts with what confirmed them, assumptions not yet confirmed, discarded hypotheses with why — filled whenever the session ends on a restart signal: the conversation passed the token warning line, or attempts on one hypothesis were blocked twice; DEC-2026-10-31-11, session-splitting 5.1), warnings, next_session. Evidence: the handoff file.
2. Spine: fill orders and kb_updates links. Evidence: the frontmatter.
3. Distil: list distillation candidates for the personal core, or 'none' with the reason. Evidence: the candidates section.
4. Memory: run `python3 -m kb hygiene --memory` and look at the facts this session wrote or changed. Propose moving each progress-state fact (work at hand, what comes next, uncommitted changes, blockers) into in_progress or warnings of this handoff, and set `verified` to today on the facts the person confirms are still right. Removing a fact from memory is a separate question asked after the move: only for facts the person approves one by one, by moving the file to `_archive/` with `retired` and `retired_reason` and dropping its index line — never a plain delete (context-protocol §7, DEC-2026-10-31-16·17). Evidence: the proposal and the person's answers, or 'no memory written this session'.
5. Verify: run the coverage gate, link check, uncommitted-record check. Evidence: outputs. The gate's line 'unowned changed code N · candidates M · new spec needed K' (with the modules that need a specification of their own) goes into the handoff; its covers candidates wait in projects/<project>/_meta/covers-candidates.yaml (source: impact) until someone approves them and runs `python3 -m kb hygiene --covers-apply`. When the session changed knowledge rather than code (a concept, policy or decision), the gate also lists 'code to recheck (advisory)' — the covers of the specifications on the same topic nodes and the affects of superseded decisions; name in the handoff what was rechecked or why not. When the gate's grade is unresolved (a FAIL or BLOCK line; the script puts a 'no-go' line at the top of the handoff and on stderr), the session does not close as done: write the specification (strata.kb-update) or leave an override with reason and date in the Tier P gate-overrides.yaml, and name which one in the handoff (DEC-2026-10-29-08).
6. Publish: stage only the listed paths (handoff, ledger, mirrors) and commit through the session-end channel; report push success or failure truthfully. If the remote moved, never rebase or autostash over files this session did not write: publish this session's commits on top of the remote from a temporary clone, or stop and report the overlap. Before committing, read the project's commit rules: list the project root and read AGENTS.md, CLAUDE.md and any rules or notes file there (README, CONTRIBUTING, files named like *NOTES* or *RULES*); where a project or user rule differs from a harness default such as an attribution trailer, follow the project or user rule.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "'Waiting on user' is enough for the pending item." | Waiting for what, and what unblocks it? Write both or the item rolls over forever. |
| "I will commit everything in the vault." | Only this session's paths. Other sessions' changes are not yours to publish. |
| "Nothing to distil this time." | Say 'none' and why. The absence is information too. |

## Red flags

- A pending item without blocker.
- A publish that staged files you did not write.
- A handoff with no next_session value.

## Verification

- Pending items complete.
- Gate outputs in the reply.
- Published paths listed; push status truthful.
