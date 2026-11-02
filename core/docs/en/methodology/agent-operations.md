# Agent Operations

> Canonical: strata-kit `core/docs/en/methodology/agent-operations.md` (migrated 2026-10-29 from strata `docs/04-agents/agent-operations.md`, DEC-2026-10-29-11).

> The **third orthogonal axis** of Strata. Execution Mode (how the work is done) → Verification Tier (who verifies) → **Agent Operations (when, how much, and how it is digested)**.
> The definition of Verification Tier lives in `core/docs/en/methodology/verification-tier.md`, which is the source of truth.
> Covers: operating hours (night batch), budget (budget envelope), multi-session structure, and how a person digests the surging output (Decision Inbox + self-report validation gate).
> Status: `draft` (design agreed. §1 packet and §5 ledger CLI (`kb ledger`) are implemented. There is no automated tool for the output validation and the Decision Inbox gate of §2–4 — the old strata agent-ops.py has not been used since 2026-06 (DEC-2026-10-29-12). The actual agent runner is not implemented)

## 0. Why this is needed

Execution Mode and Verification Tier cover "how to do one task well".
Agent Operations covers the problem above that — **the operating discipline that keeps people from becoming a bottleneck or drowning when many agents run for a long time**.

The core premise (it runs through this whole axis):

> The goal is not to run many agents. The goal is to **strongly limit the unit of delivery, the roles, the outputs, and the surface a person has to look at**.
> Every device that increases output (multi-session, night batch) drowns the person unless there is a device that digests the output (Decision Inbox, validation gate).

Principles in brief:

1. A relay sends a **structured packet**, not the whole conversation.
2. Multi-session is run **Coordinator-centered (hub-and-spoke)**, not as an N:N conversation.
3. Night work is limited to a **budgeted batch**, not autonomy.
4. The person looks only at the **Decision Inbox**, not at raw output.
5. The labels the person sees are not self-reports but **labels re-judged by cross-verification**.

This document is the source of truth for the methodology primitives of the runtime family: **Relay Packet, Decision Inbox, review_gate, Shared Session Ledger**.
Adapters/runtimes such as the Quilt hub do not redefine these primitives; they consume them as routing, projection, and execution surfaces.

---

## 1. Relay Packet layers (fewer tokens + fewer errors)

Sending the whole conversation is forbidden. The goal is not to reduce the token count but to **raise the information density per token**.
(Cross-review procedure: `skills/strata.review/SKILL.md`; delivery is the Quilt hub's `hub_send`)

```text
Level 0: question only
Level 1: question + current conclusion + points of contention            ← default
Level 2: Level 1 + evidence files/lines + diff summary  ← default
Level 3: full text of the needed excerpts
Level 4: full transcript (exceptions only)
```

The default is Level 1–2. If you throw prose conversation over as it is, it becomes unclear what the other side should judge.
Recommended packet shape:

```yaml
intent: "review"
decision_so_far: "The canonical source of Verification Tier was split out to verification-tier.md"
open_questions:
  - "Do the Promotion Gate flow and the backlog schema boundary line up?"
evidence:
  - file: "core/docs/en/methodology/verification-tier.md"
  - file: "core/docs/en/methodology/task-spec-schema.md"
constraints:
  - "Do not put tool names in Core documents"
request:
  - "Point out only 1-2 gaps"
```

- **Attach the anchor**: over multiple round trips, attach `decision_so_far` (a fixed summary) every time so the other side does not forget the agreement and drift.
- **Block thin packets**: if `evidence`/`request` is empty, warn before sending — if an empty packet is sent, there is a risk that it looks Cross-Verified although no verification was performed. (Real case: a Reviewer that received an empty packet correctly returned "cannot review")

## 2. Multi-session (Model-A n · Model-B n)

It is possible, but letting sessions talk to each other N:N leads to token explosion, duplicated review, and unclear responsibility.
The default is **hub-and-spoke**.

```text
Coordinator
  ├─ ModelA-Review-1
  ├─ ModelA-Research-1
  ├─ ModelB-CodeReview-1
  ├─ ModelB-Impl-1
  └─ ModelB-Contrarian-1
```

Sessions are not allowed to talk to each other directly. All of them put their output in the relay queue and the **Coordinator gathers it**.

Forbidden structure:
```text
Model A1 ↔ Model B1 ↔ Model A2 ↔ Model B2 ...   (fan-out is easy, fan-in is hard)
```

Role separation:

| Role | Responsibility | Authority boundary |
|------|------|----------|
| Primary | Leads the work | — |
| Reviewer | Finds defects | Does not decide, only points out |
| Contrarian | Finds counter-arguments | Linked to adversarial verify |
| Summarizer | Compresses outputs | Must not change content |
| Archivist | Organizes decisions/backlog | **Only up to `open→triaged`. `accepted/rejected` is the person** |

> **Key point**: fan-out (multi-session) is easy and fan-in (synthesis) is hard. Without a convergence point (Coordinator or person), it worsens the §4 problem by itself.

Work tree (git worktree) rule (DEC-2026-09-17-01): even for parallel Workers and parallel sessions, a work tree is created **only if the user has accepted that proposal**. Auto mode is the same. The default is sequential execution on a single branch in the checkout the user is looking at; if a work tree is really needed, propose the necessity, the branch name, and the cleanup plan as one item and wait for the answer. When done, leave the branch, clean up the work tree, and report. The canonical rule is `core/docs/en/methodology/execution-modes.md` § Absolute rule 7.

### 2.1 Execution output schema

There is no runner yet that executes multi-session itself. The plan output the Coordinator receives follows the schema below, and review confirms **the ban on N:N links**, the role enum, and the Archivist authority boundary (there is no automated check tool now).

```yaml
multi_session:
  coordinator: "human"        # human | agent
  sessions:
    - id: "review-1"
      role: "reviewer"        # primary | reviewer | contrarian | summarizer | archivist
      tool: "codex"           # adapter label, not a Core enum
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      allowed_transitions: [] # archivist is allowed only ["open->triaged"]
```

Forbidden:
- `direct_peer_links`: a link where sessions talk to each other directly. Reject it when found.
- A transition in which the Archivist decides as far as `accepted/rejected/applied`.

## 3. Night batch protocol (22:00–08:00)

It is not autonomous work but a **budgeted batch**. To avoid breaking the "the person decides" principle, split it as **night = generate, day = judge**.

### Before 22:00 — the person prepares
```text
1. Select 3–5 work packets to process tonight
2. State the scope / prohibitions / budget / completion condition in each packet
3. Limit the allowed write scope (write_scope)
4. Define the stop conditions
```

### Night agent rules
```text
- No new architecture decisions
- No work that affects production
- No commit/deploy/delete (or separate approval)
- If ambiguous, stop and leave it as a question
- Each agent submits only a final one-page summary
- All outputs wait as needs_decision (no adoption before cross_verified)
```

### budget envelope + hard limits
```yaml
agent_budget:
  max_turns: 8
  max_files_read: 12
  max_output_lines: 80
  write_scope: ["assigned/paths/only"]
  stop_if:
    - "architecture decision required"
    - "test cannot run"
    - "scope expands beyond assigned files"
```

> **Safeguard priority**: hard limits (`max_turns`/`max_files`/`write_scope`) are **primary**. Self-judged stops (`stop_if: if ambiguous`) are **secondary** — because an agent that does not recognize ambiguity does not stop. The primary must always work.

### 08:00 — what the person looks at
```text
- Items needing a decision / files actually changed / test results / risks / outputs to discard / candidates for the next instruction
```

Manage tokens/time not by exact numbers but by a **per-session budget envelope + hourly pacing** (so the limit is not used up before dawn, leaving a gap).

### 3.1 Batch output schema

A night batch is fixed first as a **batch spec**, not as a runner. Before starting, confirm that packets exist and the
hard budget fields are present (there is no automated check tool now). Whatever the execution tool is, a night batch does not start without this spec.

```yaml
night_batch:
  window: "22:00-08:00"
  packets:
    - id: "nb-001"
      packet_ref: "$STRATA_VAULT/projects/{n}/relays/..."
      owner: "primary"
  budget:
    max_turns: 8
    max_files_read: 12
    max_output_lines: 80
    write_scope:
      - "assigned/paths/only"
    stop_if:
      - "architecture decision required"
      - "test cannot run"
```

Every night output is treated as `review_gate.required: true` at the §4 gate.

## 4. Decision Inbox + self-report validation gate (the core of this axis)

The person's bottleneck is not "reading" but "**judging**". Process agent output not as information but as a **judgeable unit**.
The surface the person looks at is **the Decision Inbox alone**. Raw output is only stored.

### 4.1 Enforced output format (self-report)
```yaml
result:
  status: completed | blocked | needs_decision | rejected
  one_line: "what was done"
  changed_files: []
  evidence: []          # pointer required (no long explanation without a decision)
  tests: []
  risks:
    - severity: high | medium | low
      summary: ""
      action_needed: ""
  decisions_needed: []
  discardable_notes_ref: "..."   # raw output is only stored here
```

### 4.2 Self-Report Validation Gate

**Problem**: the `status`/`risks` above are classified by the agent **itself**. If it underestimates its own risk (high→low), then the moment the person looks only at the Inbox, a misclassified item is buried and passes.
**Measured basis**: a self-report cannot be trusted — a model does not register an unsupported self-claim as fact, and when given evidence plus code it verifies and then accepts.

**Solution**: **before** entering the Decision Inbox, the relay (cross-verification) re-judges **only the triage labels**.

```text
What is verified:
  Re-reviewing the whole raw output ❌          (this would undo the §1 token saving)
  Re-judging status / risk / decisions_needed / evidence pointer ✅
```

Flow:
```text
Agent self-report
  → Relay reclassifies (labels only)
  → agree    → enters the Decision Inbox
  → disagree → promoted to "needs_human_decision" (to the person)
```

Preventing infinite loops:
```yaml
review_gate:
  required: true
  reviewer: cross_verified
  max_review_rounds: 1            # a Reviewer must not call a Reviewer again
  disagreement_policy: human_decision   # disagreement = promoted straight to the Inbox
```

### 4.3 Risk-based branching (do not re-judge everything)

Re-judging everything is expensive. Split it by risk.

**Re-judgment required:**
```text
- status: completed but files changed
- risk: high or unknown
- decisions_needed present
- related to architecture / schema / migration / deletion / security
- night batch outputs (all of them)
- methodology_backlog / decisions changes
```

**Sampling (or skip):**
```text
- low risk / document summaries / exploration results / work that only ran tests
```

### 4.4 Fallback when no re-judge exists (safe default)

`reviewer: cross_verified` presupposes a re-judge from a different model family.
**If there is no re-judge** (e.g. no cross session running at night), verification could not be done, so
the item is automatically classified as **`needs_human_decision`** — since it could not be verified, it is not let through but raised to the person.

### 4.5 What the person does every day (Agent Output Triage)
```text
1. Approve  2. Reject  3. Ask more questions  4. Discard
```
Rules: raw output is only stored, the person sees only the digest, the digest must have evidence pointers, no long text without a decision.

### 4.6 Schema example (task completion extension)
```yaml
triage:
  self_report:
    status: completed
    risk: low
    decisions_needed: []
  review_gate:
    required: true
    reviewer: cross_verified
    result: reclassified            # agreed | reclassified | no_reviewer
    final_status: needs_decision
    reason: "classified as low, but includes a schema change"
    max_review_rounds: 1
```

### 4.7 Gate judgment rules

There is no automated validation tool now (the old strata agent-ops.py has not been used since 2026-06, DEC-2026-10-29-12). The judgment rules below are applied by a person or the Builder when preparing reviews and the Decision Inbox.

Gate judgment:
- `completed` + changed files, `risk: high|unknown`, `decisions_needed`, architecture/schema/migration/security/decision signals, and night batch outputs get `review_gate.required: true`.
- If there is no reviewer, `result: no_reviewer`, `final_status: needs_decision`.
- `max_review_rounds` is always 1.
- If there are `changed_files`, an `evidence` pointer is required.

A Decision Inbox item is exposed only as one action of `approve | reject | question | discard`. Raw output is
stored in `discardable_notes_ref` and the Inbox holds only a pointer.

---

## 5. Shared Session Ledger

> The **single source of truth** that lets three workers (**user / primary / reviewer**) share one request flow and collaborate.
> Per-tool adapters map the `primary`/`reviewer` roles to actual tool sessions. The Core schema has no tool names as an enum.
> This file, not the reviewer session's memory, holds the context — it applies the first principle of Strata ("sessions are disposable, documents are persistent") to the relay.

### 5.1 Why a ledger (the higher-level answer to reviewer session management)

When a relay runs for a long time, "how do we keep the reviewer session alive" becomes the problem. But **if the unit of truth is the shared ledger rather than the reviewer session**, the problem goes away:

- The reviewer session **may be volatile** — the context stays in the ledger, not in the reviewer's memory.
- The next relay packet's `decision_so_far` / `evidence` / `open_questions` are **generated from the ledger**, not from the reviewer's memory (§1 packet).
- Whichever tool the user starts with, they read the same ledger and continue (regardless of tool or starting point).

> **However, the reviewer reset rule (around §1) is not discarded.** The ledger solves the *context retention* problem, but
> the **contamination** where the reviewer mixes **old agreements not in the packet** into its own judgment is a separate matter. The reset is kept, demoted from "for context retention" to
> **"contamination-prevention hygiene"** (the purpose differs, so it does not disappear when a ledger exists).

### 5.2 Location · format

```text
Location: $STRATA_VAULT/projects/{project}/sessions/session-{date}-{slug}.md
          (outside Core; persistent, shared, suited to indexing. .strata/local is machine-local state, so unsuitable)
Format: Markdown file + per-actor YAML block entries (human-readable and machine-indexable at once)
frontmatter required: session_id · project · status · actors · topic · created · next_session · nodes
          (nodes = the topic nodes this session belongs to — the §5.7 coverage gate derives them from changed files and compares)
actor: user | primary | reviewer | coordinator | archivist
tool: optional adapter label    (e.g. claude | codex — not a Core enum)
```

### 5.3 Entry schema

Each entry is a `## [actor] {ISO8601 timestamp}` header + a YAML block. Append-only, in time order.

```markdown
## [user] 2026-06-01T12:34:00+09:00
​```yaml
intent: "define shared ledger"
request: "Let Claude/Codex/User share the same request flow"
decision: null            # the user's decision / stop judgment (if any)
​```

## [primary] 2026-06-01T12:40:00+09:00
​```yaml
tool: "claude"                         # optional adapter label
from_user: "shared ledger proposal"     # what problem was received
action: "analyzed with a higher-level frame"        # how it was handled
to_reviewer:                        # summary of the packet sent to the reviewer (null if none)
  intent: "review"
  decision_so_far: "ledger is source of truth"
  questions: []
outcome: "accept | rebut | hold"         # how the reviewer's response was handled (if any)
​```

## [reviewer] 2026-06-01T12:45:00+09:00
​```yaml
tool: "codex"                          # optional adapter label
reviewed: "ledger proposal"          # what was reviewed
verdict: "agree | agree_with_caveat | disagree"
risks:
  - "single writer required"
returned: "the key opinion returned"
​```

## [primary] 2026-06-01T15:10:00+09:00
​```yaml
action: "restart signal — warning line passed | two failures on one hypothesis"
confirmed: ["confirmed fact (with what confirmed it)"]
assumed: ["assumption not yet confirmed"]
discarded: ["discarded hypothesis (with why)"]
​```

## next_session
​```yaml
next: "session-2026-06-01-qwer.md"   # enforced at close (null forbidden — prevents a broken chain)
reason: "why the flow is handed to the next session"
​```
```

The `[primary] 2026-06-01T15:10` entry above is a restart entry. When a restart signal (session-splitting 5.1) moves the work to a new session, it carries the same three fields as the handoff's facts-and-hypotheses section (confirmed, assumed, discarded).

### 5.4 Single writer + file lock (B3 — preventing concurrent-write contamination)

To avoid repeating, in the ledger, the session-file contamination we just measured (two processes appending to one file at the same time):

- Per-tool agent processes **do not write the ledger file directly.** They write only through the single entry CLI (`python3 "$STRATA_KIT/kb" ledger`).
- **Single CLI ≠ single concurrency**: the CLI must have a **file lock (flock)** inside. Even if several adapters call `append` almost simultaneously, they are serialized.
- The ledger is a **separate file** from the live TUI session files (`~/.claude/...`, `~/.codex/...`) — it is unrelated to TUI occupancy, so it is not a target of the lsof guard.

### 5.5 Append triggers (B1 — who leaves it, and when)

Entries are left not automatically but on **explicit triggers**:

```text
- Around a relay: a primary entry (to_reviewer) when a packet is sent, a reviewer entry (verdict) when the response is collected
- User decisions: a user entry (decision) when the user judges adopt/reject/stop
- End of work: write the next_session pointer at close (§5.6)
```

### 5.6 Session chaining (B2 — enforcing next_session)

When closing a ledger, you **must** fill `next_session.next`. Do not close with `null` —
if the chain breaks, the next worker cannot continue the flow (the same pattern as the handoff's "a pending item must have a blocker").
If there is no work to continue, state `next: "none"` + `reason` to record that it is an *intentional end*.

### 5.7 Coverage gate (at session end — did the code change but the shape not)

When a session closes, the session-end gate (the handoff generator and the ledger CLI's validate/close) checks the following **in the same place** as the uncommitted decision record warning:

```text
Input: the list of code files this session changed (task completion.files_modified/created, otherwise the repository diff)
① For each changed file, find the spec that owns that surface via covers (coverage resolver)
② Collect the owning specs' nodes and compare them with the nodes in the ledger / handoff frontmatter — if missing, warn to fill them in
③ If any owning spec was not updated in this session (updated is before the session start) and
   the frontmatter has no doc_change: none + doc_change_reason → warning + recorded as debt of that node
④ If any changed file has no owning spec → "unowned surface" warning (a spec must be created or covers extended)
```

- **It is a warning, not a block.** It is the same level as the uncommitted record warning. But if ignored, it remains on the node page's "debt" face for the next person to see.
- `doc_change: none` follows the same principle as `next: "none"` in §5.6 — no empty values, an explicit none + reason.
- The canonical source of debt is not the page but the very fact that "the session has no doc_change declaration". There are only two ways to pay off debt: update the spec (update updated·sources), or retroactively write the doc_change reason in that session's document.
- Value format: the "Node and coverage fields" section of `core/docs/en/knowledge-base/document-format.md`. It is a signal separate from the review policy (90 days).

`nodes` is included in the ledger frontmatter required fields (§5.2). The value is derived by the resolver in ②, and only sessions with no code change have a person pick it directly.

---

## 6. Relationship to the other axes

```text
②multi-session (fan-out) ┐
③night batch (generate)  ├→ ④Decision Inbox + validation gate (fan-in) ← without it ①②③ drown the person
①relay (density up)      ┘
⑤ledger ← the shared source of truth where every act of ①~④ is recorded (regardless of tool or starting point)
```

- **Execution Mode**: only references Agent Operations. (Mode judgment/transition is in `core/docs/en/methodology/execution-modes.md`)
- **Verification Tier**: the validation gate's `reviewer: cross_verified` uses the Cross-Verified Tier of `core/docs/en/methodology/verification-tier.md` as it is.
- **Methodology Feedback Loop**: the Archivist's `open→triaged` boundary follows the Promotion Gate and the backlog lifecycle of `core/docs/en/methodology/task-spec-schema.md`. The judgment (accepted) is the person's.
- **Cross review**: the §1 packet is produced by `skills/strata.review/SKILL.md` and sent to a reviewer in a fresh context (Quilt `hub_send`). The old Claude↔Codex relay tool (strata bridge) was a past implementation and is not used.

## 7. Adoption priority

```text
①relay packet structuring  → possible right away (clear gain, low risk)
④Decision Inbox + gate     → master key (the safeguard for ②③, design first)
⑤Shared Session Ledger     → before running the relay over many round trips (single writer + lock is the precondition)
②multi-session / ③night batch → after ④⑤ are designed (do them first and the person becomes the bottleneck / drowns)
```

The parts already exist: cross review (strata.review, the cross-verification filter) + the backlog lifecycle (judgment queue) + Verification Tier (trust gate). The fan-in guardrail (automatic validation of outputs) does not exist yet — the old agent-ops.py is not used. It is **assembly**, not invention.

## 8. Open items

- Measure the actual token cost of `review_gate` re-judgment (to verify the thin-gate assumption).
- Whether the Coordinator is an agent or the person doubles as one (depends on the multi-session scale).
- The multi-session runner and the night batch runner are not implemented. The current implementation goes only as far as validating plan/batch/self-report/Inbox outputs and gate normalization.
- Where to keep `discardable_notes_ref` (raw output) — the possibility of reusing vault relays/.
- `kb ledger` (formerly session-ledger.py) is implemented (append/read/close/validate + flock). Remaining refinement is in the cross-verification queue.
- The §5.7 coverage gate is implemented — wired into the handoff generator (pre-generation check + derived-node prefill) and the ledger CLI validate/close (warning), and node pages are regenerated after close·handoff. The ledger required field `nodes` is in its introduction period, so it is at **warning level** (promotion to error comes after the retroactive pass). Retroactive work on existing documents (nodes/covers) and per-project toc.yaml are not started (methodology-backlog MB-strata-2026-007).
- How to link the reviewer reset triggers (topic_change / max_rounds 3–5 / decision_accepted / packet_drift / high_risk) with ledger entries.
