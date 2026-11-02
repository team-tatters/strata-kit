# Data Placement

> Canonical: strata-kit `core/docs/en/environment/data-placement.md` (migrated 2026-10-29 from strata `docs/06-environment/data-placement.md`, DEC-2026-10-29-11).

> The single source of truth for **where Strata artifacts live and who tracks them**.
> It gathers rules that were scattered across the cross-model-bridge data table, CLAUDE.md, task-spec-schema, and the local/shared split in 01-context.
> Core principle: **"Sessions are disposable, data lives outside Core, and work history lives outside the project repo."**

## 0. Why this is needed (the problem it solves)

The early design had `.strata/handoffs/` and `.strata/tasks/` **tracked in git in the project repo so that sessions could share them**. As a result:

- **Commit churn**: handoffs and tasks are *work history* that is created and changed in every session, yet they were committed to the code repo for sharing, so the commit rate was abnormally high.
- **Double storage**: a handoff was written to `.strata/handoffs/*.yaml` (repo) and then synced to vault `sessions/*.md`, leaving the original in the repo, so the same information existed in two places.
- **Location drift**: the newer models (shared session ledger, task-spec) already treat the vault as the source of truth, but the old templates/scripts still pointed at `.strata/`, so one artifact had two sources of truth.

The fix is to **move work history out of the project repo (into the vault) and leave only project-specific guidance in the repo**. This finishes the part left incomplete by the decision that already moved the ledger and relay to the vault.

## 1. The 3-Tier boundary

```text
Tier L · local      {project}/.strata/local/        git-ignored   machine-local, volatile runtime state
Tier P · project    {project}/.strata/              git-tracked   project-specific 'guidance' (together with the code)
Tier V · vault      $STRATA_VAULT/projects/{n}/     vault git     work 'history' and collaboration artifacts
```

The classification rule in one line:

> **If it is volatile, it is L; if it is project-specific guidance, it is P; if it is work history or a collaboration artifact, it is V.**

| Tier | Location | git | Nature | Change frequency |
|---|---|---|---|---|
| **L · local** | `{project}/.strata/local/` | Ignored (.gitignore) | Machine-specific, breaks on other machines, regenerable | High (irrelevant because it is not tracked) |
| **P · project SoT** | `{project}/.strata/` (root) | Tracked | This project's architecture and constraints. Must be reviewed in a PR together with the code | Low (only when the architecture changes) |
| **V · vault/shared** | `$STRATA_VAULT/projects/{n}/` | vault git (separate) | History and artifacts shared between sessions and between people. Independent of repo commits | High (no churn because it is outside the repo) |

## 1.5 Placement Profile (embedded | detached)

The **physical location** of Tier P is one of two, depending on the project's repo policy.
The meaning of the Tier (project-specific guidance) and the review obligation are the same; only the location differs. (DEC-2026-08-19-01)

| Profile | Where Tier P is the source of truth | Trace in the repo | When to apply |
|---|---|---|---|
| **embedded** (default) | `{project}/.strata/` — git-tracked | One ignore line for `.strata/local/` | Personal/controlled repos — Tier P can be reviewed in a PR together with the code |
| **detached** | `$STRATA_VAULT/projects/{n}/strata/` — vault git | Only the git-ignored `.strata/local/` (zero commits) | Team repos, etc., where committing `.strata` violates convention |

The **source of truth for the profile is a manifest file** — a pointer kept only on the local machine would not be restored on a new PC (reflecting the cross-review of 2026-08-19):

| Profile | Manifest location | Where it is preserved |
|---|---|---|
| embedded | `{project}/.strata/profile.yaml` (git-tracked) | The project repo — **a new project with no decisions yet can also be identified** |
| detached | `$STRATA_VAULT/projects/{n}/strata/profile.yaml` | The vault — **a new PC restores the profile with just a vault pull** |

```yaml
# profile.yaml — placement profile manifest
profile: detached        # embedded | detached (the repo-side manifest allows only embedded)
project: "{project-name}"
```

`.strata/local/vault-link.yaml` (Tier L, git-ignored) is an **optional local cache** — it is not the SoT, and things work without it.

- **Tier P resolver rules** (common to every consumer that reads Tier P — implementation mapping: `python3 -m kb --help`, `core/docs/en/kb-engine.md`):
  ① repo `.strata/profile.yaml` (embedded declaration) → embedded
  ② repo `.strata/decisions.yaml` or `.strata/decisions/` exists (legacy detection) → embedded
  ③ `.strata/local/vault-link.yaml` (local cache) → detached
  ④ `$STRATA_VAULT/projects/{directory basename}/strata/profile.yaml` → detached (new-PC bootstrap)
  ⑤ If none exist, the project does not use Strata
- The detached Tier P tree: `strata/{profile.yaml, decisions/, decisions.yaml, constraint-registry.yaml, layer-map.yaml}`
- If the repo must be left completely untouched, register `.strata/` in the **global gitignore** (`~/.config/git/ignore`) instead of the team repo's `.gitignore`.
- With detached, continuing a session across PCs is **completed by a single vault pull** (sync hook: DEC-2026-08-19-02).
- A decision that must be shared with the team is promoted to the repo's `docs/`, separately from its vault storage (the same pattern as the API contract promotion rule in §2).

## 2. Placement by artifact (the canonical table)

| Artifact | Tier | Path | Notes |
|---|---|---|---|
| active-task (per session) | L | `.strata/local/active/{session-id}.yaml` | The current state when a session is interrupted (absolute rule). One file per session so that concurrent sessions do not overwrite each other (DEC-2026-08-19-05) |
| session-plan.yaml | L | `.strata/local/session-plan.yaml` | |
| session-log.txt | L | `.strata/local/session-log.txt` | Written by the SessionEnd hook |
| last-compaction.yaml | L | `.strata/local/last-compaction.yaml` | PreCompact snapshot |
| agent-sessions.yaml (session mapping) | L | `.strata/local/agent-sessions.yaml` | claude_id ↔ codex_id, machine-specific |
| **profile manifest** | **P** | `.strata/profile.yaml` (embedded) / vault `strata/profile.yaml` (detached) | Source of truth for the placement profile (§1.5) |
| **decision record** | **P** | `.strata/decisions/DEC-{date}-{NN}-{slug}.yaml` | The decision **source of truth** — one decision = one file. Numbering and recording go through the decision writer CLI (safe for concurrent sessions, DEC-2026-08-19-05) |
| **decisions.yaml (index)** | **P** | `.strata/decisions.yaml` | A **T0 index regenerated from the records**. Never edit by hand |
| **constraint-registry.yaml** | **P** | `.strata/constraint-registry.yaml` | Context constraint registry |
| **layer-map.yaml** | **P** | `.strata/layer-map.yaml` | Mapping used for layer-violation checks |
| cowork DB | L | `.strata/cowork/cowork.sqlite*` | Volatile CoWorking state (including WAL). Persistent promotions go to tasks (V) and decision records (P) |
| ~~shared/~~ | — | `.strata/shared/` | **deprecated** — work history is to be fully migrated to Tier V. Creating new ones is forbidden |
| **handoffs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Same location as the shared session ledger. **Written directly in the vault** |
| **shared session ledger** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` | Context source of truth |
| **tasks (task specs)** | **V** | `$STRATA_VAULT/projects/{n}/tasks/{date}/{nn}-{title}/` | `_order.yaml` + `task-{nn}.yaml` |
| **relay records** | **V** | `$STRATA_VAULT/projects/{n}/relays/` | request/feedback exchange |
| **Hub delivery state** | **L** | `.strata/local/` or the local Hub DB | hub_id, inbox cursor, pull/ack state. Machine- and session-specific |
| **Hub audit projection** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` or `relays/` | Summary of packets/reviews/decisions that a person must pick up |
| **methodology-backlog (project)** | **V** | `$STRATA_VAULT/projects/{n}/backlog/methodology-backlog.yaml` | An operational queue = work-history in nature |
| **exploration-report / draft api-specs** | **V** | `$STRATA_VAULT/projects/{n}/sessions/` (or next to tasks) | Intermediate artifacts handed over between sessions (accepted APIs are promoted — see the note below) |
| **DEC note mirror** (human ADR mirror) | V | `$STRATA_VAULT/projects/{n}/decisions/DEC-{date}-{NN}.md` + `_generated-index.md` | A **mirror for human reading and backlinks**, generated from the records. The source of truth is Tier P. **When generated**: right after `add`, `regen-index` or `migrate` of the decision writer CLI writes the records and index, **in the same run**, the DEC projection generator is called and **fully regenerates** that project's notes (idempotent, removing notes that have no source). The commit is handled by the session-end channel (handoff/ledger close → vault commit+push); use `--sync` for immediate reflection (DEC-2026-08-21-01) |

| **topic node tree (toc.yaml)** | **V** | `$STRATA_VAULT/projects/{n}/_meta/toc.yaml` | The **source of truth** of the human-readable table of contents. It is guidance in nature, but all its consumers (the node page generator, the KB index, the coverage resolver) are on the vault side, and a detached project has nowhere to put it in the repo, so it is V. It is not a change that has to be reviewed together with the code |
| **node pages** | V | `$STRATA_VAULT/projects/{n}/nodes/{node-id}.md` | A **join view** (Index layer, never edit by hand) generated from toc.yaml plus the four-facet frontmatter (spec, constraint, decision, session). **When generated**: the KB index build and the session-end channel (handoff/ledger close) fully regenerate that project's pages in the same run (idempotent, removing pages that have no source). It is not left to a separate manual run — the lesson of the DEC note mirror |

> **A node page is not a source of truth** — the sources of truth for the four facets are, respectively, the specification (V), the Constraint Card (V) and registry (P), the decision record (P), and the session (V); a node page gathers them read-only. The "debt" facet is likewise only an indicator; its source of truth is the very fact that a session document has no `doc_change` declaration.
>
> **The source of truth for decisions is Tier P** — the physical location follows the profile (embedded = repo `.strata/`, detached = vault `projects/{n}/strata/`, §1.5). The vault `projects/{n}/decisions/` holds **DEC notes** generated from the records (for human reading and backlinks, never edit by hand) and is not a machine-readable SoT.
>
> **Role and limits of the DEC note mirror** (DEC-2026-08-21-01): for an embedded project, the source of truth of the records **cannot be read on another machine until the project repo is committed and pushed**. The mirror is a cross-environment supplement that fills this gap through the vault channel; it does not replace the source of truth. Therefore ① the mirror must be generated in **the same run** that records the record (leaving it to a separate manual run leaves it empty — the real case of zero mirrors on a backend project on 2026-08-21), and ② the session-end gates (the handoff generator and the ledger CLI `validate`/`close`) **warn about uncommitted records** in the repo's `.strata/decisions*` (they do not block). A detached project is not a gate target because the records themselves are in the vault and the session-end channel commits them together.
>
> **API contract promotion rule**: `draft api-specs` are Tier V (intermediate hand-over artifacts), but an **accepted API contract** (the moment it becomes the basis for code, clients, and documentation) is not work history but a project artifact → **promote it to Tier P or to the repo's `docs/openapi`**.
>
> **Backlog visibility caution**: the project `methodology-backlog` itself is an operational queue and so Tier V, but **if an accepted item changes Tier P (`decisions`/`constraint-registry`/`layer-map`), that Tier P change must show up in the same PR** (code-review visibility — even when the backlog moves to the vault, *the code reflection of a decision* is reviewed in the repo).

## 3. .gitignore rules (project)

Tier L is excluded and only Tier P is tracked. Tier V is outside the project repo to begin with, so it does not matter.

```gitignore
# Strata — exclude Tier L (local, cowork), track only Tier P (guidance)  [embedded profile]
.strata/local/
.strata/cowork/
.strata/**/*.tmp

# Tier P is tracked explicitly (not excluded):
#   .strata/decisions/  .strata/decisions.yaml
#   .strata/constraint-registry.yaml
#   .strata/layer-map.yaml
```

For the **detached profile**, the principle is not to touch the repo `.gitignore` — register `.strata/` in the global gitignore (`~/.config/git/ignore`) to keep the repo trace at zero (§1.5).

> ⚠️ This is **reversed** from the old rule (tracking `handoffs/` and `tasks/`). It used to be "track them for sharing", but now sharing is the job of the **vault (Tier V)** and the repo does not track them.

## 4. Why this boundary (rationale)

- **Machine-specific data (L) breaks if put in git.** Session IDs and local paths mean nothing on another machine (the same as the local/shared principle of the card `rec.session.state-in-files`).
- **Guidance (P) shares the fate of the code.** Architecture decisions and constraints must be seen together when that code is reviewed or rolled back, so by default they live in the same repo and the same PR (embedded). However, if the team repo's convention does not allow committing `.strata`, move **only the location** to the vault (detached, §1.5) — the nature of the guidance and the review obligation stay the same. Its low change frequency means it creates no churn.
- **History (V) has its own sharing channel.** Handoffs, the ledger, and relays are history that connects sessions and people. This sharing is handled solely by the **vault (its own git/Obsidian sync)**, so there is no reason to put them in the code repo. The code repo is committed only when code or guidance changes.

## 5. Relationship to other documents

- **Vault sync**: handoffs are written directly in the vault (the old double-storage flow of "repo original → vault conversion" is abolished). DEC-2026-10-29-04 decides who writes each vault artifact — DEC notes are built into the decision writer CLI run (§2 table), node pages are written by the librarian (`kb views-publish`), and index metadata is kept per machine.
- **task-spec-schema.md** (`core/docs/en/methodology/task-spec-schema.md`): tasks and backlog are Tier V. This table is the source of truth for paths.
