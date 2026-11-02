# 09 — Context Protocol: Constraint-Aware Context Loading

> Canonical: strata-kit `core/docs/en/methodology/context-protocol.md` (migrated 2026-10-29 from strata `docs/09-context-protocol.md`, DEC-2026-10-29-11).

> Based on the principles of the kit cards (`rec.context.entry-view-budget`, `rec.session.split-at-task-boundary`, `rec.session.state-in-files`) and `core/docs/en/methodology/session-splitting.md`, this document defines the rules for constraint-aware context loading.

## 1. Problem definition

The ways in which a domain constraint decided in an ADR (for example "no hard-delete", "Bitemporal required") gets lost at implementation time:

1. The ADR prose is too long to read in full every time
2. ADR details are lost at compaction
3. A Worker has an independent context — it does not know the ADR discussion from the Builder session
4. If a domain constraint is missing from the task specification, the Worker cannot detect it

## 2. Solution: constraints go into the entry view as a summary; the full registry is read on demand

### Context tiers

```
T0 — Universal (always loaded, within 12KB — rec.context.entry-view-budget)
  ├── AGENTS.md + CLAUDE.md            (generated guidance — must card summary, constraint summary within 2KB)
  └── active/{session-id}.yaml         (per-session active-task — DEC-2026-08-19-05)

T1 — Session (at session start)
  ├── The latest handoff file
  ├── decisions.yaml                   (generated index, on demand — the source of truth is the decisions/ records)
  └── constraint-registry.yaml         (on demand — through the entry view's link)

T2 — Domain (per task target)
  ├── The node page of the topic node (a join of final shape, policy, decisions, work history, and debt — generated, the entry point)
  ├── The full Constraint Card of that domain
  └── The Decision Outcome section of the related ADR

T3 — Implementation (at implementation time)
  ├── The target source files
  ├── The test files
  └── layer-rules.yaml (the section for that layer)
```

### constraint-registry.yaml rules

- **Location**: `.strata/constraint-registry.yaml` (inside the project)
- **Size limit**: within 3KB. The generated guidance carries only a 2KB summary and links the full file
- **When it exceeds 3KB**: move `severity: should` items to a separate file. Keep only `must`/`must-not` in the registry
- **When to update**: at the same time as an ADR moves to accepted and as a Constraint Card is created
- **Format**: the same YAML index as `decisions.yaml`

```yaml
constraints:
  - id: CC-NNN-01
    source: ADR-NNN
    severity: must
    scope: {domains: [{domain}], layers: [{layer}]}
    rule: "{one-line executable rule}"
    status: active
```

### decisions.yaml rules (corrected 2026-08-19)

- The `decisions.yaml` read on demand is a **compact index regenerated from the records (`.strata/decisions/DEC-*.yaml`)**. Hand-editing is forbidden.
- Only the **decision writer CLI** adds decisions, assigns numbers, and regenerates the index (serialized with flock — safe with several sessions at once, DEC-2026-08-19-05. Role → implementation mapping: `python3 -m kb --help`, `core/docs/en/kb-engine.md`).
- When you need detail, load the full record through the `record:` path of the index entry — the same pattern as the layered detail of Registry (1 line) → Card (~50 lines) → ADR (~200 lines) (index summary → full record).
- The physical location of Tier P follows the placement profile (`core/docs/en/environment/data-placement.md` §1.5 — embedded=repo, detached=vault `projects/{n}/strata/`).

## 3. Context loading per Agent Role

### Builder

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Creating a task | ✓ constraint-registry filtered | ✓ | Node page → the Cards of that domain | - |
| Writing an ADR | ✓ | ✓ | Node page (check the decision chain) | - |
| Extracting a Constraint | ✓ | - | - | - |

The Builder reads constraint-registry.yaml, filters by the task's domain/layer,
and injects the matching constraints into `scope.constraints` of the task specification.
In the same way, it finds the specification that owns the change scope (`covers`) with the coverage resolver and injects it into `scope.docs_to_update`.
The node page is the entry point for these two injections — opening one node shows the current specification, the active constraints, and the current decisions on a single screen.

### Worker

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Executing a task | CLAUDE.md only | - | - | ✓ |

**The Worker does not read constraint-registry.yaml directly.** It does not read node pages directly either.

It uses only what the Builder injected into `scope.constraints` and `scope.docs_to_update` of the task specification.
This matches the **self-containment** principle of the task specification.

```yaml
# The task specification a Worker receives
scope:
  layer: "L2_DataLayer"
  constraints:
    - id: "CC-NNN-01"
      rule: "A constraint that applies to this scope"
    - id: "CC-NNN-02"
      rule: "Another constraint"
```

The Worker converts this `scope.constraints` into `constraint_compliance` in the completion report.

### Supporter

| Situation | T0 | T1 | T2 | T3 |
|---|---|---|---|---|
| Searching constraints | ✓ registry search | - | Search results only | - |

At the Builder's request, the Supporter searches for the constraints of a specific domain/layer.

## 4. Context Budget rules

```
CB-1: T0 (AGENTS.md + CLAUDE.md) within 12KB, within 14KB including inherited guidance (wizard verify)
  → the constraint registry and the decision index are not T0; constraints go into the generated guidance as a 2KB summary
  → if the guidance grows too large, shrink it into a table of contents (reference-centered) first
  → the entry path using-strata reads (skill body, core registry, constitution) is reported separately by verify (2026-10-29, no ceiling)

CB-2: A T2 Constraint Card is within 10KB per domain
  → if it exceeds 10KB, load only the registry's one-line summary instead of the full Card

CB-3: The total .strata/ load is within 30KB (T0+T1+T2 combined)
  → if it is exceeded, replace T2 with the matching rows of the registry

CB-4: The full ADR is loaded only by the Builder (writing an ADR / extracting a Constraint)
  → other roles reach the ADR's decision through the Constraint Card
  → this is the reason the Constraint Card exists

CB-5: A node page is within 8KB per node (together with the Card budget of CB-2, this keeps the T2 ceiling)
  → the generator cuts the work-history section to the latest 5 entries and the decisions section to the current one plus the one before it, to fit the budget
  → if it still exceeds, keep only the final-shape and policy sections and replace the rest with links
```

## 5. Compaction resilience

```
Before compaction:  the full ADR + detailed discussion (present in the context)
After compaction:   only a summary remains — risk of losing ADR detail

Constraint recovery path:
  constraint-registry.yaml (it is a file, so it can always be read again)
  → the one-line summary immediately shows "what must be kept"
  → if detail is needed, refer to the individual Constraint Card (T2)
  → if deeper context is needed, refer to source_adr

Layered Detail:
  Registry (1 line)  →  Node page (~100 lines)  →  Card (~50 lines)  →  ADR (~200 lines)
  summary in entry view  once, on entering a domain   loaded when needed   almost never loaded
```

The node page does not replace the Card and the ADR. It is an entry point that tells you which Card, which ADR, and which specification is current; the body lies beyond the links.

## 6. Relationship to existing context management

| Existing (kit cards and session-splitting.md) | This document (extension) |
|---|---|
| CLAUDE.md tier design (§2·§4, `wizard verify`) | Kept — the constraint summary goes into the generated guidance, the full registry is read on demand |
| Handoff protocol (`strata.handoff`, session-splitting.md §5) | Kept — the constraint extraction status is added to the handoff |
| Compaction defense (execution-modes.md, `kb pre-compact`, SessionStart compact) | Strengthened — the registry is an additional recovery anchor |
| Token budget guide (session-splitting.md §5.2) | Extended — rules CB-1~5 added |
| Memory vs Handoff vs KB distinction (§7, rec.session.state-in-files, rec.kb.session-records-in-vault) | Kept — Constraint Cards are placed in the KB |
| (new) Topic node | T2 entry point — the node page is a product of the Index tier, not a source of truth (core/docs/en/knowledge-base/vault-structure.md) |

## 7. Memory, handoff and KB

The harness memory (for Claude Code, `~/.claude/projects/<project>/memory/`) is read at every session start through its index, so what goes there changes the next session's judgement.

| What | Where | Why |
|---|---|---|
| Progress state — the work at hand, what comes next, uncommitted changes, blockers | The active file (`.strata/local/active/`) and the handoff | It goes stale when the session ends; in memory, the next session reads a past state as a present fact |
| Long-lived facts — the user's preferences, instructions on how to work, where outside resources are | The harness memory | Things every session must read without asking |
| Decisions and policies | Decision records, cards | The reviewed source of truth; a memory feedback that becomes policy moves here |
| Design, specifications, knowledge | The vault KB | Tied to the code by links and coverage |

**Progress state does not go into memory.** When a session closes, the progress-state facts it wrote to memory move to the handoff (`strata.handoff` memory check step, DEC-2026-10-31-16).

**Verification date.** A memory fact's front matter carries the last day it was confirmed correct as `verified: YYYY-MM-DD` (DEC-2026-10-31-14·34). The harness's `modified` is the day it changed; `verified` is the day it was seen to be still right. The agent writes it when it writes or edits a fact, and the handoff check updates it for facts the person confirms are still right.

**Cleanup.** `python3 -m kb hygiene --memory` lists the cleanup candidates in the current folder's memory with their reasons: stale (verified, else modified, over 60 days — user config `memory.stale_days`), no date, a status-word match, unknown format, possible contradicting feedback pairs, and an index that does not match the files. The tool only reads and never prints the body. A status-word match is a match, not a verdict — a rule that names a state matches too. Moving, merging and deleting happen only for facts the person approves one by one. A deletion moves the file to `_archive/` in the same directory, writes `retired` and `retired_reason` in its front matter and removes the index line (DEC-2026-10-31-17). `wizard verify` shows the size of the memory index and warns over 12 KB without failing (DEC-2026-10-31-19). Codex memory is out of scope for now (DEC-2026-10-31-13).
