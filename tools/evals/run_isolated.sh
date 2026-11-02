#!/bin/sh
# Isolated headless run for a clean RED (order 2026.10.29-10): the agent sees no user CLAUDE.md, no saved memory,
# no skills or plugins, no MCP servers and no STRATA_* variables. Auto-memory is keyed by the working directory,
# so a fresh fixture directory starts empty. Login reuses the existing session (no credential is copied).
#
#   tools/evals/run_isolated.sh <fixture-work-dir> <prompt-file> <transcript.jsonl> [model]
#
# Shell access is limited to the commands the scenarios need; anything else is denied, not asked.
set -eu
work=$1; prompt=$2; out=$3; model=${4:-sonnet}
cd "$work"
env -u STRATA_KIT -u STRATA_VAULT -u STRATA_ENV \
  claude -p "$(cat "$prompt")" --model "$model" \
    --setting-sources project --strict-mcp-config --disable-slash-commands --no-session-persistence \
    --output-format stream-json --verbose \
    --allowedTools "Read" "Edit" "Write" "Glob" "Grep" "Agent" "Task" \
      "Bash(cd:*)" "Bash(git:*)" "Bash(python3:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(head:*)" "Bash(tail:*)" \
      "Bash(grep:*)" "Bash(find:*)" "Bash(wc:*)" "Bash(diff:*)" "Bash(mkdir:*)" "Bash(cp:*)" "Bash(rm:*)" \
      "Bash(touch:*)" "Bash(echo:*)" "Bash(sed:*)" "Bash(env:*)" "Bash(date:*)" "Bash(sort:*)" \
  > "$out" 2>&1
