---
name: strata.order
description: Use when an approved specification must become an order and tasks for workers; when the user says plan, break it down, split the work, order, task list; when a change touches more than one layer or more than one worker. Keywords - plan, tasks, order, breakdown, who does what.
---

# strata.order

```yaml
skill:
  id: strata.order
  version: '0.1'
  owner: builder
  triggers:
  - a specification is approved and work must be split
  - the user asks for a plan or task list
  - a change spans layers or workers
  inputs:
  - desired specification
  - layer-map and profile
  - constraint registry filtered to the scope
  outputs:
  - _order.yaml with goals, acceptance, task list and dependencies
  - task-NN.yaml per task with layer, files, constraints, verification
  - inline mode note when the order is small
  required_context:
  - rec.structure.prepaid
  - the profile's layer-map
  allowed_tools:
  - read
  - write(order and task files)
  validation:
  - each task is one layer and names its files, constraints and verification command
  - dependencies form no cycle
  - small orders (two or three tasks, one concern) use inline mode and say so
  failure_modes:
  - 'the specification has unresolved open questions that block a task: stop and list them'
  - 'a task would need two layers: split it or stop'
```

## Overview

Turns an approved specification into an order and self-contained tasks a worker can execute without the conversation: one layer each, explicit files, constraints from the registry, and the command that proves completion.

## When to use

After strata.spec, when work must be split. Also when the user asks for a plan. Small orders (two or three tasks, one concern) use inline mode: the order is written, the task ceremony is reduced to a checklist in the same file.

## Process

1. Read the specification and the layer-map. Evidence: paths.
2. Write the order: goal, acceptance criteria copied from the spec, task list with dependencies. Evidence: _order.yaml.
3. Write each task: layer, files to touch, constraints filtered from the registry by scope, verification command, done criteria. Evidence: task files.
4. Decide inline mode if the order is small and say why. Evidence: the note in the order.
5. Check for cycles and for tasks spanning two layers. Evidence: the check result.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The worker will figure out the files." | A plan is written for a reader with no context. Name the files. |
| "The constraints are in the registry anyway." | Filter them into the task. Workers read the task, not the registry. |
| "Small change, skip the order." | Use inline mode. Skipping the order loses the acceptance criteria. |

## Red flags

- A task that names no verification command.
- A task touching two layers.
- An order with no acceptance criteria.

## Verification

- Every task has layer, files, constraints, verification.
- No dependency cycle.
- Inline mode, if used, is stated with its reason.
