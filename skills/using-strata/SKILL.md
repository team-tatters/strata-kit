---
name: using-strata
description: Use when a session starts, before the first response or action of any kind, including clarifying questions and file reads; and again whenever the task changes shape. Routes the work to the strata skill that owns it and prints the project context (domain, project id, profile, active must cards, next action from files). Keywords - new session, first action, which skill, what applies here, strata.
---

# using-strata

```yaml
skill:
  id: "using-strata"
  version: "0.1"
  owner: "builder"
  triggers:
    - "a session starts, before any response or action"
    - "the task changes shape (new feature, bug, review, deploy, docs)"
  inputs:
    - "skills/registry.yaml (core), profiles/<id>/skills/registry.yaml, the user layer ~/.strata/skills (packs/ and local/), <project>/.strata/kit/registry.yaml (generated) and the Tier P skills/registry.yaml (skill packs, when present)"
    - "<project>/.strata/profile.yaml, constraint registry, latest handoff"
  outputs:
    - "a context header printed to the user (domain, project id, profile, must cards, next action)"
    - "the work mode (read-only, single-session, multi-session, orchestration) and its duties"
    - "the name of the skill that owns the task, invoked next"
  required_context:
    - "core/constitution/constitution.yaml (only when the SessionStart hook printed no header — DEC-2026-10-29-19)"
  allowed_tools: ["read"]
  validation:
    - "the context header was printed before any other action"
    - "a skill was named for the task, or 'none' with the reason"
    - "the work mode is stated (DEC-2026-10-29-15)"
  failure_modes:
    - "no profile manifest found: run strata.init-wizard first"
    - "dispatched as a subagent for a specific task: ignore this skill"
```

## Overview

`using-strata` is the entry point. It does two things and nothing else: it prints where the session is (so the user and the agent share the same facts) and it routes the task to the skill that owns it. It never does the work itself and it never changes; extensions come from the layered registry, not from this file.

## When to use

- At the start of every session, before any response, including a clarifying question, a codebase search or a file read. Questions are tasks.
- Whenever the task changes shape: a bug report in the middle of a feature, a request to deploy, a request to update documentation.
- Not when you were dispatched as a subagent to execute one specific task: then follow the task and ignore this skill.

## Process

1. **Read the project manifest.** Open `.strata/profile.yaml` in the project root. If it is missing, stop and invoke `strata.init-wizard`. Evidence: the manifest path and its `project` value.
2. **Load the registry in layers — only when there is no header.** If the SessionStart hook printed the strata header, it already names the must cards in force and every registry layer with its state: use it, and do not reopen the constitution or the registries in full. Match routes in step 5 against the skill descriptions the harness lists, and open a registry file only when the header shows a profile or project layer with routes of its own. Without the header, do the following. Read `skills/registry.yaml` from strata-kit, then the profile registry, then the project registry (`.strata/kit/registry.yaml`, written by the wizard, and the Tier P `skills/registry.yaml` when the project has skill packs). Open each file; when a layer file does not exist, say "absent" for that layer instead of skipping it. Later layers add routes and override earlier ones by `skill`. Also open every file in this skill's `required_context` (the constitution) rather than relying on a summary of it. Evidence: the list of routes, with the layer each came from, and the required_context paths opened. The user layer (`~/.strata/skills`: kit packs under `packs/`, the person's own skills under `local/`) is read after the profile and before the project; it only adds routes — a name another layer has is refused, except a local skill that names the core skill it replaces with `overrides:`, which the header shows (`python3 -m kb skills check`, DEC-2026-10-31-36).
3. **Print the context header.** Domain (work or personal), project id and aliases, profile id, the must cards in force (ids only), waived should cards with their reasons, and the next action from the latest handoff or active-task file. When the hook printed the header, repeat it and add the work mode; do not rebuild it from files. When neither an active file nor a handoff can be read (variable unset, tool denied, no file), say so and read the repository's own traces — notes such as NOTES or HANDOFF files, `git log`, branches — before asking where the work stands; the header names where it looked. Evidence: the header in the reply, before anything else.
4. **Set the work mode.** If the harness assigned one (a Quilt piece states its mode in its instructions), use it. Otherwise choose: read-only (investigation, questions, review; no file or external state changes), single-session (a change that finishes in this session), multi-session (work that crosses sessions: an order exists or will), orchestration (several sessions or roles working in parallel). Duties: read-only — the header and the route only, no active file or handoff; single-session — active file with `mode` and `harness_session_id` (the harness session id, `CLAUDE_CODE_SESSION_ID` in Claude Code, so the header and the compaction restore find this session's file), verification evidence, decision records, a handoff only when pending items remain; multi-session — also the order and a handoff at every session end; orchestration — also role policies, constraints injected into task files, review packets. A read-only session that is about to change state becomes single-session first. Decision records and confirmation before a state change apply in every mode. Evidence: the mode in the header.
5. **Match the task to a route.** Compare the request with the triggers in the requested locale, falling back to `en`. If any route plausibly applies, name it. If several apply, process skills (`strata.spec`, `strata.order`) go before implementation skills (`strata.build-task`). Evidence: the route and the one-line reason.
6. **Invoke the skill.** Announce "using <skill> because <reason>" and follow it exactly. Create a todo per checklist item of that skill. If after reading it the skill does not fit, say so and return to step 5.

## Rationalizations

| Thought | Rebuttal |
|---|---|
| "This is just a simple question." | Questions are tasks. Print the header and route. It costs one read. |
| "I need more context before I check skills." | The skill check comes before context gathering; a skill tells you what context to gather. |
| "I remember what this skill says." | Skills change with the core revision. Read the current version. |
| "The skill is overkill for this change." | Small changes become large ones. Routing is cheap; skipping a checkpoint is not. |
| "It is read-only, so the header can go." | Read-only drops the files, not the header. The header is what shows the must cards. |
| "The user is in a hurry." | The header is five lines. A wrong route costs more time than printing it. |

## Red flags

- A reply that starts with an answer or an action and no context header.
- Work that proceeds with no named skill and no stated reason.
- A session that edits files in a project with no `.strata/profile.yaml`.
- A must card listed in the header that the following steps then argue around.
- A read-only session that edits a file without first becoming single-session.

## Verification

Before continuing to the routed skill, confirm all of the following and state them in one line:

- The header was printed first and names the project id and profile.
- The registry layers were read, or the hook header stated them, and the route (or "none, because …") is named.
- The work mode is stated.
- The routed skill's `required_context` list is loaded.
