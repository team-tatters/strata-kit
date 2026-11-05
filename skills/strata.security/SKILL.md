---
name: strata.security
description: Use when the day's security note must be read and acted on — a new urgent item, an advisory to promote or accept, a blind target to link, a grading threshold to change, or a target list to refresh; when the user says security note, vulnerability, CVE, patch, which versions are we running. Reads the note, matches and inventories the core writes, records the person's classification, and never touches a server or patches without the recorded conditions. Keywords - security note, vulnerability, CVE, inventory, grading, accepted risk.
---

# strata.security

```yaml
skill:
  id: strata.security
  version: '0.1'
  owner: librarian
  triggers:
  - the daily note (security/notes/<day>.md) has new urgent or advisory items
  - a target shows under blind targets, or a new service, server or desktop must enter the inventory
  - the person asks what we run, whether a CVE touches us, or to change a grading threshold
  - an advisory should become an order, or a pair should be an accepted risk with a reason and a term
  inputs:
  - security/notes/<day>.md · security/matches/<day>.yaml · security/runs/<day>.yaml
  - projects/<p>/security/inventory/*.yaml · grading.yaml · accepted-risks.yaml
  - security/registry.yaml (what each inventory is built from) · security/sources.yaml (four source layers, manual links)
  outputs:
  - the person's classification written back: an order (promote), an accepted risk (accept, with reason and term), a changed threshold (grading set), a manual link (sources.yaml)
  - a refreshed inventory when the person supplies new measurements (compose, dpkg, docker ps, OS versions)
  required_context:
  - DEC-2026-11-03-02 (two grades, 9.0 default, KEV never grades; patching only under three conditions)
  - DEC-2026-11-03-03 (core skill + librarian daily job; every target; blind targets are shown, not hidden)
  - DEC-2026-11-03-04·05 (list in the vault; repository setting with environment override; file placement)
  - rec.process.confirm-before-state-change · rec.verify.evidence-not-impression · rec.data.soft-delete-only
  allowed_tools:
  - read
  - bash(python3 -m kb security inventory|collect|match|grade|note|daily|grading|order|promote|assign|accept|close|patch plan)
  - write(inventory input files the person supplied, sources.yaml manual_links, grading.yaml through the command)
  validation:
  - every item acted on is in the note or the matches file of that day, with its link set source → record → match
  - no grade was changed by hand — thresholds only through `grading set`, which records who and when
  - an accepted risk has a reason and a term; a promoted advisory has an order file
  - no command was run on a server; measurements came from the person
  - '`python3 -m kb security inventory --all` exits 0 after an inventory change'
  failure_modes:
  - 'the person pastes server output with secrets (compose environment, .env): keep only images and versions in the vault, say what was left out'
  - 'a target has no identifier and no notice place: list it as blind and ask for the notice place; do not guess a CVE match from the name'
  - 'a candidate without any score: it stays advisory with reason no-score — do not raise it to urgent on the title'
  - 'the person wants it patched now: run `patch plan`, read the condition; without one of the three conditions the work ends at the order (DEC-02)'
```

## Overview

The core gives the operator one note a day: what is new, what is still open, what closed, and which targets nobody is watching. This skill is the person's side of that note. It reads what the daily job wrote, puts the person's judgement back into files (an order, an accepted risk, a threshold, a link), and refreshes the target lists when the person brings new measurements. It does not collect, grade or patch on its own — the daily job collects and grades by the recorded rules, and patching happens only through `patch plan` and `patch run` with a condition that holds.

## When to use

Reading the note is the daily trigger. Also when something new must be watched (a server, a desktop, a dependency file), when the person asks whether a vulnerability touches us, or when a threshold or an accepted risk is to be set. Not for incident response (that is the operator's flow) and not for the product's own defect store.

## Process

1. **Read the note of the day.** Open `security/notes/<day>.md`. Start with the urgent lines, then open items with their first day, then blind targets. If the top says a layer was not seen, say so before anything else. Evidence: the note path and its counts line.
2. **Follow the link set before judging.** For each item you act on, open the record and the match in `security/matches/<day>.yaml`: which identifier matched, which range, which score and from which source (NVD, CNA, vendor), whether a value was filled from another source. Evidence: the record id and the match id.
3. **Classify with the person.** Urgent items already have an order (the daily job made it, attributed to infra by default) — show the order and ask only about attribution (`assign`). For advisories ask: promote to an order (`promote <match> --by`), accept as a risk with reason and term (`accept ... --until --by`), or leave it in the note. Never decide alone. Evidence: the command output.
4. **Give eyes to blind targets.** For each blind target ask the person for its notice place (a GitHub repository, a vendor page) and write it as a manual link in `security/sources.yaml`; for a repository without a lockfile, name the SBOM it needs. Evidence: the manual_links line.
5. **Refresh the lists from measurements, never from the server.** When the person pastes `docker ps`, a compose file, `dpkg-query` output or OS versions, keep only images, versions and package names (strip environment, passwords, hashes), put the files where `security/registry.yaml` points, run `python3 -m kb security inventory --project <p> --env <e> --write` and show the difference. Evidence: the diff output.
6. **Change a threshold only through the command.** `python3 -m kb security grading set --project <p> [--env <e>] threshold <value> --by <person>` — the history line is the record. Evidence: the history entry.
7. **Patch only under a condition that holds.** `patch plan <order>` names the condition (code level · no downtime · swap within minutes · recorded acceptance). `patch run` refuses without one; the person's acceptance must be recorded in the order before a run that needs it. Evidence: the plan and the execution record in the order.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The title says remote code execution; I'll mark it urgent." | Grades come from scores and the recorded threshold. Without a score it is advisory with reason no-score — show it, do not raise it. |
| "KEV lists it, so it must be urgent." | KEV orders the note; it never grades (DEC-02). Below the threshold it is advisory. |
| "I'll ssh in and check the version myself." | The agent does not enter servers. Ask the person for the command output. |
| "The compose file has the versions — I'll store it as is." | It also has passwords. Keep images and versions; say what was left out. |
| "The person is busy; I'll accept this risk for now." | An accepted risk is the person's, with a reason and a term. Leave it in the note. |

## Red flags

- A grade or threshold edited in a file by hand.
- An accepted risk without a term, or recorded by the agent.
- A server command run from the session.
- A compose or environment file copied into the vault with secrets.
- A blind target turned into a CVE match by name alone.

## Verification

- Every action names a line of the note or a match id of that day.
- `python3 -m kb security inventory --all` exits 0 after list changes.
- grading.yaml history grew by exactly the changes made; accepted-risks.yaml rows have reason, until and by.
- No file under the server or the product's own flows was touched.
