# Task Specification Schema

> Canonical: strata-kit `core/docs/en/methodology/task-spec-schema.md` (migrated 2026-10-29 from strata `docs/04-agents/task-spec-schema.md`, DEC-2026-10-29-11).

> Defines the structure of the task specification that the Builder produces and the Worker consumes.
> A task specification is **self-contained** — the Worker must be able to finish the code from the specification alone.

## Storage location

```
$STRATA_VAULT/projects/{project-name}/tasks/
  {yyyy.mm.dd}/
    {nn}-{short-kebab-title}/      # Work Order folder
      _order.yaml                   # work order (created by the Builder)
      task-{nn}-{title}.yaml        # Worker execution specification
```

### Why this location

- `$STRATA_VAULT` — does not touch the project repository (separate repo)
- `tasks/` — kept apart from KB documents (knowledge-base/), not a search index target
- `{yyyy.mm.dd}/` — tracking follows the flow of time, minimal cognitive load
- `{nn}-{title}/` — tells apart several work orders on the same day by sequence plus title

### Naming rules

| Element | Format | Example |
| ------------- | ------------------------------ | ------------------------------- |
| Date folder | `yyyy.mm.dd` | `2026.04.23` |
| Work Order folder | `{nn}-{kebab-title}` | `01-debounce-mongo-sync` |
| Work order | `_order.yaml` | Always fixed (underscore = sorts first) |
| Task file | `task-{nn}-{kebab-title}.yaml` | `task-01-redis-dirty-mark.yaml` |

### Sequence number rules

- Number of existing entries in that date folder + 1
- Numbers can collide when several machines work at once → **the title is the real identifier**
- A number collision only affects sorting, with no functional problem

---

## _order.yaml — work order

The manifest the Builder creates after splitting the tasks.

### Required fields

```yaml
order:
  id: "2026.04.23-01"                # {date}-{sequence}
  title: "Optimize MongoDB sync with Redis debounce"
  date: "2026-04-23"
  mode: "task"                        # task | verbal (escalated)
  project: "shop-api"

  goal: |
    State the purpose and background of the work.
    Why this work is needed and what state it must reach when complete.

  context:
    prior_session: "session-2026-04-22-01"    # reference to the previous handoff
    prior_decisions:                           # existing decisions that affect this work
      - "PostProcessJob uses polling (@Scheduled fixedDelay=5000)"
    blocker_resolved: "PostProcessJob system implemented (4/21)"
    kb_references:                             # related KB documents
      - "$STRATA_VAULT/projects/shop-api/knowledge-base/03-orders/checkout.md"

  tasks:
    - id: "task-01"
      title: "Add SET operations to CacheGenericOperator"
      model_tier: "standard"
      layer: "L2_DataLayer"
      depends_on: []

    - id: "task-02"
      title: "Implement DirtyMarkService"
      model_tier: "standard"
      layer: "L3_Composite"
      depends_on: ["task-01"]

    - id: "task-03"
      title: "Switch DataUpsertListener to debounce"
      model_tier: "deep"
      layer: "L3_Composite"
      depends_on: ["task-01", "task-02"]

  acceptance:
    - "Switch from the existing immediate-processing flow to the dirty-mark flow is complete"
    - "All unit tests pass"
    - "0 layer violations"

  status: "open"                       # drafting | open | in_progress | completed | cancelled
  completed_tasks: []                  # list of completed task ids
```

### Optional fields

```yaml
  escalated_from: "verbal"             # when converting verbal → task
  completed_before_spec:               # items completed verbally before the conversion
    - "Add SET operations to CacheGenericOperator"
  
  estimated_sessions: 1                # expected number of sessions
  priority: "high"                     # high | medium | low
  deadline: "2026-04-25"              # absolute date

  verification_tier: "self_verified"  # solo | self_verified | cross_verified (enum values)
                                      #   When omitted, verbal = solo. Task Mode should state it explicitly.
                                      #   Details: core/docs/en/methodology/verification-tier.md
  entry_point: "change"               # design_first | dev_first | spec_first | change — entry point of the deliverables (Spec, Design, Impl).
                                      #   Does not fix the order. The consistency check is the gate. Details: core/docs/en/architecture/frontend-design-contract.md
  design_verified: "self"             # none | self | designer | cross — independence of the design consistency check (core/docs/en/methodology/verification-tier.md).
                                      #   none unless it is UI work.
  methodology_feedback:               # methodology feedback loop (optional)
    enabled: true
    backlog_ref: "$STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml"
```

> **However, for work that changes the Core source of truth** (layer-rules / naming-convention / task-spec-schema / agent-roles),
> `verification_tier: cross_verified` is **required** (`core/docs/en/methodology/verification-tier.md`).
> Only in this case is verification_tier treated as a required field rather than an optional one.

### status lifecycle

```
drafting → open → in_progress → completed
                              → cancelled
```

| Status | Meaning | Transition condition |
|------|------|----------|
| `drafting` | The Builder is splitting tasks | The Builder starts writing _order.yaml |
| `open` | Work order confirmed, the Worker can run | All task specifications are written |
| `in_progress` | Some tasks are running | The first Worker run starts |
| `completed` | All tasks complete | All acceptance criteria are met |
| `cancelled` | Cancelled | An explicit cancellation decision |

A work order in `drafting` state is either completed or discarded by the Builder in the next session.

---

## _order.md — new format for the work order (2026-08-19, DEC-2026-08-19-03)

New orders are written as `_order.md` — the **YAML frontmatter is the order itself** (the schema is identical to `_order.yaml` above),
and the body is minimal markdown so the order joins the Obsidian link graph.

```markdown
---
order:
  id: "2026.08.20-01"
  # ... (_order.yaml schema as is)
---

# {order title}

- Design: [[design-doc]]
- Decisions: [[DEC-YYYY-MM-DD-NN]]
```

- Only the frontmatter is machine-parsed — scripts that consume orders support both `_order.yaml` and `_order.md` (frontmatter).
- The body must keep `[[wikilink]]`s to the design document and the related DECs (spine (handoff links: orders, kb_updates, decisions_made) edges — session→order→design+DEC).
- Existing `_order.yaml` files are not converted retroactively. `task-{nn}.yaml` stays yaml (the order note handles joining the graph).

---

## task-{nn}.yaml — Worker execution specification

The self-contained task document the Worker receives.

### Full schema

```yaml
task:
  id: "2026.04.23-01/task-01"          # {order-id}/{task-id}
  title: "Add SET operations to CacheGenericOperator"
  order_ref: "_order.yaml"             # reference to the parent work order

execution:
  model_tier: "standard"               # deep | standard | light (the tool adapter maps model names)
  model_reason: "Follows the existing CacheGenericOperator pattern"
  estimated_turns: 8
  estimated_files: 2

scope:
  layer: "L2_DataLayer"
  module: "domain:common-cache"
  nodes: ["common.cache"]                         # topic nodes this task belongs to — the coverage resolver derives them from directories
  can_reference: ["L1_Component"]
  cannot_reference: ["L3_Composite", "Route_Controller"]
  constraints:                                    # domain constraints extracted from ADRs
    - id: "CC-NNN-NN"
      rule: "{one-line rule for the constraint that applies to this scope}"
  docs_to_update:                                 # specifications that own directories·module through covers — injected by the coverage resolver
    - node: "common.cache"
      doc: "[[kb-shop-api-common-cache-spec]]"
      reason: "covers.paths match — adding SET operations changes the specification's operation list"
  directories:
    - "domain/common-cache/src/main/kotlin/com/example/domain/common_cache/components/"

inputs:
  reference_files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      reason: "Reference the existing pattern — how ReactiveRedisOperations is used"
    - path: "docs/architecture/layer-rules.yaml#L2_DataLayer"
      reason: "Check the layer rules"

  requirements: |
    Detailed specification of what to implement.
    - Method signatures
    - Behavior description
    - Constraints

  conventions: |
    Summary of the conventions to apply (so the Worker does not need to read separate files).
    - PAL markers required (@pal-port, @pal-layer, @pal-domain, @Comment)
    - Naming: {Domain}{ServiceType}

  design_ref:                          # Required for a task that builds UI. Pointer to the design deliverable (core/docs/en/architecture/frontend-design-contract.md)
    kind: "figma"                      # figma | storybook | claude_design | none
    ref: "file/abc?node-id=12:34"      # file, node, story id, or canvas URL
    version: "2026-04-23"              # tool version or snapshot date — baseline for the consistency check
    reason: null                       # required when kind: none (e.g. "text-only admin screen")

deliverables:
  files:
    - path: "domain/common-cache/.../CacheGenericOperator.kt"
      action: "modify"                  # create | modify | create_or_modify
      description: "Add 4 SET operation methods"
    - path: "domain/common-cache/.../CacheGenericOperatorTest.kt"
      action: "create_or_modify"
      description: "Unit tests for SET operations"

acceptance_criteria:
  - "addToSet, popFromSet, getSetSize, getSetMembers implemented"
  - "No change to existing method signatures"
  - "Unit tests pass"
  - "No layer violations"

context_budget:
  max_reference_files: 5
  max_loaded_tokens: 20000
  compaction_strategy: "file-based"

status: "pending"                       # pending | in_progress | completed | blocked
completion: null                        # filled in by the Worker on completion (see below)
```

**`scope.nodes` and `scope.docs_to_update`** — the Builder injects the specifications that own the code surface the task changes (frontmatter `covers`) and those specifications' topic nodes. The principle is the same as `scope.constraints`. The Worker does not run the resolver; it only reads the injected values.
- For a surface with no owning specification (a new feature), either include creating the specification in `deliverables.files`, or write `docs_to_update: []` and state the reason for the intentional emptiness in `inputs.requirements`. An empty array without a reason triggers a validation warning.
- The source of truth for the value format is the "Node and coverage fields" section of core/docs/en/knowledge-base/document-format.md.

### completion section (filled in by the Worker — except `triage.review_gate`)

The Worker fills in `completion.self_report` and the list of deliverables, but **`triage.review_gate` is filled in
by the independent re-judge (reviewer/relay)** — the premise of the self-report verification gate (agent ≠ re-judge,
`core/docs/en/methodology/agent-operations.md` §4) means the gate is neutralized if the Worker fills it in itself.

```yaml
completion:
  status: "completed"                   # completed | blocked | partial
  completed_at: "2026-04-23T14:30:00+09:00"
  files_created:
    - "domain/common-cache/.../CacheGenericOperatorTest.kt"
  files_modified:
    - "domain/common-cache/.../CacheGenericOperator.kt"
  tests:
    total: 4
    passed: 4
    failed: 0
  layer_violations: 0
  naming_violations: 0
  constraint_compliance:                # compliance result for each item in scope.constraints
    - id: "CC-NNN-NN"
      met: true
      note: "{basis for compliance or anything unusual}"
  design_sync: "aligned"                # aligned | stale | waived | none — Impl↔Design consistency (required if inputs.design_ref exists)
  design_sync_reason: ""                # required if waived: reason + until YYYY-MM-DD. If stale, completion cannot be declared
  doc_change: "updated"                 # updated | none — result of handling scope.docs_to_update (same key as the session frontmatter)
  doc_change_reason: ""                 # required if none (e.g. "refactoring only — no change to external contract or policy")
  docs_updated:                         # if updated, the documents updated (add this task to the updated stamp and sources)
    - "[[kb-shop-api-common-cache-spec]]"
  notes: "Nothing unusual"
  methodology_signals:                  # optional — methodology improvement signals (a list; [] or omitted if none)
    - type: "incomplete_spec"           # incomplete_spec | scope_issue | constraint_conflict | rule_gap | drift | design_drift
                                        #   design_drift: a value outside the alias or a contract (axis, state) mismatch was found → candidate to improve the token/design contract
      severity: "minor"                 # minor | major | blocking
      scope: "methodology"              # project | methodology
      affected_core:                    # at least 1 required when scope: methodology
        - "core/docs/en/methodology/task-spec-schema.md"
      summary: "The task specification has no test command field, so the completion verification criteria were unstable"
  triage:                               # optional — Agent Operations output classification (for the Decision Inbox)
    self_report:
      status: "completed"               # completed | blocked | needs_decision | rejected
      risk: "low"                       # high | medium | low | unknown
      decisions_needed: []
    review_gate:                        # self-report verification gate (when a re-judgment is required)
      required: true
      reviewer: "cross_verified"
      result: "agreed"                  # agreed | reclassified | no_reviewer
      final_status: "completed"         # status confirmed after the re-judgment
      max_review_rounds: 1
```

`methodology_signals` is the channel through which the Worker reports **gaps in the methodology itself** found during the work.
Several gaps (e.g. incomplete_spec + rule_gap) can appear in one completion at the same time, so it is a **list**.
The Builder classifies each item individually.
Unlike an ordinary `scope_issue` (a blockage in the current task), it points to candidates for improving rules, schema, or conventions.
At handoff the Builder loads these into the backlog and judges promotion
(→ the "Promotion Gate" section below).

`triage` is the classification applied before the output goes to the human-facing Decision Inbox. The agent fills in `self_report`,
and cross-verification re-judges that label through `review_gate` (because a self-report cannot be trusted). For the rules, the risk-based branching, and the fallback
when there is no re-judge, see → `core/docs/en/methodology/agent-operations.md` "Decision Inbox + self-report verification gate".

---

## methodology-backlog.yaml — accumulating improvement candidates

A separate file that accumulates methodology improvement candidates. It is kept apart from decisions.yaml (the decision record) —
the backlog holds *candidates* and has a different lifecycle (review → adopt/reject).
This section is the source of truth for the backlog **field schema and lifecycle enum**.
The signal flow and the Promotion Gate are also defined in this section (the "Promotion Gate" section below, DEC-2026-10-29-12).

```
project backlog:  $STRATA_VAULT/projects/{name}/backlog/methodology-backlog.yaml  # vault (Tier V)
core backlog:     $STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml  # Strata Core improvement candidates
```

```yaml
methodology_backlog:
  - id: "MB-shop-api-2026-001"   # {project} prefix prevents collisions on central promotion
    scope: "methodology"              # project | methodology
    source:
      project: "shop-api"
      type: "worker_rejection"        # worker_rejection | reviewer_finding | repeated_warning
      ref: "tasks/2026.05.31/01-sync/task-02.yaml"
    signal: "incomplete_spec"
    severity: "major"
    affected_core:                    # at least 1 required when scope: methodology
      - "core/docs/en/methodology/task-spec-schema.md"
      - "core/roles/agent-roles.yaml"
    summary: "The Worker judged completion unverifiable because the test command was missing"
    proposed_action: "Add a verification.commands field to the task schema"
    status: "open"                    # open → triaged → accepted | rejected → applied
    promoted_to: null                 # on promotion, "$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml#<id>"
```

### lifecycle

```
open → triaged → accepted → applied
              → rejected
```

| Status | Meaning |
|------|------|
| `open` | Signal loaded, not yet reviewed |
| `triaged` | The Builder has checked scope, duplicates, and affected_core |
| `accepted` | Adopted as a Core improvement target (promoted) |
| `rejected` | Judged as needing no improvement (reason recorded) |
| `applied` | Applied to Strata Core, templates/adapters regenerated |

---

### Promotion Gate

A backlog item takes a different handling path depending on its `scope`.

- `scope: project` — handled as a candidate to improve that project's rules, layer-map, AGENTS.md, KB, or decisions.
- `scope: methodology` — promoted to the core backlog (`$STRATA_VAULT/projects/strata-kit/backlog/methodology-backlog.yaml`).

For an item with `scope: methodology`, the Builder does the following.

1. Check for duplicates.
2. Check that `affected_core` has at least one entry.
3. Add a promotion item to the core backlog.
4. Record `promoted_to` on the original project item.
5. Until it is reflected in the kit, leave the status as `triaged` or `accepted`. Once reflected, write `applied` and `applied_in` (commit or DEC).

The judgment (`accepted`, `rejected`) is made by a person. The earlier central strata backlog (`strata/methodology-backlog.yaml`) has been moved to the kit backlog (DEC-2026-10-29-12).

## Self-containment checklist

Checked by the Builder after writing a task specification, before handing it to the Worker:

```
□ Is scope.layer a single layer?
□ Does scope.can_reference match layer-rules.yaml?
□ Does scope.constraints include the applicable constraints for that domain/layer?
□ Is there scope.nodes, and does scope.docs_to_update match the coverage resolver result?
  (If there is no owning specification, is creating one in deliverables, or is there an intentional-emptiness reason?)
□ Does inputs.reference_files list every file the Worker needs?
□ Is inputs.requirements understandable without a verbal explanation?
□ Does inputs.conventions summarize the conventions of that layer?
□ Does deliverables.files list every file to create/modify?
□ Is acceptance_criteria in a verifiable form? (tests pass, 0 violations, etc.)
□ Does acceptance_criteria include verification of constraint compliance?
□ Does acceptance_criteria include handling docs_to_update (specification update, or doc_change: none + reason)?
□ Is context_budget.max_reference_files ≤ 5?
```

**If even one item is unmet, it is not handed to the Worker.**

Checked by the Worker on receiving a task:

```
□ Is scope.layer stated?
□ If scope.docs_to_update is empty, is the intentional-emptiness reason stated?
□ Do the files in inputs.reference_files actually exist?
□ Is inputs.requirements non-empty?
□ Is deliverables.files non-empty?
□ Is there at least 1 acceptance_criteria?
```

**On finding an unmet item, reject it to the Builder immediately (report a scope_issue).**

---

## Task cleanup policy

| When | Action |
|------|------|
| Task complete | `status: completed` + fill in the completion section |
| Whole work order complete | `status: completed` in `_order.yaml` |
| Sprint end | Keep completed date folders (do not delete) |
| After 90 days | Completed work order folders may be archived |

The key decisions of a completed task have already flowed back into the handoff and the KB,
so the task file itself is kept only as an **audit trail**.
