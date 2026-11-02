---
name: strata.build-task
description: Use when executing one task file from an order: implementing code within one layer, running its tests, and reporting with evidence; when the user says implement, build, do the task, write the code. Keywords - implement, build task, worker, single layer.
---

# strata.build-task

```yaml
skill:
  id: strata.build-task
  version: '0.2'
  owner: worker
  triggers:
  - a task file is assigned
  - the user asks to implement a planned change
  inputs:
  - task-NN.yaml
  - layer rules and naming convention of the profile
  - the files named in the task
  outputs:
  - code and tests within the task's layer
  - completion report with constraint compliance and evidence
  - a rejection with reasons when the task is incomplete
  required_context:
  - rec.architecture.no-layer-violation
  - rec.naming.follow-convention
  - rec.verify.evidence-not-impression
  allowed_tools:
  - read
  - edit
  - test
  - bash(build and test commands)
  validation:
  - the task's verification command passed and its output is in the report
  - no file outside the task's layer was changed
  - each constraint in the task is marked complied or not, with a reason
  failure_modes:
  - 'the task lacks files, constraints or a verification command: reject it, do not guess'
  - 'a change outside the layer is needed: stop and report the boundary'
```

## Overview

Executes one task: reads the specification the task carries, changes only the named files within one layer, runs the verification command, and reports completion with evidence and per-constraint compliance.

## When to use

A task file from strata.order is assigned, or the user asks to implement a planned change. Not without a task: an incomplete task is rejected with the missing items listed.

## Process

1. Read the task and check it is complete (layer, files, constraints, verification). Evidence: the checklist. Reject if incomplete — but read the named files and the documents they point to first, and list the missing decisions as concrete choices with options and a recommendation; reading is not guessing, implementing is. Then claim the order (`python3 -m kb order claim <order-id>`); if another machine or session holds it, stop and ask the person. Evidence: the claim output.
2. Read the named files and one existing example of the same pattern. Evidence: paths.
3. Write the failing test first when the task adds behaviour, then the minimal code, then refactor. Evidence: test output before and after.
4. Run the task's verification command and the layer checker. Evidence: outputs and exit codes.
5. Report: files changed, constraint compliance table, evidence, anything not verified.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The task is almost complete, I can infer the rest." | Inference is how layers get crossed. Reject and ask for the missing items. |
| "Tests after the code are fine." | The failing test is the evidence that the test tests something. |
| "The checker warning is a false positive." | Report it as a warning with your reasoning; do not silence it. |

## Red flags

- Edits to files not named in the task.
- A report with no command output.
- A constraint marked complied with no reason.

## Verification

- Verification command output is in the report.
- Only files within the layer changed.
- Constraint compliance table is complete.
