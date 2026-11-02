# 02 — Session Splitting Guide

> Canonical: strata-kit `core/docs/en/methodology/session-splitting.md` (migrated 2026-10-29 from strata `docs/02-session-splitting.md`, DEC-2026-10-29-11).

> The Builder must consult this document before writing a work order.
> Splitting sessions is the most effective strategy for "preventing context loss".

## 1. Split decision matrix

### 1.1 Quantitative criteria

| Metric | Single session | 2-3 sessions | 4+ sessions |
|---|---|---|---|
| Changed files | ≤15 | 16-40 | 40+ |
| Affected layers | 1-2 | 3 | 4+ |
| Referenced files | ≤10 | 11-25 | 25+ |
| Expected conversation turns | ≤20 | 21-40 | 40+ |
| New domains | 1 | 2 | 3+ |
| Exploration steps needed | ≤2 | 3-4 | 5+ |

### 1.2 Qualitative criteria

**Situations that call for an immediate split:**
- "First investigate A, then decide on direction B based on the result" → exploration session + implementation session
- "Refactor the existing code and add a new feature at the same time" → refactoring session + feature session
- "Change the frontend and backend simultaneously" → FE session + BE session
- "Write the tests first, then verify after implementing" → TDD session (Writer/Reviewer pattern)

**Situations where a single session is enough:**
- Single-file bug fix
- Adding CRUD identical to an existing pattern
- Filling in tests
- Documentation update
- Configuration change

## 2. Split pattern catalog

### 2.1 Layer-Sequential

The most common pattern. Used when a new feature must be built up from the bottom.

```
Request: "Please implement the new Order domain"

Session 1: L1 + LM1 (foundation)
├── Define OrderEntity, OrderStatus enum, OrderType
├── MongoDB Document mapping
└── Set up inheritance from the common Audit Entity
    → Handoff: entities/types fixed, next is L2

Session 2: L2 DataLayer (data)
├── OrderCommandService (create, update, delete)
├── OrderQueryService (findById, findByStatus, search)
├── OrderRepository, OrderTemplate
└── Unit tests
    → Handoff: L2 complete, next is LM2 or L3

Session 3: L3 Composite (business)
├── OrderCompositionService
├── Payment integration logic (using PaymentCoordinator)
├── Inventory deduction logic (using InventoryCoordinator)
└── Integration tests
    → Handoff: L3 complete, next is Controller

Session 4: Route Controller (API)
├── OrderController (endpoint definitions)
├── Request/Response DTO
├── Validation setup
└── API documentation generation
```

### 2.2 Domain-Parallel

Used when several domains are worked on at the same layer at the same time.

```
Request: "Please implement L2 for the User, Order, and Product domains"

Session A: L2 — User domain (independent)
Session B: L2 — Order domain (independent)
Session C: L2 — Product domain (independent)

Precondition: L1 Component must be fixed beforehand
Precondition: there must be no L2 cross-references between domains (guaranteed by Strata rules)
```

### 2.3 Explore-Implement

Used for work whose direction is uncertain.

```
Request: "Find the slow parts and optimize them"

Session 1: Explore
├── Analyze code and identify bottlenecks
├── Interpret profiling results
├── Derive 3 optimization strategies
└── Record the exploration results in $STRATA_VAULT/projects/{name}/sessions/ (Tier V)
    → Handoff: optimization strategy fixed, detailed implementation plan

Session 2-N: Implement
├── Code changes following the fixed strategy
├── Performance tests
└── Record results
```

### 2.4 TDD split (Writer/Reviewer)

The Writer/Reviewer pattern that Anthropic recommends.

> **Relation to the verification axis:** this Writer/Reviewer pattern is **one example** of implementing the **Verification Tier**
> (Self-Verified / Cross-Verified) of `core/docs/en/methodology/verification-tier.md` through session splitting.
> The Tier definition is owned by `core/docs/en/methodology/verification-tier.md` as the source of truth, and is not duplicated here.
> - If the Reviewer is from the same tool family → **Self-Verified**
> - If from a different model family → **Cross-Verified** (implementation: `skills/strata.review/SKILL.md`)

```
Session 1: Write tests (Writer)
├── Write test cases based on the requirements
├── Confirm that all tests fail
└── Commit the test files

Session 2: Implement (Writer)
├── Write code that makes the Session 1 tests pass
├── Confirm that all tests pass
└── Commit the implementation code

Session 3 (optional): Review (Reviewer)
├── Review the code in a fresh context
├── Verify that the Session 2 code follows the layer rules
└── Suggest refactoring
```

### 2.5 Frontend-Backend

```
Request: "Please implement both the UI and the API for the order feature"

Session BE: Backend
├── Implement L2-L3-Controller
├── Fix the API spec document ($STRATA_VAULT/projects/{name}/tasks/.../api-specs/order.yaml, Tier V)
└── Handoff: API endpoints + DTO fixed

Session FE: Frontend
├── Reference the API spec (Contract) — the precondition is **the Contract being fixed**, not BE being complete. It can start earlier with a mock transport
├── Contract/DataState/Feature order matched to the Frontend variant
├── Declare entry_point (design_first | dev_first | spec_first | change) — the order is not fixed and the consistency check is the gate (core/docs/en/architecture/frontend-design-contract.md)
└── API integration tests + Impl↔Design consistency check (design_sync)
```

The BE session and the FE session can run in parallel once the Contract is fixed. `dev_first`, where FE goes first, is also allowed — in that case the Contract is a deliverable of the FE session and the BE session verifies it.

## 3. Task Specification format

The document the Builder writes for each session:

```yaml
# $STRATA_VAULT/projects/{name}/tasks/{date}/{nn}-{title}/task-{id}.yaml
task:
  id: "ORD-L2-001"
  title: "Implement Order L2 DataLayer"
  session_type: "implement"      # explore | implement | review | refactor
  estimated_turns: 15
  estimated_files: 8

scope:
  layer: "L2_DataLayer"
  domain: "order"
  directories:
    - "src/data/order/"
    - "test/data/order/"
  
constraints:
  layer_rule: "@core/rules/layer-rules.yaml#L2_DataLayer"
  naming_rule: "@core/rules/naming-convention.yaml#backend.L2"
  can_reference:
    - "L1_Component"
    - "LM1_Inherite"
  cannot_reference:
    - "L2_DataLayer (other domains)"
    - "LM2_Coordinate"
    - "L3_Composite"

inputs:
  prior_session: "ORD-L1-001"    # previous session ID (null if none)
  entities:
    - "@src/components/order/OrderEntity.ts"
    - "@src/components/order/OrderStatus.ts"
  reference_implementation:
    - "@src/data/user/UserCommandService.ts"  # pattern reference

deliverables:
  files:
    - path: "src/data/order/OrderCommandService.ts"
      description: "CUD transaction service"
    - path: "src/data/order/OrderQueryService.ts"
      description: "Read-only query service"
    - path: "src/data/order/OrderRepository.ts"
      description: "MongoDB Repository implementation"
    - path: "test/data/order/OrderCommandService.test.ts"
      description: "CommandService unit tests"
    - path: "test/data/order/OrderQueryService.test.ts"
      description: "QueryService unit tests"

acceptance_criteria:
  - "All unit tests pass"
  - "No layer dependency violations (Hook check passes)"
  - "Naming conventions followed"
  - "One method manages only one entity"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000       # token limit for reference files
  compaction_strategy: "file-based"  # decisions go in files, keep the context light
```

## 4. The Builder's split proposal protocol

The analysis procedure the Builder performs on receiving a user request:

```
User: "Implement the whole order management feature"

Builder analysis:
┌─────────────────────────────────────────┐
│ 📋 Work scope analysis                   │
│                                          │
│ Affected layers: L1, L2, LM2, L3, Route (5) │
│ Expected changed files: ~35              │
│ Expected referenced files: ~15           │
│ Expected conversation turns: ~60         │
│                                          │
│ ⚠ Verdict: session split needed (4 sessions recommended) │
│                                          │
│ Proposal:                                │
│ Session 1: L1 entities/types (15 min, ~8 turns)   │
│ Session 2: L2 DataLayer (30 min, ~15 turns)       │
│ Session 3: L3 Composite (30 min, ~15 turns)       │
│ Session 4: Controller + API (20 min, ~12 turns)   │
│                                          │
│ Parallelizable: split Session 2 by subdomain │
│ Dependency chain: S1 → S2 → S3 → S4     │
└─────────────────────────────────────────┘
```

The Builder **shows this analysis to the user first and gets approval** before generating the work orders.

## 5. Session-end signals

The moments when the Builder should end the current session and hand off:

| Signal | Response |
|---|---|
| More than 15 conversation turns | Hand off after finishing the current unit of work |
| Compaction occurs | Save state immediately; hand off after finishing the current unit if possible |
| Having to re-explain "as I mentioned before..." | A sign of context loss — prepare the handoff immediately |
| Work crossing a layer boundary begins | Finish the current layer, then move to the next session |
| Change of direction based on exploration results | Document the exploration results; implementation goes in a new session |
| The user changes the requirements | Document the changes, re-analyze, then make a new plan |
| The conversation passes the warning line (about 400,000 tokens by default) | Finish the unit at hand, hand off at the next task boundary (with the facts-and-hypotheses section), new session; at the latest before the limit (about 600,000 by default) — 5.1 |
| Attempts on one hypothesis are blocked twice | Do not look for a third workaround; stop and report the measured facts and the options — 5.1 |

### 5.1 Restart signals: the token warning line and two failures on one hypothesis

Neither signal means cutting the work off where it stands. Both mean finishing the unit at hand and splitting at the next task boundary (card `rec.session.split-at-task-boundary`). Compaction fires when the window is nearly full, so the larger the window the later it steps in, and a conversation stuck on one hypothesis clouds judgement whatever its length. The two signals catch these two cases.

**The token warning line and limit.** When the conversation passes about 400,000 tokens, finish the unit, write the handoff at the next task boundary and move to a new session. Even if the next boundary is far off, move before about 600,000 tokens. Both values are fixed token counts, not ratios of the window (DEC-2026-10-31-09; values DEC-2026-10-31-33). They are starting values meant to wrap a session up well before compaction when a 1M window is the default; there is no measurement from our own work behind them yet. Change them with `session.restart_tokens` and `session.restart_limit` in the user config `~/.strata/config.yaml`; the start header's `restart signal` line shows the current values. In Claude Code the current size shows in the `/context` command or the status line. When the agent cannot read it, the person tells it.

**Two failures on one hypothesis.** When attempts are blocked twice, do not look for a third workaround — stop and report the measured facts and the options. One hypothesis means one presumed cause: fixes in different places are the same hypothesis when they rest on the same "the cause is X". A failure means the symptom being checked (the same failing test, the same error) is still there. After the report the person sets the direction, or the handoff records the discarded hypothesis and a new session looks again.

**The facts-and-hypotheses section of the handoff.** A session that ends on a restart signal fills the handoff's facts-and-hypotheses section with confirmed facts (with what confirmed them), assumptions not yet confirmed, and discarded hypotheses (with why) (DEC-2026-10-31-11). The next session reads this section first and does not pick a discarded hypothesis up again. A session that works through the ledger writes the same three fields in its restart entry (agent-operations 5.3).

### 5.2 Conversation token budget and when compaction fires

| Window | Default auto-compaction | With `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=80` | Against the 400,000 warning line and 600,000 limit |
|---|---|---|---|
| 200,000 tokens | 200,000 (the window limit) | 160,000 | Compaction comes first; in this window the compaction signal does the warning line's job |
| 1,000,000 tokens | about 967,000 | about 770,000–800,000 | The warning line and the limit come before compaction |

The fixed cost is the harness system prompt, the tool definitions, the guidance, the start header and memory. What strata-kit adds (guidance and header) is about 8–12 KB, roughly 3,000–5,000 tokens (`wizard verify`); the rest depends on the harness and the number of connected MCP servers, so read it with `/context`.

The default compaction points come from the Claude Code documentation (model-config). The auto-compact window (the `autoCompactWindow` setting, the `/autocompact` command, the `CLAUDE_CODE_AUTO_COMPACT_WINDOW` environment variable, 100,000 to 1,000,000) is the fill level at which compaction fires, and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` is a percentage of that window that can only bring compaction forward. The environment variable reads suffixes such as `500k` only from v2.1.304. In a large window compaction comes long after the warning line, so wrapping sessions up is the job of the warning line and the limit, not of compaction. Whether to change the compaction settings is the user's call.

## 6. How the /split-session command works

The procedure the Builder performs when the user runs `/split-session`:

```
1. Analyze the scope of the current request
2. Apply the split matrix (see section 1)
3. Propose the split plan to the user
4. On approval:
   a. Create task-{id}.yaml for each session
   b. Update TASK_TRACKER.md
   c. State the dependency order
   d. Start the first session immediately, or save only the overall plan
```
