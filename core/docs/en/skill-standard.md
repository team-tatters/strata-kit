# Skill standard

A strata-kit skill is a workflow an agent follows, not a reference it skims. The schema in `core/schemas/skill.schema.yaml` fixes the shape; this page explains why each part exists and how to write it.

## Shape

```text
skills/<name>/
├── SKILL.md            English canonical: frontmatter + yaml block + six sections
├── i18n/ko.md …        localized bodies, same section order
├── evals/              pressure scenarios and results (RED / GREEN / REFACTOR)
├── references/         long material the body links to
└── scripts/            bundled tools, run through their interpreter
```

## Frontmatter

`name` is the flat identifier the harness matches. Core skills are `strata.<verb>`; the entry skill is `using-strata`.

`description` is the only thing an agent sees before deciding to open the skill. It starts with "Use when", then lists situations, symptoms and keywords. It never summarizes the workflow: an agent that reads a summary follows the summary instead of the body, and the body is where the checkpoints are.

## The yaml block

Right after the H1 comes a fenced `yaml` block with `id`, `version`, `owner`, `triggers`, `inputs`, `outputs`, `required_context`, `allowed_tools`, `validation`, `failure_modes`. It is the machine-readable twin of the prose and the generator reads it to build adapters and the registry. `validation` maps one-to-one onto the Verification section.

## The six sections

1. **Overview**: one paragraph, what this skill produces.
2. **When to use**: triggers and explicit non-triggers.
3. **Process**: numbered steps. Each step names a checkpoint and the evidence it leaves (a file, a command output, a record id).
4. **Rationalizations**: the excuses an agent uses to skip a step ("this is just a small change", "I remember the rule"), each with a rebuttal. Agents take the shortest path by default; this section is the counterweight.
5. **Red flags**: observable signs that the skill is being skipped or misapplied, written so a reviewer or a gate can detect them.
6. **Verification**: what must be true, and what evidence proves it, before the skill may report completion. "It seems right" is never evidence.

## Writing for the agent

- Prohibitions for steps agents knowingly skip. Templates with required slots for omissions. Conditionals for behaviour that depends on a condition.
- No nuance clauses. "Do not X unless it matters" reopens the negotiation; write the real exceptions as separate conditionals.
- Keep `SKILL.md` under 300 lines. Long reference material goes to `references/` and is linked, so the skill costs few tokens until it is needed.
- One complete, runnable example beats three partial ones.

## Testing a skill

Writing a skill is test-driven development applied to process. Run the scenarios in `evals/` with a subagent that does not have the skill and record what it skipped and how it justified it (RED). Write the minimal skill that addresses those failures and run again (GREEN). Close the loopholes it found and run once more (REFACTOR). Keep the scenario, the transcript summary and the verdict in `evals/`. A skill without a recorded RED run is a draft.

## Localization

Translate the body only. The yaml block, the frontmatter and all identifiers stay English. `en` and `ko` are required before the skill is `active`; the other four locales fall back to English with a warning (see `LOCALES.md`).
