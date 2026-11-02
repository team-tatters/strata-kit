# Execution Modes

> Canonical: strata-kit `core/docs/en/methodology/execution-modes.md` (migrated 2026-10-29 from strata `docs/04-agents/execution-modes.md`, DEC-2026-10-29-11).

> Defines the dual execution modes of the Strata methodology.
> Every session must declare its execution mode explicitly at the start.

## Principles

- **The default is Task Mode** — if nothing is declared, the session is treated as Task Mode
- **Verbal Mode is a deliberate exception** — it can be used only when explicitly chosen
- **Mode switching is one-way** — Verbal → Task is allowed, Task → Verbal is forbidden

> **Mapping to work modes (2026-10-29, DEC-2026-10-29-15·19)**: the four work modes of the entry skill (using-strata step 4) split these two modes. Verbal = read-only (investigation, questions, review) + a single-session change that finishes without a task file; Task = multi-session (work with an order) + orchestration (several sessions or roles in parallel). The duties a session carries (active file, handoff, order) are set by the work mode; the quantitative criteria below are used to judge whether the work can finish as Verbal.
- **Summarize and confirm before changing state** — for work that is hard to undo or changes observable state (editing files, injecting into a session, calling an external CLI, commit/deploy), present a summary of what will be done first and run it only after the user confirms

## Mode definitions

### Task Mode (default)

The mode in which the Builder writes the `_order.yaml` + `task-{nn}.yaml` specifications and the Worker executes on the basis of those specifications.

**When it applies:**
- Sprint-level execution plans
- Multi-session feature implementation
- Changes to 3 or more files
- Impact on 2 or more layers
- Establishing a new architecture pattern

**Obligations:**
- Write `_order.yaml` (the work order)
- Write each `task-{nn}.yaml` (the Worker execution specification)
- Update TASK_TRACKER.md
- Write the handoff document
- Feed architecture decisions back to the KB

### Verbal Mode (exception)

The mode in which the Builder executes directly, or handles work quickly through spoken instructions.

**When it applies:**
- Ideation, exploration, design review
- Single-file edits
- Bug hotfixes (urgent)
- Document edits, configuration changes
- Work that can be finished within 10 turns

**Obligations:**
- No task specification needed
- No TASK_TRACKER update needed
- Handoff is optional (record it if there are decisions)
- **Recording a decision record (decision writer CLI) when a decision occurs cannot be waived** (an absolute rule regardless of mode — `decisions.yaml` is a generated index, never edit it by hand)

## Mode selection criteria (quantitative)

```
IF (modified files ≤ 3) AND (affected layers ≤ 1) AND (expected turns ≤ 10)
   AND (new domains = 0) AND (exploration phases ≤ 1):
    → Verbal Mode allowed
ELSE:
    → Task Mode enforced
```

| Metric            | Verbal allowed | Task enforced |
| ----------------- | -------------- | ------------- |
| Modified files    | ≤ 3            | 4+            |
| Affected layers   | 1              | 2+            |
| Expected turns    | ≤ 10           | 11+           |
| New domains       | 0              | 1+            |
| Exploration phases | ≤ 1           | 2+            |

**Verbal is allowed only when every condition is within the Verbal range. If even one is exceeded, Task is enforced.**

## Mode declaration

At session start, record the mode in this session's file `.strata/local/active/{session}.yaml`, and put the harness session id (Claude Code: `CLAUDE_CODE_SESSION_ID`) in `harness_session_id` — the start header and the compaction restore find this session's file by that field or by the file name:

```yaml
harness_session_id: "9496c8b3-…"   # CLAUDE_CODE_SESSION_ID
session:
  date: "2026-04-23"
  mode: "verbal"              # verbal | task
  declared_scope: "Review of debounce design and briefing"
  escalation_threshold: 3     # switch to task mode when more files than this are touched
  order_ref: null              # path to _order.yaml when in task mode
```

## Mode switch (Verbal → Task)

When a session started as Verbal but its scope has grown:

1. Detect it in the Builder's 5-turn self-diagnosis (check the number of files and layers)
2. Report "Task Mode switch needed" to the user
3. Write `_order.yaml` — include the `escalated_from: "verbal"` field
4. Record work already completed in the `completed_before_spec` section of `_order.yaml`
5. Proceed with the remaining work on the basis of task specifications

```yaml
# _order.yaml (at switch time)
order:
  id: "2026.04.23-01"
  title: "Debounce MongoDB synchronization"
  escalated_from: "verbal"
  completed_before_spec:
    - "Added the SET operation to CacheGenericOperator (completed in the verbal phase)"
  tasks:
    - id: "task-01"
      title: "Implement DirtyMarkService"
      # ... later tasks have normal specifications
```

## Model allocation strategy

Worker tasks state the **reasoning tier** they run at. Write a tier, not a concrete model name; the tool adapter owns the tier → model mapping (tool-neutral).

### Allocation criteria by reasoning tier

| Tier | Allocation criteria | Relative cost | Typical work |
|------|---------------------|---------------|--------------|
| **deep** (high reasoning) | Establishing a new pattern, cross-layer reasoning, complex refactoring | High | Architecture design + implementation, new systems |
| **standard** | Following an existing pattern, single-layer CRUD, tests, documentation | Low | REST Docs, adding a QueryService, KB documents |
| **light** | Document search, rule lookup, simple summaries | Lowest | KB search, handoff summaries |

> **The tier → model mapping is the responsibility of the tool adapter, not of Core.** (Adapter example — Claude: `deep→Opus`, `standard→Sonnet`, `light→Haiku`. This mapping belongs to the adapter context and is not a Core rule.)

### Model selection decision tree

```
Does the task follow an existing pattern?
  ├─ YES → Is there a clear reference implementation?
  │         ├─ YES → standard
  │         └─ NO  → deep (the pattern must be interpreted)
  └─ NO  → Does it need a new architecture judgment?
            ├─ YES → deep
            └─ NO  → standard (plain new code)
```

### Stating the tier in a task specification

```yaml
execution:
  model_tier: "standard"
  model_reason: "Follows the existing REST Docs pattern, no new judgment needed"
```

`model_reason` is required. The Builder must state the basis for the model choice so that the next session can apply the same criteria.

## Default reasoning tier per agent

| Agent | Default tier | Changeable |
|-------|--------------|------------|
| Builder | deep | No (orchestration always needs high-level reasoning) |
| Worker | Set per task | Yes (deep or standard) |
| Supporter | light/standard | Yes (light for search, standard for summaries) |

> A concrete model is mapped to the tier by the tool adapter (see the "tier → model mapping" note above). Core specifies only the tier.

## Verification axis (Verification Tier)

The verification axis is orthogonal to the execution mode. The execution mode covers *how the work is done*; the verification axis covers *who verifies the result*.
The enum values are `solo | self_verified | cross_verified`.
The definitions, the defaults, and the range in which `cross_verified` is required when changing a Core source of truth (SoT) are governed by `core/docs/en/methodology/verification-tier.md`, which is the source of truth.
Cross-Verified review is done with `skills/strata.review/SKILL.md` (it sends a review packet once to a reviewer in a fresh context).

## Methodology Feedback Loop

Methodology gaps that a Worker/Reviewer finds are reported as `methodology_signals`, and the Builder files them in the backlog and promotes them.
The flow and the Promotion Gate are governed by the "Promotion Gate" section of `core/docs/en/methodology/task-spec-schema.md`, which is the source of truth.
The field schemas of `methodology_signals` and `methodology-backlog.yaml` are defined in `core/docs/en/methodology/task-spec-schema.md`.

## Operations axis (Agent Operations)

On top of the execution mode and the verification axis, the operating discipline for running agents **in numbers and for long periods** is treated as a separate axis:
multi-session (hub-and-spoke), overnight batch (budgeted batch), Decision Inbox, and the self-reported verification gate.
→ `core/docs/en/methodology/agent-operations.md` (this document only references it; the rules are defined there)

## Absolute rules (regardless of mode)

> **This section is not the canonical source** (DEC-2026-10-29-19). Which rules apply to a project is decided by the constitution (the articles in `core/constitution/constitution.yaml`) and the cards the project adopted (`must_cards` in `.strata/kit/registry.yaml`, written by the wizard), and the generated guidance (AGENTS.md) carries that set. The canonical wording of each rule is the card in `core/cards/`.
> This section keeps the original text those cards came from and its grounds (incidents and reasons). From constitution 1.2.0, rules 5 and 7 are not articles but adopted must cards that apply only when the project adopts them. To change a rule, edit the cards and the constitution (with a decision record); do not edit this section.

Original text (2026-09-30, the list applied to every session at the time of DEC-2026-09-30-02):

1. **Present a summary of what will be done and get user confirmation before changing state**
   - Scope: editing files, injecting session files/relays, calling external CLIs, commit/deploy/delete, long-running jobs, and work that affects cost, permissions, or data
   - The summary includes the purpose, the work to be run, the scope of change/impact, the verification method, and the rollback/abort conditions
   - Investigation that does not change state, such as plain lookups, searches, and file reads, is allowed as an exception
   - **semantic vs mechanical**: a semantic change that alters meaning, rules, or contracts requires approval. A meaning-preserving mechanical change (typo, link, format) is a candidate for automatic permission **only when it can be proven statically**. If it is ambiguous, treat it as needing approval. An LLM's own "mechanical" judgment is not used as grounds for automatic permission
2. **Record a decision record immediately when an architecture decision occurs** (decision writer CLI — the index and the vault DEC note are regenerated automatically)
3. **No layer violations** — how strongly the harness blocks them is set by the project's enforcement grade (DEC-2026-10-29-17). Whatever the grade, the agent writes no new violation
4. **Follow the naming conventions** — a hook warns
5. **Use Soft Delete only** — adopted (constitution 1.2.0, DEC-2026-10-29-14): applies when a project with a data store adopts it
6. **Keep session state, work in progress, and handoffs in files, not in the conversation context** — applies to sessions that change state; a read-only session has no state to leave (DEC-2026-10-29-15) — when a session is interrupted, record the current state in this session's `.strata/local/active/{session}.yaml` (the single `active-task.yaml` is the earlier form, read only when no per-session file exists), and keep handoffs and work history in the vault
7. **Create a work tree (git worktree) only with the user's consent** (DEC-2026-09-17-01) — adopted (constitution 1.2.0): applies when it is in the user's default adoption list or the project adopts it
   - This holds in auto mode too. Both the tool adapter's work-tree isolation (for example the Claude Code Agent tool `isolation: "worktree"` and `EnterWorktree`) and `git worktree add` are covered
   - The default is to work sequentially on a single branch in the checkout the user sees. Even with several Workers, run them in order in the same checkout
   - Only when a work tree is truly needed for parallel sessions or parallel Workers, propose the need, the branch name, and the cleanup plan as one item, and create it only if it is accepted. One acceptance is valid only for that proposal
   - A work tree created with consent is cleaned up when the task ends, leaving the branch, and the location and branch are reported
   - Reason: splitting work into work trees stops review and inspection of what the agent wrote from working properly, the user cannot check the changes and the work history directly, and tracking the shape of the code becomes hard
8. **A deploy made to confirm an assumption is limited to environments that only a deploy can reproduce** (DEC-2026-09-18-01, strata)
   - Do not use a deploy to confirm an assumption that code reading, logs, unit tests, or a local run can confirm. Putting something on a shared environment (dev, stage) is only for confirming a phenomenon that reproduces only in that environment (infrastructure, routing, integration with other services, real data)
   - Before a deploy, report what you intend to confirm, separate confirmed facts from assumptions, and include how to roll back (a revert commit, the previous image)
   - A change that affects another line or other users, such as authentication, routing, or sessions, goes up only after it is measured with that line's user flows (for example, both the 2.0 login and the 3.0 login)
   - Reason: on 2026-09-18, a gateway route was promoted on stage on an assumption alone and the 2.0 login broke, and deploys that fixed the assumption and went up again were repeated several times in one day. A deploy also takes time to roll back and blocks other people's work
9. **Write both the blocker and the unblocked_by condition for a pending item in a handoff**
   - Writing only "waiting" is forbidden. If the next session does not know what is being waited for, the pending item is only carried over
