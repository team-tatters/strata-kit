---
name: strata.init-wizard
description: Use when a project has no .strata/profile.yaml, when the user asks to set up or refresh agent guidance (AGENTS.md, CLAUDE.md, hooks, Quilt charter), when a profile or card set must be chosen or changed, or when the core revision moved and adapters need regeneration. Keywords - init, set up guidance, which profile, waive a rule, regenerate AGENTS.md, core revision changed.
---

# strata.init-wizard

```yaml
skill:
  id: "strata.init-wizard"
  version: "0.1"
  owner: "builder"
  triggers:
    - "no .strata/profile.yaml in the project"
    - "set up or refresh guidance; choose or change profile or cards"
    - "core revision changed; adapters stale"
  inputs:
    - "project root"
    - "core/cards/*.yaml, core/constitution/constitution.yaml, profiles/*/profile.yaml, skills/registry.yaml"
    - "the user's answers to the interview"
  outputs:
    - ".strata/kit/diagnosis.yaml, .strata/kit/proposal.yaml (reviewed by the user)"
    - "generated adapters: AGENTS.md, CLAUDE.md index, .strata/profile.yaml, .strata/kit/registry.yaml (waivers), Quilt charter/policy drafts"
    - "verification report: budget bytes, drift, trigger test"
  required_context:
    - "core/constitution/constitution.yaml"
    - "LOCALES.md"
  allowed_tools: ["read", "bash(tools/wizard.py)", "write(only paths listed in proposal.yaml)"]
  validation:
    - "every proposed card shows id, strength, and at least one evidence ref"
    - "every waived should card has a reason recorded"
    - "generated files carry core_revision and adapter_revision headers"
    - "tools/wizard.py verify exits 0"
  failure_modes:
    - "a must card is asked to be waived: explain, do not waive, record the pushback as a counter_example candidate"
    - "diagnosis finds two conflicting profiles with no user choice: stop and ask one question"
    - "proposal.yaml not approved: generate nothing"
```

## Overview

The wizard assembles a project's guidance from recommendation cards. It interviews only for what code cannot answer, diagnoses the stack against profile detection rules, proposes cards with their evidence, generates adapters once the user approves, and verifies the result. It is also the path for regeneration when the core revision moves. It never writes outside the paths listed in the approved proposal.

## When to use

- A project has no `.strata/profile.yaml` (using-strata sends you here).
- The user asks for guidance to be set up, changed, or regenerated.
- A profile, card or waiver must change.
- Not for day-to-day work: that is routed by using-strata to the owning skill.

## Process

1. **Diagnose from code first.** Run `python3 tools/wizard.py diagnose <project> --apply`. It reads build files and manifests, matches profile detection rules, measures the always-loaded budget, and lists what it could not decide. Evidence: `.strata/kit/diagnosis.yaml`.
2. **Interview one question at a time.** Ask only the open questions from the diagnosis (team size, expected lifetime, number of domains with cross-domain writes, shared environments, harnesses in use). Never ask what the diagnosis already answered. Record each answer on recommend with `--answer <key>=<value> --because <key>=<reason>` (keys `team_size`, `lifetime`, `cross_domain_writes`, `shared_envs`, `runtime`, `strata_python`); the proposal keeps them under `answers` and the next recommend carries them. **Runtime environment.** Show the diagnosis's `runtime` part — the python each execution path runs (interactive shell, Claude Code hooks, MCP, launchd, non-interactive sh), the missing kit dependencies and the managers and version files found — then ask which python the kit runs on. Present the options with their pros and cons as recommend prints them (`asdf`: many languages in one file, but shims are not on launchd's or a non-interactive PATH so it needs the absolute path; `uv-venv`: isolated, reproducible from the lockfile, installs python, one language; `mise`: asdf-compatible plus env and tasks; `pyenv`; `brew`·`system`: easy, weak pinning and isolation) and the default `uv-venv` with its reason (the kit in a uv venv, the person's language runtime manager kept). Record the choice with `--answer runtime=<choice>`; generate then writes one STRATA_PYTHON into snippet files under `.strata/kit/runtime/` (hooks and settings env, MCP command, launchd EnvironmentVariables, `~/.zshenv` lines) and the person applies them — never edit home files yourself. Evidence: the proposal's `answers` and `runtime`, and `tools/doctor.py` without runtime items after the person applied them.
3. **Propose cards.** Run `python3 tools/wizard.py recommend <project> --profile <id> [--locale ko] --apply`. Present each card as: id, strength, claim, the evidence refs, and counter-examples. Must cards are explained, not negotiated. Opt-in must cards (`adoption: opt_in`, outside the constitution) are asked as questions: the proposal shows each with its default (the user's `wizard.adopt_cards` in `~/.strata/config.yaml`, then the profile's `cards_default`); record the answer with `--adopt <id>` or `--decline <id>=<reason>` (a decline keeps its reason in the proposal and the registry). Conditional must cards (`adoption: conditional`) are not asked: they load whenever their fact holds for the project — `uses_vault` (`--uses-vault yes|no`), `uses_quilt` (`--harness …,quilt`), `domain_work` (the domain); say which loaded and why. Ask the enforcement grade per rule family (`layers`, `naming`, `rules`): advisory records violations only, default fails unless overridden with a reason and an expiry, block fails; undeclared families stay block. Record it with `--enforce <family>=<grade>`; it goes into the manifest, and checkers run through `kb enforce run`. A warning-mode checker that prints violations and exits 0 is wrapped with `--violation-exit 0,1 --violation-pattern <its violation marker>`; a wrong ledger entry is fixed by appending `kb enforce correct`, never by editing. For each should card the user declines, record `waived_reason`. For each pushback on a must card, record a counter_example candidate (it goes to the backlog, not into the project). Without `--apply` (or `--out <dir>`) diagnose and recommend only print. Previous answers come from the last proposal — for a detached project the vault copy (`$STRATA_VAULT/projects/<p>/strata/kit/proposal.yaml`) first — and an answer given now wins. An approved `proposal.yaml` is never replaced: the new proposal goes to `proposal.next.yaml`; show the difference, and once the user agrees, move it over `proposal.yaml` and let them set `approved: true`. Evidence: `.strata/kit/proposal.yaml` with `approved: true` set by the user.
4. **Generate.** Run `python3 tools/wizard.py generate <project> --apply`. It writes only the paths listed in the proposal and stamps `core_revision` and `adapter_revision`. An existing hand-written file (no generated marker at its head) is kept unless the proposal names it in `overwrite_handwritten`; move its text to `.strata/kit/notes.<locale>.md` first. Evidence: the list of written files in the command output.
5. **Verify.** Run `python3 tools/wizard.py verify <project>`. It checks the budget (always-loaded bytes), the revision headers, the registry, and runs five sample requests through the registry triggers. Evidence: exit 0 and the report.
6. **Record.** If the profile choice or a waiver is an architecture decision for this project, record it with the decision writer. Evidence: the DEC id in the reply.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "The stack is obvious, skip diagnose." | Diagnose also measures the budget and finds drift. Run it; it is one command. |
| "The user knows the rules, skip the evidence." | A card without evidence is an opinion. Show the refs; that is the whole point. |
| "This must card does not fit here, waive it." | Must is not waived. Explain it and record the pushback as a counter_example candidate. |
| "Generate everything, they can delete what they do not want." | Write only the approved paths. Unasked files are drift. |
| "Verification passed last time." | The core revision may have moved. Verify after every generate. |

## Red flags

- Interview questions whose answers are in `package.json`, `build.gradle`, `go.mod` or `Cargo.toml`.
- A proposal with a card that has no `evidence` entry.
- A generated AGENTS.md without `core_revision` in its header.
- Files written outside the proposal's path list.

## Verification

- `.strata/kit/proposal.yaml` exists with `approved: true` and every card has evidence.
- Every waived should card has `waived_reason`.
- `tools/wizard.py verify <project>` exits 0 and its report is in the reply.
- Any decision made is recorded and its id is in the reply.
