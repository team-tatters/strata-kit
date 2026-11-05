# Knowledge Base — Document Format

> Canonical: strata-kit `core/docs/en/knowledge-base/document-format.md` (migrated 2026-10-29 from strata `docs/07-knowledge-base/document-format.md`, DEC-2026-10-29-11).

## Overview

Every `.md` file in the vault must contain YAML frontmatter.
Use a format that both Obsidian and the MCP server (Phase 3) can parse.

## Frontmatter schema

```yaml
---
# === Required fields ===
title: "Document title"
id: "{prefix}-{project}-{slug}"  # Stable ID — unchanged by moves and renames (prefix scheme: the stable ID section of core/docs/en/knowledge-base/vault-structure.md)
type: overview | decision | session | pattern | reference | glossary
      | concept | specification | flow | guide | runbook | constraint | epic | moc | node
created: YYYY-MM-DD

# === Conditionally required ===
project: {project-name}       # For project-specific documents (for cross-cutting documents, put vault in the project slot of the id)
status: draft | active | review-needed | superseded | archived
sources: ["[[source session/task]]"]  # Required when updating a Knowledge-layer document (KB, pattern) — links to the Archive evidence (DEC-2026-08-19-03)
nodes: ["{node-id}"]          # Topic node membership — required for decision, session, specification, concept, constraint (section "Node and coverage fields")

# === Optional fields ===
tags: [namespace/value, ...]  # Namespaced tags recommended
updated: YYYY-MM-DD           # Last modified date
updated_by: {git user}@{machine}  # Last updater — the write hook stamps it from the git identity and the machine alias (DEC-2026-09-09-05)
page_order: 1                 # Document order within a category (for the KB index)
author: builder | worker | manual  # Who wrote it
machine: {alias}              # Machine that wrote it: this machine's alias (STRATA_ENV) in env-config.yaml — vault-git refuses a session record naming another machine
superseded_by: "[[new document]]"   # When status is superseded (superseded side → superseding side)
supersedes: ["[[earlier decision]]"]   # decision — the earlier decisions this one supersedes (the opposite direction of superseded_by)
covers: {paths, symbols, endpoints, tables}  # specification, concept — the code surface this document is canonical for
doc_change: none              # session, task — declares that code changed but the as-built shape was not updated (doc_change_reason required)
aliases: ["old file name"]         # Keeps the original identifier when moved or renamed
related: ["[[related document 1]]"]     # Obsidian wikilink — a mention relation (ownership is covers)
---
```

## Required fields by type

| type | Additional required fields | Description |
|---|---|---|
| `overview` | `project` | Overview of a project or a category |
| `decision` | `project`, `status`, `nodes` | ADR. Includes the context and rationale of the decision. Optional `supersedes` |
| `session` | `project`, `machine`, `nodes` | Session handoff / ledger. **Only the metadata and summary part are indexed** (Archive — 2026.08.19-06). Optional `doc_change` |
| `pattern` | — | Reusable pattern that cuts across projects |
| `reference` | — | Summary reference of an external document, standard, or specification |
| `glossary` | — | Definitions of domain or technical terms |
| `concept` | `nodes` | Domain concept, business rule, or explanation of a principle. Optional `covers` |
| `specification` | `status`, `nodes` | Feature spec, requirements, constraints, acceptance criteria. The final shape of a node. `covers` recommended |
| `flow` | — | Business process, data flow, sequence |
| `guide` | — | Step-by-step guidance, how-to document |
| `runbook` | `status` | Operations / incident response procedure |
| `constraint` | `source_adr`, `severity`, `scope`, `rule`, `verification`, `status`, `nodes` | A single enforceable constraint extracted from an ADR |
| `epic` | `constraints`, `domains`, `layers`, `personas`, `status` | A PRD feature unit. A constraint link is required |
| `planning` | `project`, `status`, `nodes`, `source`, `implementation` | Original planning text imported from an external planning tool (PRD, policy, Epic/Story). The original text is immutable, plus an `## Implementation review` section. `implementation.status` classifies the review result. status is the planning state (lifecycle_override) |
| `moc` | — | Table of contents (Map of Content). `_index/`, each `_index.md`, and generated static indexes. **Generated only** |
| `node` | `project`, `node` | Topic node page. Joins the final shape, policies, decisions, planning, work history, and debt. **Generated only** |

`moc` and `node` belong to the Index layer. Do not write them by hand; regenerate them from the canonical sources (frontmatter, records, toc.yaml).

## Node and coverage fields

A topic node (node) is the unit of the table of contents that people read. One node is the key that gathers the final shape (specification), policies (constraints), decisions, and work history on one screen. The canonical node tree is the project's `_meta/toc.yaml`, and a document links itself to nodes and code with the four fields below. **This section is the canonical source for value formats.** The taxonomy only decides whether a field is required.

### `nodes` — the topic nodes this document belongs to

```yaml
nodes: ["orders.checkout-v2.coupon"]   # node ids defined in toc.yaml; several are allowed
```

- A node id lives in a **different namespace** from the document id (`{prefix}-{project}-{slug}`). It is a path joined by dots (.) from the ancestor down, and each segment is kebab-case.
- Required for decision, session, specification, concept, and constraint. Task specs use the same field (see `core/docs/en/methodology/task-spec-schema.md`).
- The nodes of sessions and tasks are derived by the coverage resolver (changed file → the specification that owns that file → that specification's node). A person picks them only for sessions with no code change.
- An empty array is allowed, but validation warns. If having no node is intentional, leave the reason in the body.

### `covers` — the code surface this document is canonical for

```yaml
covers:
  paths: ["service/order-api/src/main/kotlin/com/example/order/refund/"]   # repository-relative path, substring match
  symbols: ["RefundCalculationService"]                              # class or function name
  endpoints: ["POST /v1/orders/{id}/refunds"]                    # METHOD + path prefix
  tables: ["refund_items"]                                      # table name
```

- Use it only in specification and concept. Sessions, decisions, and constraints do not have `covers`. They only point to a node through `nodes`.
- Do not use file-level paths. Use only identifiers that stay stable under moves, such as a module, package, controller, or route prefix. The matching rule is the same as the path matching in the layer-map (substring, from the top).
- Exactly one document owns a surface. Validation warns on overlap. Link a higher-level concept document with `up`.
- `covers` is **ownership**, not a mention. Put mentions in `related`. If this distinction blurs, five documents end up owning one file, and the coverage gate becomes noise and gets ignored.
- A code path pointer does not conflict with the principle of keeping no source code in the vault. Only repository-relative paths are recorded, not code (`core/docs/en/knowledge-base/vault-structure.md`, "What is never included").

### `doc_change` — when code changed but the as-built shape was not updated

```yaml
doc_change: none
doc_change_reason: "Refactoring only — no change to external contracts or policies"
```

- Used in session and task. If a `covers` path changed, the document that owns that surface was not updated, and this field is absent, the session-end gate records it as **debt** of that node and warns.
- An empty value is forbidden. If it is `none`, a reason must be attached. It is the same principle as the ledger requiring a reason for `next: "none"`.

### `supersedes` — the earlier decisions this decision supersedes

```yaml
supersedes: ["[[DEC-2026-08-13-05]]"]
```

- Used in decision. **The state of the superseded side is derived, not stored** (DEC-2026-09-30-03): a decision that appears in some record's `supersedes` automatically gets `status: superseded` and `superseded_by` in the index and in the DEC note. The record file of the superseded side is not edited.
- To add a supersession relation to an already recorded decision later, use `python3 "$STRATA_KIT/kb" decision supersede --id new --target old`; to retire a decision without a superseding decision, use `python3 "$STRATA_KIT/kb" decision withdraw --id X --reason ...`. Merely writing "superseded" or "withdrawn" in the body is not recognized as a state.
- KB documents (other than decision) still carry `status: superseded` and `superseded_by` written by hand on the superseded side.
- `superseded_by` is the existing field for the opposite direction (superseded side → superseding side). The two are the two ends of the same fact.
- The "decisions" facet of a node page shows the end of this chain as the current decision and the rest as history.

## Document lifecycle

```
draft → active → review-needed → superseded → archived
                      ↓                ↓
                   active           archived
```

| State | Meaning | Allowed transitions |
|------|------|-----------|
| `draft` | Being written, not yet reviewed | active, archived |
| `active` | Valid, current document | review-needed, superseded, archived |
| `review-needed` | Needs an update (flagged automatically after 90 days) | active, superseded, archived |
| `superseded` | Replaced by a new document. The `superseded_by` field is required. If the superseding decision declares `supersedes`, the pair is subject to symmetry validation | archived |
| `archived` | No longer valid. Search weight is reduced | — |

**Exception by type**: `constraint` uses its own lifecycle —
`active → superseded → retired` (taxonomy.yaml `lifecycle_override`).
A constraint is created as active at the moment its ADR is accepted, with no draft state, and its retirement is marked `retired`.

## Body rules

### General rules

- Markdown format (CommonMark + Obsidian extensions)
- Headings start at `##` (`#` is avoided to prevent duplicating the frontmatter title)
- One document focuses on one topic (MECE principle)
- Maximum length: overview/pattern/concept 500 lines, ADR 200 lines, session summary 100 lines, specification 1000 lines, table of contents and node pages 300 lines
- The canonical source of body section headings is taxonomy `document_types.{type}.body_sections`. The structure blocks below are a rendering of it, and the generator builds headings from the taxonomy

### Readability rules (required)

- **Self-contained terms**: a document must be understandable from that document alone. Do not use terms whose meaning is unclear without outside technical background — English jargon, implementation-internal concepts, or compound words the author coined — as they are. If one is truly needed, **explain it in one line at its first appearance**. (Example: instead of words like "materialize", "resolve", "single-flight", "degraded", **spell out the action**, such as "build it ahead of time on the first request" or "look it up and assemble it".)
- **Body and closing flow match**: the "open / needs confirmation / request answers" items at the end of a document are drawn only from what the body actually defined and developed. Do not introduce a new concept for the first time in the closing section. The reader must be able to find, one to one, which part of the body each open item connects to.
- **Criterion**: "Can a teammate on the same team who sees this document for the first time understand every term and every open item from the body alone, without searching elsewhere?" If not, spell it out or add the grounds to the body.

### Rules for human-read documents (required — DEC-2026-09-10-01)

The reader is a person. Do not write in a shape that is easy for an agent to parse. These rules apply equally to KB documents, session handoffs, decision records, and chat reports.

- **Use only arrangements a person can take in.** Do not write paragraphs or tables whose meaning cannot be understood in one reading. Do not list code symbols, paths, or decision IDs in place of an explanation. A table holds one fact per cell, and no table goes inside a table.
- **Forbid duplication and verbosity; write in one context.** Do not repeat the same fact in several sections. Keep one flow so that the viewpoint does not change when a section changes.
- **Summary first, grounds after.** When the account gets long, put a summary of the conclusion at the very top, and attach code locations, measured values, and quotations in a grounds section afterward. A reader must be able to decide from the summary alone.
- **Do not use code-style order labels.** Do not classify tasks, document order, or items with codes that combine a letter and a number, such as `A1·A2·B3`. Write order and items as short sentences whose meaning shows. (Not "A3 hub pruning" but "delete the screens the hub no longer uses".) Add the original label in parentheses only when quoting an existing document that already carries one.

### Decision (ADR) body structure

```markdown
## 맥락
{the background that made the decision necessary}

## 결정
{the chosen direction and the reason}

## 대안
{directions that were considered but not chosen, and why}

## 결과
{the effects of this decision, the trade-offs}
```

A decision that declares `supersedes` leaves one line in `## Consequences` saying what it supersedes and why. When a node page shows the decision chain, that line becomes the explanation.

### Session summary body structure

```markdown
## 완료
- {completed item}

## 진행 중
- {unfinished item and its current state}

## 결정 사항
- {decision made in this session}

## 주의 사항
- {warning/issue the next session needs to know}
```

- The four sections above are the structure of the handoff **summary part**. The format of the ledger's actor entries and of the `next_session` block is canonical in `core/docs/en/methodology/agent-operations.md` §5.3, and coexists with this structure.
- If code changed but the final shape was not updated, declare `doc_change: none` and a reason in the frontmatter, and write the same reason under `## Cautions`.

### Pattern body structure

```markdown
## 문제
{the problem this pattern solves}

## 해결
{description of the pattern}

## 적용 예시
{code snippet or structure example}

## 적용 프로젝트
- [[project-a]] — {how it was applied}
```

### Constraint Card body structure

A single enforceable constraint extracted from an ADR. Keep it concise, within 50 lines.

```yaml
---
title: "{constraint title — one-line noun phrase}"
type: constraint
created: YYYY-MM-DD
status: active
source_adr: "[[NNN-adr-slug|ADR-NNN]]"
severity: must-not        # must | must-not | should
scope:
  domains: [{domain}]     # business domains this constraint applies to
  layers: [{layer}]       # Strata layers this constraint applies to
rule: "{one-line enforceable rule — a MUST/MUST NOT sentence}"
verification: code-review  # code-review | unit-test | integration-test | static-analysis
tags: [constraint, severity/{level}, layer/{layer}, domain/{domain}]
aliases: [CC-NNN-NN]       # unique ID (ADR number-sequence number)
---
```

```markdown
## 근거
{which section of the ADR it was derived from, and why this constraint is needed, in 1-3 lines}

## 위반 시 영향
{what problems occur if this constraint is broken, in 1-3 lines}

## 검증 방법
{concrete ways to check, such as code review, tests, static analysis}
```

**Constraint Card writing rules:**
- Extract them in the same session when an ADR moves to accepted (a Builder duty)
- 1 ADR → N Cards (usually 3-10)
- Decide severity from the wording of the ADR text: "must/required/MUST" → must, "forbidden/NEVER" → must-not, "recommended/SHOULD" → should
- scope is the range of domains and layers this constraint applies to
- Register a one-line summary in constraint-registry.yaml at the same time

### Epic body structure

A PRD feature unit. It links to ADR constraints through the constraints field.

```yaml
---
title: "{feature unit title}"
type: epic
project: {project-name}
created: YYYY-MM-DD
status: draft
constraints:                # ★ Required — the Constraint Cards this Epic must comply with
  - "[[CC-NNN-01]]"
  - "[[CC-NNN-02]]"
domains: [{domain}]
layers: [{affected layers}]
personas: [{target personas}]  # persona IDs defined in the project
tags: [epic, domain/{domain}]
---
```

```markdown
## Goals
{the user problem this Epic solves, in 1-3 lines}

## Acceptance criteria
- {verifiable completion condition}

## Constraints summary
{a summary of how each Constraint Card in the constraints field applies to this Epic}
```

**Epic writing rules:**
- The constraints field is required. An empty array is a review signal (you must tell an intentional blank from an omission)
- When splitting into tasks, the Builder distributes the Epic's constraints into each task's scope.constraints

### Planning body structure

Original planning text imported from an external planning tool (Notion and the like). Most of these documents are past the request stage or already reflect decisions, so they are treated as **planning**, not as a "request" (DEC-2026-09-09-01).
The original text is as-intended, and the Knowledge specification is as-built. Do not mix the two in one document — do not edit the original sections; update only the `## Implementation review` section at the end of the document.

```yaml
---
title: "{original title}"
id: plan-{project}-{source id}          # unchanged on re-import
type: planning
project: {project-name}
status: realized                      # planning state — requested | planned | in-progress | realized | on-hold | archived
nodes: ["orders.payments-v2"]           # recorded after Inbox approval (the importer only proposes candidates)
source: "notion:{32hex}"              # source identifier (required)
source_name: notion-orders-intake        # subdirectory under planning/
source_path: "{source export relative path}"  # edition tracking
up: "[[plan-{project}-{parent id}]]"    # when there is a parent document, as with Epic/Story
topic: "Category: … · Task grouping: … · Sprint: …"   # one line of source properties — searched by the node backfill planner
owner: "{name}"                       # optional — the plan's owner; a plan-gap judgement is asked of them (else the user, DEC-2026-10-31-35)
implementation:                       # ★ Required — classification of the implementation review result
  status: unreviewed                  # unreviewed | implemented | partial | diverged | not-implemented | superseded
  reviewed: YYYY-MM-DD                # omit if unreviewed
  spec: "[[kb-…]]"                    # the distilled final-shape document (if any)
created: YYYY-MM-DD
---
```

```markdown
# {original title}
{original text — do not edit}

## 구현 검토

| Item | Plan | Implementation | Difference | Evidence |
|---|---|---|---|---|
| {policy item} | {what the plan says} | {what the code does} | {none · different · not implemented} | {code path · symbol · spec link} |
```

**Planning writing rules:**
- Write `## Implementation review` per item (policy sentence, checkbox, Story). The one-line summary of the document is carried by `implementation.status` — if it is diverged or partial, the table must have a difference row.
- If the review leads to a specification update, add this document to that specification's `sources:` and point back with `implementation.spec`.
- `status` (planning state) and `implementation.status` (implementation review) are different axes. A plan marked "deployed" can differ from the code — that is diverged.
- The "planning" facet of a node page joins only this type and shows it with badges (unreviewed, implemented, partially implemented, differs from plan, not implemented, superseded). The unreviewed count and the diverged or partial documents are counted as debt.
- When the plan and the code disagree, do not stop at a difference row in `## Implementation review`: queue a judgement request (`python3 -m kb divergence add`; the gate's recheck rows with `kb coverage-gate --divergence-inbox`). Only a person judges, with one of four: consistent (no divergence), doc stale (bring the plan or specification up to the code), plan gap (ask the `owner` to complete the plan), implementation defect (a bug task). Recording the judgement (`kb divergence judge`) sets `implementation.reviewed` to that day, so the same changes do not ask for a recheck again; `implementation.status` is updated by the judgement (DEC-2026-10-31-35).

### Planning bundles (strata.planning)

When an outside planning source is refined, use a bundle instead of one original document (DEC-2026-11-01-04·05). A folder `planning/<bundle>/` that has an `audit/` folder is a bundle. Planning documents outside a bundle (the format above) stay originals.

| Place | Holds | Injected · shared |
|---|---|---|
| `source/` (or `category: source`) | the original source, never edited | no — evidence |
| `audit/facts*.md` | fact list `# \| source location \| type \| content \| role \| axes \| subtopic` | no — evidence |
| `audit/coverage*.md` | crosswalk `# \| source location \| destination \| note` — seven destinations | no — evidence |
| `audit/defects*.md`, `audit/isolated*.md` | defects (`# \| kind \| content \| handling`), isolated rules | no — evidence |
| `*.md` directly in the bundle | refined documents: `planning_doc: prd \| tech-spec \| terms \| tree` | yes |

- Refined documents carry no code or architecture (tables, columns, schemas; classes, modules, service names; API paths, HTTP codes; frameworks, libraries, vendors). Such facts go to the crosswalk's `code` destination.
- Tables are read by column position, so headers may be in any language. Destinations are written in English (`isolated:` `defect:` `code` `background` `duplicate:#n` `out of scope:`) or Korean (`격리:` `결함:` `코드` `배경` `중복:#n` `범위 밖:`); any other value reads as `<refined document> R<n>`.
- Knowledge search finds refined documents only. `python3 -m kb planning check <bundle>` checks the crosswalk and refined documents; `python3 -m kb planning boundary [--list]` prints the injection boundary.

## Tag namespaces

Every tag should use the `namespace/value` format. Namespaces defined in taxonomy.yaml:

| Namespace | Pattern | Description | Value restriction |
|-------------|------|------|---------|
| `project` | `project/{name}` | Project scope | free |
| `layer` | `layer/{name}` | Strata architecture layer | L1, LM1, L2, LM2, L3, Route, Atomic, Molecule, Partial, Page, Layout, Foundation, Contract, DataState, Primitive_UI, Semantic_Component, Feature_Block, Route_Surface, App_Shell |
| `domain` | `domain/{domain}` | Business domain | free |
| `tech` | `tech/{technology}` | Technology or framework | free |
| `audience` | `audience/{role}` | Target reader | developer, planner, devops, all |

Example: `tags: [project/my-api, layer/L2, domain/auth, tech/jwt]`

Tags without a namespace are also allowed, but the build emits a warning.
Detailed validation rules: `core/templates/vault/_meta/taxonomy.yaml` → `tag_namespaces`, `validation`
