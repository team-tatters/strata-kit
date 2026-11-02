---
name: strata.distill
description: Use at session close or on request when work produced a reusable judgement, pattern, failure lesson or methodology improvement that should live in the personal knowledge core; when the user says pattern, lesson, reusable, distil, remember this for other projects. Keywords - distil, pattern, personal core, reusable, lesson learned.
---

# strata.distill

```yaml
skill:
  id: strata.distill
  version: '0.1'
  owner: builder
  triggers:
  - a session produced a reusable judgement or pattern
  - a failure taught something general
  - the user asks to keep a lesson for other projects
  inputs:
  - the source evidence in the work vault (decision, session, incident)
  - the personal core taxonomy and existing patterns
  outputs:
  - a candidate entry in the work vault's distill-candidates file (candidate id, source revision, target note id, status)
  - a new or updated personal-core document (pattern, guide, concept) with synthetic example
  - no company names, customer names, internal paths or raw data
  required_context:
  - rec.session.state-in-files
  allowed_tools:
  - read
  - write(personal core)
  - write(distill candidates file)
  validation:
  - the candidate record exists with source revision and target id
  - the personal-core document explains problem, conditions, counter-cases and verification without the company context
  - no identifying company data in the document; guard check passes
  - re-running the same candidate updates, not duplicates
  failure_modes:
  - 'the lesson only makes sense with the company''s specific data model: keep it in the work vault and record ''not distilled'' with the reason'
```

## Overview

Moves what was learned, not what was written, from the work vault into the personal core: a candidate record on the work side, and a re-written pattern or guide on the personal side that stands without the original context.

## When to use

At session close or on request when something reusable emerged. Not every session has a candidate; 'none' with a reason is a valid result.

## Process

1. Name the lesson as a problem and a judgement, independent of the project. Evidence: one sentence.
2. Write the candidate record in the work vault: id, source revision, target note id, status. Evidence: the record.
3. Write or update the personal-core document: problem, options and trade-offs, conditions, counter-cases, verification, a synthetic example. Evidence: the document.
4. Run the guard (names, domains, paths, attachments) and read the result yourself. Evidence: guard output.
5. Mark the candidate applied; a re-run with the same id must update, not duplicate.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "Just copy the document, it is already written." | Copies carry the company context. Re-write the general part only. |
| "The guard passed, so it is clean." | String checks catch names, not shapes. Read it as an outsider. |
| "I will distil at the end of the project." | Lessons fade. Distil at the session that learned them. |

## Red flags

- A personal-core document that cites a company path as its only source.
- Two documents for one candidate id.
- A candidate with no target id.

## Verification

- Candidate record complete.
- Document stands alone; guard passed and was read.
- Re-run is idempotent.
