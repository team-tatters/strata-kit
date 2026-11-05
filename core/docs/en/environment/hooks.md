# Hook output: what reaches the agent

A Claude Code hook that cannot check must say so where the agent reads it. Three channels exist, and only two reach
the agent:

| Hook exits | stdout | stderr | The agent sees |
|---|---|---|---|
| 0 | plain text | anything | nothing (stderr goes to the transcript log only) |
| 0 | JSON `{"hookSpecificOutput": {"hookEventName": "<event>", "additionalContext": "…"}}` | anything | the `additionalContext` text |
| 2 | ignored | the message | the stderr text (PostToolUse: after the tool ran; PreToolUse: the call is blocked) |

So a check that prints to stderr and then exits 0 is a silent pass. The kit's own hooks follow this table: the layer
hook (`kb check-layer`) exits 2 on a violation and, when it could not check at all — PyYAML missing in the hook's
python, or no layer rules — exits 0 with `additionalContext` that starts `레이어 검사 안 함` and names the python that
ran it.

## Local hooks written by hand

A project's own PostToolUse hook in `.claude/settings.local.json` often looks like this:

```sh
f=$(cat | "$STRATA_PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")
case "$f" in *.ts|*.tsx|*.css) sh "$STRATA_VAULT/projects/<p>/strata/enforcement/run.sh" diff --file "$f" >&2 || true;; esac
```

It never reaches the agent: findings go to stderr, `|| true` turns every failure into exit 0, and an unset
`STRATA_PYTHON` makes `f` empty so nothing runs at all. Write it so a finding or a failure exits 2:

```sh
py=${STRATA_PYTHON:-}; [ -x "$py" ] || { echo "local hook did not run: STRATA_PYTHON not set — no rule check" >&2; exit 2; }
f=$(cat | "$py" -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")
case "$f" in *.ts|*.tsx|*.css)
  out=$(sh "$STRATA_VAULT/projects/<p>/strata/enforcement/run.sh" diff --file "$f" 2>&1) || { printf '%s\n' "$out" >&2; exit 2; };;
esac
```

If the checker prints advice on success too and that should reach the agent without blocking, print it as the
`additionalContext` JSON on stdout and exit 0 instead.
