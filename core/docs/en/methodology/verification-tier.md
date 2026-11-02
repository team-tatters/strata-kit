# Verification Tier

> Canonical: strata-kit `core/docs/en/methodology/verification-tier.md` (migrated 2026-10-29 from strata `docs/04-agents/verification-tier.md`, DEC-2026-10-29-11).

> An axis of verification independence, orthogonal to the execution mode (Verbal/Task).
> The execution mode covers *how the work is done*; the verification tier defines *who verifies the result*.
> This document is the source of truth for the `verification_tier` enum.

## Tier definitions

| Tier | enum value | Definition | Verification independence |
|------|------------|------------|---------------------------|
| **Solo** | `solo` | The party that executed verifies with its own checklist | None |
| **Self-Verified** | `self_verified` | An independent Reviewer within the same execution environment/tool family verifies | Medium |
| **Cross-Verified** | `cross_verified` | A Reviewer from a different execution environment, tool family, or model family verifies | High |

- Tool names are not written in Core. Mappings such as "executed by X → verified by Y" belong in the per-tool adapter (AGENTS.md, settings).
- The Reviewer sees not the whole conversation but only **the request + the diff + the rules + the test results + the checklist**.
- The display name is `Cross-Verified`; the enum value written in `_order.yaml` is `cross_verified`.

## Defaults and required range

```text
Verbal Mode: when verification_tier is omitted → solo
Task Mode:   stating verification_tier in _order.yaml is recommended
Changes to a Core source of truth (layer-rules / naming-convention / task-spec-schema / agent-roles):
             → cross_verified required
Other Core document and adapter changes (core/docs/, core/templates/, etc.):
             → cross_verified recommended
```

Do not make people declare a Tier for every small edit. If the cost of declaring exceeds the benefit of verifying, Strata becomes heavy.

## Implementation patterns

The TDD Writer/Reviewer (`core/docs/en/methodology/session-splitting.md` §2.4) is one implementation pattern of the Self/Cross-Verified Tier.
The session-splitting document covers how to split sessions; this document holds the meaning of verification independence and the enum.

The concrete tool implementation of Cross-Verified is covered by `skills/strata.review/SKILL.md`.
That skill is the procedure that actually performs this document's `cross_verified`; this document does not define the procedure.

## Relationship to other axes

- **Execution Mode**: choosing and switching between Verbal/Task is defined in `core/docs/en/methodology/execution-modes.md`.
- **Agent Operations**: `reviewer: cross_verified` in the Decision Inbox uses this Tier. The operating discipline is defined in `core/docs/en/methodology/agent-operations.md`.
- **Methodology Feedback Loop**: methodology gaps that a Reviewer finds are filed in the backlog and promoted through the Promotion Gate flow of `core/docs/en/methodology/task-spec-schema.md`.

## Design verification axis (design_verified)

The third axis, orthogonal to the execution mode and the verification tier. It defines who checked **the consistency between the design deliverable and the implementation** (`core/docs/en/architecture/frontend-design-contract.md` §Design artifacts and alignment).
This document is the source of truth for the `design_verified` enum in `_order.yaml`.

| Value | Definition |
|---|---|
| `none` | No UI deliverable (`design_ref.kind: none`), or not verified |
| `self` | The implementer cross-checked on their own against the consistency definition (name, axis, alias, state axis) |
| `designer` | The owner of the design deliverable (the designer or the person in charge of the design tool) confirmed it |
| `cross` | A Reviewer from a different execution environment or model confirmed it by comparing the story render/frames |

Defaults and required range:

```text
No design_ref, or kind: none → none
New/changed Primitive UI · Semantic Component (shared UI package) → designer or higher recommended
Feature Block · Route Surface → self or higher
```

If `completion.design_sync` is `stale`, the work is not complete regardless of this axis's value. `waived` carries a reason and an expiry date.
