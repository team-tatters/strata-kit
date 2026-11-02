#!/bin/sh
# Baseline comparison (order 2026.10.29-14 task-07, DEC-2026-10-29-16): the same three tasks on the same fixture,
# once with no guidance, no plugin and no kit MCP, and once with strata (wizard guidance + the kit plugin + kit MCP).
# Auto mode refuses unattended headless runs, so a person runs this with `!`.
#
#   tools/evals/run_baseline.sh <out-dir> [model] [tasks]   (tasks: default "read fix resume")
#
# Tasks (fixed — change them only with a decision, or revisions stop being comparable):
#   read    read-only question: where the balance is rounded and how (no file may change)
#   fix     fix over-refunds; success = all tests pass + the hidden check (decision 0003: reject, never clamp)
#   resume  a fresh session told only to continue the previous work (NOTES-previous-session.md is the trail)
# Each run leaves <arm>-<task>.jsonl; tools/metrics.py session reads them; results.yaml collects the rows.
#
# When: after a change that alters what agents do (a constitution version, a skill's process, the entry path), and at
# least once a month otherwise. Keep each run under vault projects/strata-kit/measurements/baseline/<date>-<kit rev>/.
# Day-to-day numbers come from `tools/metrics.py collect <project> --write` (the librarian's daily job; one writer, so
# the shared vault file does not conflict). Not measured yet: injection accuracy (needs review findings that name a
# missed constraint) and edits made through Bash (the transcript only shows Edit/Write as edits).
#
# Same conditions in both arms (DEC-2026-10-29-19): model, --allowedTools, --setting-sources project,
# --strict-mcp-config, --no-session-persistence. The only differences are what strata is: the generated guidance,
# the kit plugin (skills, SessionStart header), the kit MCP server (--mcp-config) and STRATA_KIT. STRATA_VAULT points
# at a scratch vault inside <out-dir> in the strata arm, so nothing a run records reaches the real vault.
set -eu
out=$(mkdir -p "$1" && cd "$1" && pwd); model=${2:-sonnet}; tasks=${3:-"read fix resume"}
kit=$(cd "$(dirname "$0")/../.." && pwd)
TOOLS='Read Edit Write Glob Grep Skill Bash(python3:*) Bash(git:*) Bash(ls:*) Bash(cat:*) Bash(grep:*) Bash(head:*) Bash(tail:*)'
mkdir -p "$out/vault"
printf '{"mcpServers":{"knowledge-base":{"type":"stdio","command":"uv","args":["run","--directory","%s","strata-kb-mcp"],"env":{"STRATA_VAULT":"%s"}}}}\n' "$kit" "$out/vault" > "$out/kit-mcp.json"
prompts() {
  case $1 in
    read)   echo "Where in this project is the account balance rounded, and with which rounding mode? Answer only; do not change files." ;;
    fix)    echo "Refunds larger than the balance currently drive it negative. Fix it and make sure the tests pass." ;;
    resume) echo "Continue the work from the previous session." ;;
  esac
}
for arm in baseline strata; do
  for task in $tasks; do
    root="$out/$arm-$task"; rm -rf "$root"; mkdir -p "$root"
    python3 "$kit/tools/evals/fixtures.py" "$root" baseline-ledger >/dev/null
    work="$root/baseline-ledger-red/work"; rm -rf "$root/baseline-ledger-green"
    prompt="$root/prompt.txt"; prompts "$task" > "$prompt"
    # shellcheck disable=SC2086
    if [ "$arm" = baseline ]; then
      (cd "$work" && env -u STRATA_KIT -u STRATA_VAULT -u STRATA_ENV \
        claude -p "$(cat "$prompt")" --model "$model" --setting-sources project --strict-mcp-config --no-session-persistence \
          --disable-slash-commands --output-format stream-json --verbose --allowedTools $TOOLS \
        > "$out/$arm-$task.jsonl" 2>&1) || true
    else
      python3 "$kit/tools/wizard.py" recommend "$work" --profile core.generic --locale en --domain personal >/dev/null
      sed -i.bak 's/^approved: false$/approved: true/' "$work/.strata/kit/proposal.yaml" && rm -f "$work/.strata/kit/proposal.yaml.bak"
      python3 "$kit/tools/wizard.py" generate "$work" --apply >/dev/null
      (cd "$work" && env STRATA_KIT="$kit" STRATA_VAULT="$out/vault" \
        claude -p "$(cat "$prompt")" --model "$model" --setting-sources project --strict-mcp-config --no-session-persistence \
          --plugin-dir "$kit/dist/claude/strata-kit-en" --mcp-config "$out/kit-mcp.json" \
          --output-format stream-json --verbose --allowedTools $TOOLS \
        > "$out/$arm-$task.jsonl" 2>&1) || true
    fi
    # outcome: files changed, tests, hidden check
    changed=$(git -C "$work" status --porcelain | grep -v '^?? \.strata/\|^?? AGENTS.md\|^?? CLAUDE.md' | wc -l | tr -d ' ')
    tests=$(cd "$work" && python3 -m unittest -q >/dev/null 2>&1 && echo pass || echo fail)
    cp "$kit/tools/evals/baseline_hidden_test.py" "$work/tests/test_hidden.py"
    hidden=$(cd "$work" && python3 -m unittest -q tests.test_hidden >/dev/null 2>&1 && echo pass || echo fail)
    { printf -- "- arm: %s\n  task: %s\n  files_changed: %s\n  tests: %s\n  hidden_check: %s\n" "$arm" "$task" "$changed" "$tests" "$hidden"
      python3 "$kit/tools/metrics.py" session "$out/$arm-$task.jsonl" | sed 's/^/  /'; } >> "$out/results.yaml"
  done
done
echo "results: $out/results.yaml"
