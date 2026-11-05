<div align="center">
    <img src="./media/strata-kit-symbol.svg" alt="strata-kit symbol: layers stitched across a fault" width="160" height="160"/>
    <h1>strata-kit</h1>
    <h3><em>Work in layers. Keep the thread.</em></h3>
</div>

<p align="center">
    <a href="https://github.com/team-tatters/strata-kit/stargazers"><img src="https://img.shields.io/github/stars/team-tatters/strata-kit?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/team-tatters/strata-kit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/team-tatters/strata-kit" alt="License: MIT"/></a>
    <img src="https://img.shields.io/badge/python-3.11%2B-3776AB" alt="Python 3.11+"/>
    <img src="https://img.shields.io/badge/agents-Claude_Code_%C2%B7_Codex_%C2%B7_AGENTS.md-263D3A" alt="Agents: Claude Code, Codex, AGENTS.md"/>
    <img src="https://img.shields.io/badge/locales-6-C86646" alt="6 locales"/>
</p>

<p align="center">
    <strong>English</strong> ·
    <a href="./README.ko.md">한국어</a> ·
    <a href="./README.ja.md">日本語</a> ·
    <a href="./README.zh-CN.md">简体中文</a> ·
    <a href="./README.es.md">Español</a> ·
    <a href="./README.fr.md">Français</a>
</p>

strata-kit is a methodology for working with AI coding agents, packaged as a kit. Its centre is the record: every
step of the work is written to a plain Markdown folder (the vault), each topic keeps one document that is updated
in place, and every new session, agent or person starts from those same documents. That is what keeps the work
consistent and lets it continue across sessions, instead of starting over with every chat.

It runs on Claude Code first, and on Codex and any other agent that reads `AGENTS.md` and `SKILL.md`, including
agents you run yourself with an API key.

Author: n0roo · License: [MIT](LICENSE)

## Choose where to start

| You want to | Start with | You get |
|---|---|---|
| Try it on one project | [Quick start](#quick-start) | a vault, the plugin, generated guidance and a first session |
| Understand the idea | [What it gives you](#what-it-gives-you) | records, specifications, cards, skills and checks in one page |
| Pick the rules for your stack | [Profiles](#profiles) | which profiles are proven on a real project and which are drafts |
| Look something up | [Documentation](#documentation) | generated tables of cards, skills, commands and profiles |
| Know the limits first | [Status and limits](#status-and-limits) | what has and has not been measured |

## Who it is for

Mainly developers who work with a coding agent, and most of all engineers who carry a project from plan to
production on their own. Planners, designers and operators take part through the same records: planning documents
and specifications, decisions, and operational signals. The kit does not yet have a full workflow of its own for
those roles, and it has not yet been used by a whole team.

## What it gives you

- **Records that stay current.** The vault keeps three kinds of record. The work log (sessions, tasks, test
  evidence) is only ever added to. Living docs describe how things are now, one per topic, updated in place and
  citing the work log they came from. The index (decision lists, topic pages) is generated from the other two and
  never edited by hand. Decisions are written by a CLI, one file each, and change only through a record that
  replaces them. Each session ends with a handoff that names what is open and what blocks it.
- **Specifications that converge.** Planning documents link to as-built specifications; specifications own code
  through `covers`; a coverage gate reports changed code with no owner and implemented plans whose code moved,
  graded per project (`advisory` · `default` · `block`), with a baseline for gaps that predate adoption.
- **A method you can learn without an agent.** The conventions (layers by role and names by language, plan before
  specification before code, decisions and handoffs in files) are written for agents, but people can learn and
  use them the same way.
- **Cards, not prose rules.** Each card has a claim, a strength (`must` · `should` · `may`), when it applies and when
  it does not, evidence, counter-examples and how to verify it. `must` is not negotiated; `should` can be switched
  off with a recorded reason. Eight base rules apply to every project.
- **Skills that end in evidence.** 16 core skills (entry and routing, init wizard, planning, specification, order,
  build task, verify, review, decision, knowledge update, handoff, distil, translate, retrospective, operations
  signal, security), in six locales, plus optional packs (ideation, design). Each skill says when to use it, what evidence
  ends it, and the excuses an agent reaches for when it wants to skip a step, with the answer to each. Six roles
  (builder, worker, reviewer, supporter, operator, librarian) each have what they may and may not do.
- **Hooks where the app has them, plain files where it does not.** In Claude Code, hooks and cards steer the flow:
  a session-start header shows the project, its `must` cards and the next action read from files, and a hook
  saves state before the context is compacted. Where there are no hooks, the same guidance and skills are plain
  `AGENTS.md` and `SKILL.md` files, and the knowledge-base engine is a command-line tool and an MCP server.
- **Graded checks around the checkers you already have.** `kb enforce run` wraps an existing checker (a layer test,
  dependency-cruiser, a lint) and records every run, so a rule family can be promoted once its numbers are known.

## Documentation

Reference tables generated from the sources: [cards](docs/reference/cards.md) · [skills](docs/reference/skills.md) ·
[commands](docs/reference/cli.md) · [profiles](docs/reference/profiles.md) (Korean: `docs/ko/reference/`). Guides and
concept pages are being written. The full methodology reference for agents is in `core/docs/en/`.

## Layout

```text
core/       base rules (constitution/), recommendation cards, roles, schemas, layer and naming rules, docs (six locales)
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
   git clone https://github.com/team-tatters/strata-kit.git ~/workspace/strata-kit
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
