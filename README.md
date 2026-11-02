# strata-kit

strata-kit is a methodology kit for AI coding agents (Claude Code first, Codex and other harnesses that read
`AGENTS.md` and `SKILL.md`). It keeps the rules of working as **recommendation cards** with claims and evidence,
the procedures as **skills** the agent follows, per-stack **profiles**, and a **guidance wizard** that generates each
project's instructions from those cards and keeps them current. Underneath sits a small knowledge-base engine that
records decisions, handoffs and measurements in a Markdown vault and checks that specifications and code converge.

Author: n0roo · License: [MIT](LICENSE)

## What it gives you

- **Cards, not prose rules.** Each card has a claim, a strength (`must` · `should` · `may`), when it applies and when
  it does not, evidence, counter-examples and how to verify it. `must` is not negotiated; `should` can be switched
  off with a recorded reason. A constitution lists the eight articles every project carries.
- **Skills that end in evidence.** 15 core skills (entry and routing, init wizard, planning, specification, order,
  build task, verify, review, decision, knowledge update, handoff, distil, translate, retrospective, operations
  signal), in six locales, plus optional packs (ideation, design).
- **Specifications that converge.** Planning documents link to as-built specifications; specifications own code
  through `covers`; a coverage gate reports changed code with no owner and implemented plans whose code moved,
  graded per project (`advisory` · `default` · `block`), with a baseline for gaps that predate adoption.
- **Graded checks around the checkers you already have.** `kb enforce run` wraps an existing checker (a layer test,
  dependency-cruiser, a lint) and records every run, so a rule family can be promoted once its numbers are known.
- **Records in files, not in the chat.** Decision records (one file each, written by a CLI), session handoffs with
  blockers, test-time verification evidence.

## Layout

```text
core/       constitution, recommendation cards, roles, schemas, layer and naming rules, docs (six locales)
profiles/   per-stack bundles: card selection, layer-map and checker templates, conventions
skills/     SKILL.md procedures and registry.yaml (the routing table the entry skill reads); packs/
kb/         knowledge-base engine: store, search, gates, decision CLI, MCP server
tools/      wizard, plugin and bundle generators, validators, doctor, metrics, evals runner
adapters/   inputs for the Claude Code plugin and the Codex bundle
i18n/       glossary and pending-translation markers
```

## Profiles

| Profile | Status |
|---|---|
| `core.generic` | active |
| `frontend.next-web` (Next.js / React) | active |
| `backend.kotlin-spring-cqrs` | active |
| `backend.go-service`, `backend.typescript-nest`, `cli.go`, `frontend.swiftui`, `service.rust` | draft |

*Active* means the profile is used on a real project and a checker for its layer rules has run there and left a
record. A draft profile has its documents and rules, but its checkers have not been proven on a project yet.

## Quick start

Requirements: Python 3.11+, git, [uv](https://docs.astral.sh/uv/) for the MCP server, Claude Code for the plugin.

1. Put the kit and a vault in place. The vault is a plain Markdown folder (a git repository is recommended) where
   handoffs, tasks, knowledge documents and measurements live. `kb vault-init` lays one out from the templates in
   `core/templates/vault/`; it never overwrites a file.

   ```sh
   git clone <this repository> ~/workspace/strata-kit
   export STRATA_KIT=~/workspace/strata-kit
   cd "$STRATA_KIT" && uv sync
   python3 "$STRATA_KIT/kb" vault-init ~/workspace/vault --project my-app   # add --detached to keep Tier P in the vault
   export STRATA_VAULT=~/workspace/vault        # required: the engine never guesses a vault path
   ```

2. Build and install the Claude Code plugin.

   ```sh
   python3 "$STRATA_KIT/tools/gen_claude_plugin.py" --locale en
   claude plugin marketplace add "$STRATA_KIT/dist/claude"
   claude plugin install strata-kit@strata-kit
   ```

   It registers the session-start header hook, a pre-compaction snapshot hook, the skills, six role agents and the
   knowledge-base MCP server. For Codex, `tools/gen_codex_bundle.py` writes the skills and role instructions.

3. Generate guidance for a project — or ask the agent "set up strata guidance for this project".

   ```sh
   python3 "$STRATA_KIT/tools/wizard.py" diagnose  <project>
   python3 "$STRATA_KIT/tools/wizard.py" recommend <project> --profile <id> --uses-vault yes
   python3 "$STRATA_KIT/tools/wizard.py" generate  <project> --apply
   python3 "$STRATA_KIT/tools/wizard.py" verify    <project>
   ```

4. Open a session in the project. The header shows the project, its must cards and the next action from files; say
   what you want to do and the entry skill routes it. Say "handoff" to close.

A project can keep strata out of a shared repository entirely (`detached`): guidance and records then live in the
vault, and the repository receives only what its CI runs.

## Status and limits

- Every core skill has pressure scenarios that fail without the skill and pass with it (`skills/*/evals/`).
- Evidence that the method makes work better comes from one person on a small number of projects. It has not been
  reproduced elsewhere, and there is no measurement yet that it beats other ways of working.
- The documentation tree under `core/docs/en/` and the rule files, templates and checker READMEs are in English.
  Many `kb` code comments and some command-line messages are still in Korean.
- Quilt, the orchestrator the kit was built alongside, is an optional adapter (`--harness quilt`); its adapter is not
  in this repository yet. Nothing else depends on it.
- New teams should start with every check at `advisory` and promote a family only after looking at its numbers.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Report security problems as
described in [SECURITY.md](SECURITY.md).

Third-party material is listed in the `NOTICE.md` files next to it (`skills/packs/*/`).
