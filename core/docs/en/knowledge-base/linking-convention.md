# Knowledge Base — Linking Convention

> Canonical: strata-kit `core/docs/en/knowledge-base/linking-convention.md` (migrated 2026-10-29 from strata `docs/07-knowledge-base/linking-convention.md`, DEC-2026-10-29-11).

## Overview

Links inside the vault put Obsidian compatibility first.
References to anything outside the vault (strata-kit, projects) are based on environment variables.

## Link types

### 1. Links inside the vault — use wikilinks

```markdown
<!-- Reference a document in the same vault -->
[[overview]]
[[decisions/001-use-jwt-auth]]
[[glossary#JWT]]

<!-- Change the display text -->
[[decisions/001-use-jwt-auth|JWT auth decision]]
```

**Rules:**
- Always use `[[wikilink]]` inside the vault
- The path is relative to the vault root
- Omit the `.md` extension
- The relationships are visualized in the Obsidian Graph View

### 2. vault → kit references — environment variable

```markdown
<!-- When a vault document references kit methodology -->
See `$STRATA_KIT/core/rules/layer-rules.yaml` for the layer rules.
```

**Rules:**
- Absolute paths are forbidden
- Always use the `$STRATA_KIT` environment variable
- Keep kit references from vault documents to a minimum (the vault is knowledge, the kit is methodology)

### 3. vault → project references — environment variable

```markdown
<!-- When a vault document references project code -->
Implementation: `$STRATA_PROJECTS/{project-name}/src/auth/AuthService.ts`
```

**Rules:**
- Use the `$STRATA_PROJECTS` environment variable
- Record only the path for code references (never copy code)

### 4. project CLAUDE.md → vault references — @ syntax

```markdown
<!-- When a project CLAUDE.md references the vault -->
Project knowledge: @$STRATA_VAULT/projects/my-api/
```

**Rules:**
- Use Claude Code's `@` lazy-loading syntax
- The path is resolved through the environment variable

### 5. project CLAUDE.md → kit references — @ syntax

```markdown
<!-- When a project CLAUDE.md references the kit -->
Layer rules: @$STRATA_KIT/core/rules/layer-rules.yaml
```

### 6. typed frontmatter link — the kind of relationship as data

A body wikilink only says "related". The **kind** of relationship is written as a frontmatter field (DEC-2026-08-19-03). Generators, validation, and node pages read only these fields and do not read body links.

| Field | Direction | Types that use it | Meaning |
|---|---|---|---|
| `sources` | Knowledge → Archive | KB, pattern | The sessions and tasks this document is based on. Required when Knowledge is updated |
| `up` | child → parent | All documents | The parent concept or MOC that contains this document |
| `decisions` | document → decision | KB, session, task | The decisions this document follows or produced |
| `supersedes` / `superseded_by` | new decision → old decision / old → new | decision | The two ends of a supersession relationship. Validation checks symmetry |
| `nodes` | document → topic node | decision, session, task, specification, concept, constraint | The table-of-contents unit this document belongs to |
| `covers` | specification → code surface | specification, concept | The code paths, symbols, endpoints, and tables for which this document is the **source of truth** |
| `related` | document ↔ document | All documents | A mention or reference relationship. Not ownership |

**Rules:**
- The values of `sources`, `up`, `decisions`, `supersedes`, and `related` are `[[wikilink]]`s. The values of `nodes` are node ids from toc.yaml, and the values of `covers` are repo-relative pointers. Neither is a wikilink.
- Omit a relationship field when it has no value. If you leave an empty array, validation asks whether the emptiness is intentional.
- Writing the same relationship as a body wikilink as well is allowed (for the Obsidian graph). But the source of truth is the frontmatter.
- Sources of truth for value formats: for `nodes`, `covers`, `doc_change`, and `supersedes`, the "node and coverage fields" section of document-format.md; for `sources`, the frontmatter schema of the same document.

### 7. Rules that keep links pointing to the current document (DEC-2026-09-30-03)

- **A wikilink target must resolve by file name (or vault-relative path).** Do not use links that resolve only through the frontmatter `id:` or `aliases` (such as task ids), because they break in Obsidian. When you move or rename a file, keep the old name in `aliases:` (for search and unlinked mentions), but fix the link itself to the new file name as the checker reports it.
- **Do not wrap free text in a link.** A link whose target document does not exist, such as `[[restdocs 양식 정렬]]`, is forbidden. If an explanation is needed, use display text (`[[session-2026-09-02-x|task05 후속]]`).
- **Change body links that point to a superseded document so they point to the current document.** The supersession relationship fields (`supersedes`, `superseded_by`) and sentences that explain history are exceptions. The checker cannot tell the two apart, so this item is reported only as a note (warning).
- **Point to code by symbol rather than by path.** Write class and function names in `covers.symbols`, and in the body too write symbols such as `CollaboratorCommandService.invite`. Write paths only down to the module or package level. This is because symbol names rarely change even when files are moved.
- **Check:** `python3 "$STRATA_KIT/kb" link-check` finds broken wikilinks, free-text links, links that resolve only by id, and body links to superseded documents. Violations in generated or imported documents (DEC notes, node pages, original planning documents, `_index/`) cannot be fixed by hand, so they are only reported and do not block (the place to fix is the generator). The session-end gate looks only at that session's project documents. Existing violations are tied to a baseline (`$STRATA_VAULT/.kb/link-baseline.json`), and the check **fails only when there is a new violation outside the baseline**. Session end (`python3 "$STRATA_KIT/kb" ledger close`) stops the vault sync on this check, while handoff generation (`python3 "$STRATA_KIT/kb" handoff`) only warns. Only in an emergency, downgrade it to a warning with `STRATA_LINK_CHECK=warn`. Shrink the baseline with `--shrink-baseline` as much as you have fixed.
- **Code cross-check:** if you pass `--code-root {project}=<repo>`, it also checks whether the KB `covers.paths` exist in the repository and whether the `covers.symbols` names can be found in the code (only on a machine that has the code repository).

## Prohibitions

| Forbidden pattern | Reason | Alternative |
|---|---|---|
| Absolute paths in the vault (`/home/alice/...`) | Not compatible across machines | Use `$STRATA_KIT`, `$STRATA_VAULT` |
| Markdown links `[text](path)` in the vault | Not shown in the Obsidian Graph | Use `[[wikilink]]` |
| Copying code blocks | Code rot | Record only path references |
| Direct references between projects | Creates a dependency | Extract into a shared pattern in vault/patterns/ |
| Relying on body links alone for the kind of relationship | Generators and validation cannot read it | §6 typed frontmatter link |

The code pointers of `covers` need not be wikilinks. A repo-relative path inside frontmatter is not subject to "no Markdown links in the vault".

## Embeds

Obsidian embed syntax can also be used:

```markdown
<!-- Embed a specific section of another document -->
![[decisions/001-use-jwt-auth#결정]]

<!-- Embed an image -->
![[architecture-diagram.png]]
```

An embed reflects changes in the referenced document automatically, so embedding is recommended over writing duplicates.
