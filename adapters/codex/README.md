# Codex adapter contract

Codex is the second target harness. It reads a root `AGENTS.md`, invokes skills by name (`$skill`), and accepts developer instructions per thread when driven through Quilt's app-server transport. Its hooks are a reviewed subset, so deterministic checks run in CI, git hooks and the Quilt gate rather than in the harness.

| Kit source | Codex surface | Generator (pending) |
|---|---|---|
| wizard output `AGENTS.md` | root `AGENTS.md` (the universal cross-tool file) | `tools/wizard.py generate` already writes it |
| `skills/*/SKILL.md` (+ `i18n/<locale>.md`) | `.codex/skills/<name>/SKILL.md`, invoked as `$<name>` | `tools/gen_codex_bundle.py` |
| `core/roles/agent-roles.yaml` | developer instructions per role (thread/start), delivered by Quilt | Quilt reads the roles file (see `adapters/quilt/README.md`) |
| must cards | `AGENTS.md` section; also the gate policy when under Quilt | wizard |
| layer and naming checkers | CI jobs and git pre-commit (not Codex hooks) | profile enforcement templates |

Every generated file carries `core_revision`; a Codex session that starts with `using-strata` prints the header and the revision so a stale bundle is visible.
