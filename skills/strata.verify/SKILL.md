---
name: strata.verify
description: Use before any completion report, merge request, or 'done' claim; when the user asks whether something works, is finished, or can ship; whenever the phrase 'should work' or 'seems right' appears. Keywords - verify, is it done, evidence, before completion, ship.
---

# strata.verify

```yaml
skill:
  id: strata.verify
  version: '0.2'
  owner: worker
  triggers:
  - a completion report is about to be written
  - the user asks if it is done or works
  - '''should work'' or ''seems right'' appears in reasoning'
  inputs:
  - the skill's validation list for the task at hand
  - test, checker and build commands of the project
  outputs:
  - an evidence file .strata/local/verify/<session>.yaml written when each command ran
  - 'a verification table: item, evidence, status (verified / not verified)'
  - a go or no-go line
  required_context:
  - rec.verify.evidence-not-impression
  allowed_tools:
  - read
  - bash(test, build, checkers)
  - bash(tools/verify_evidence.py record, check)
  validation:
  - every validation item has evidence or 'not verified'
  - no item relies on reasoning alone
  - the no-go reasons are listed when any must item is not verified
  - verify_evidence.py check returns 0 for the commands the table cites
  failure_modes:
  - 'evidence cannot be produced in this environment: report ''not verified'' with what would produce it'
  - 'the command runs elsewhere (CI, a remote host): cite that run (id or URL) as the evidence; it is not recorded locally'
```

## Overview

Replaces the impression of completion with evidence. Evidence is written at the moment a test, checker or build runs, and compared at the moment completion is claimed: if a task file changed in between, the evidence is stale and the command runs again. Builds a table of what the owning skill required, what proves each item, and what could not be verified, then states go or no-go.

## When to use

Before any completion report, merge request or 'done' claim; when asked whether something works; the moment 'should work' or 'seems right' appears. Never skipped because the change is small.

## Process

1. Collect the validation items from the owning skill and the task. Evidence: the list.
2. Run each command that produces evidence (tests, checkers, build) through the recorder, naming the files the task changed: `python3 "$STRATA_KIT/tools/verify_evidence.py" record --files <task files or directories> -- <command>`. The recorder prints the output, returns the command's exit code and appends an entry (command, exit code, time, output tail, content hash of the named files) to `.strata/local/verify/<session>.yaml`; the session is the newest per-session active file unless `--session` is given. Name only this task's files: other sessions may be editing the same checkout. Evidence: outputs with exit codes and the evidence file path.
3. Before the report, run `python3 "$STRATA_KIT/tools/verify_evidence.py" check`. Each command's latest entry is passed or failed, fresh or stale (with the files that changed). Re-run a stale command; a failed one is a no-go item. Evidence: the check output.
4. Fill the table: item, evidence (the check line, or the external run for CI), verified or not verified with reason.
5. State go or no-go. No-go when any must item is not verified or its evidence is stale. A handoff that says `tests_passed: true` names the evidence file. A behaviour the change adds or alters must be exercised by a committed test; a one-off command is a manual check, not evidence for completion — mark the item not verified and state no-go until that test exists.

When the question is the whole project rather than one task — is strata actually running here: checkers installed and run, guidance current, decisions committed, solo decisions on core sources, the librarian's last run — run `python3 "$STRATA_KIT/tools/doctor.py" <project>` (read-only; `--json` for the same items). Its default and block items count as must items above; advisory items are reported, not graded (DEC-2026-10-31-22·28).

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "I ran the tests earlier." | `check` says whether earlier is still valid. Stale means run them now. |
| "Recording is overhead; I will just run the command." | The record is what lets the claim be checked later, by you after a compaction or by the next session. |
| "It is a one-line change." | One-line changes break builds. The table is three lines. |
| "I cannot run that here." | Then write 'not verified' and what would verify it. Do not claim it. |

## Red flags

- A done report without a table.
- 'Should work' in a completion message.
- Tests described but no output shown.
- `tests_passed: true` with no evidence file, or a table citing evidence that `check` reports stale.

## Verification

- Table complete.
- `check` returns 0 for the cited commands (fresh and passed), or the item cites an external run.
- Go/no-go stated.
