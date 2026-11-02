#!/bin/sh
# Clean RED/GREEN in a container (MB-strata-kit-2026-002, order 2026.10.31-04). The host isolated runner
# (run_isolated.sh) still left two traces: the fixture path named strata-kit and the host login's setup. Here the agent
# runs in an image with an empty home, the fixture is mounted at /work, and the only thing passed in is the login token.
# Auto mode refuses unattended agent runs, so a person runs this with `!`.
#
#   docker build -t strata-eval tools/evals/container            # once. If it hangs pulling the base image, the
#     credential helper (credsStore: desktop) is waiting on the keychain — build with a config that has none:
#     D=$(mktemp -d); echo '{}' > $D/config.json; ln -s ~/.docker/cli-plugins $D/; DOCKER_CONFIG=$D docker build ...
#   export CLAUDE_CODE_OAUTH_TOKEN=...                            # from `claude setup-token`; kept in the shell only
#   tools/evals/run_container.sh <out-dir> [model] [scenario ...]   # default: the two unclean round-2 scenarios
#
# Same flags as run_isolated.sh. GREEN puts the skill body in front of the same request (as round 3 did).
# Each run leaves <out>/<scenario>-<variant>.jsonl and the fixture's final state under <out>/fx/.
set -eu
kit=$(cd "$(dirname "$0")/../.." && pwd)
out=$(mkdir -p "$1" && cd "$1" && pwd); model=${2:-sonnet}; shift; [ $# -gt 0 ] && shift
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || { echo "CLAUDE_CODE_OAUTH_TOKEN 없음 — claude setup-token 으로 만들어 export" >&2; exit 2; }
scenarios=${*:-"underspecified-task stale-owner-after-change"}
skill_of() { case $1 in underspecified-task) echo strata.build-task;; stale-owner-after-change) echo strata.kb-update;; *) echo "";; esac; }
ask_of() { case $1 in underspecified-task) echo "please implement task-02";; stale-owner-after-change) echo "update the docs for this change";; *) echo "";; esac; }
python3 "$kit/tools/evals/fixtures.py" "$out/fx" $scenarios >/dev/null
for s in $scenarios; do
  skill=$(skill_of "$s"); ask=$(ask_of "$s")
  [ -n "$skill" ] || { echo "모르는 시나리오: $s" >&2; exit 2; }
  for v in red green; do
    p="$out/$s-$v.prompt"
    if [ "$v" = green ]; then { cat "$kit/skills/$skill/SKILL.md"; printf '\n\n---\n\n'; } > "$p"; else : > "$p"; fi
    printf '%s\n' "$ask" >> "$p"
    docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN -v "$out/fx/$s-$v/work:/work" -v "$p:/prompt.txt:ro" strata-eval \
      sh -c 'claude -p "$(cat /prompt.txt)" --model "$0" --setting-sources project --strict-mcp-config --disable-slash-commands \
        --no-session-persistence --output-format stream-json --verbose \
        --allowedTools Read Edit Write Glob Grep "Bash(git:*)" "Bash(python3:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(head:*)" \
          "Bash(tail:*)" "Bash(grep:*)" "Bash(find:*)" "Bash(wc:*)" "Bash(diff:*)" "Bash(mkdir:*)" "Bash(sed:*)" "Bash(date:*)"' \
      "$model" > "$out/$s-$v.jsonl" 2>&1 || echo "실행 실패: $s $v (기록 $out/$s-$v.jsonl)" >&2
    echo "done $s $v"
  done
done
