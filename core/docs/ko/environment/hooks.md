# 훅 출력: 무엇이 에이전트에게 닿는가

검사하지 못한 Claude Code 훅은 그 사실을 에이전트가 읽는 곳에 알려야 한다. 출력 통로는 셋이고, 에이전트에게 닿는 것은 둘이다.

| 훅 종료 코드 | stdout | stderr | 에이전트가 보는 것 |
|---|---|---|---|
| 0 | 일반 텍스트 | 무엇이든 | 없음 (stderr 는 기록 로그에만 남는다) |
| 0 | JSON `{"hookSpecificOutput": {"hookEventName": "<이벤트>", "additionalContext": "…"}}` | 무엇이든 | `additionalContext` 글 |
| 2 | 무시됨 | 메시지 | stderr 글 (PostToolUse: 도구가 실행된 뒤, PreToolUse: 호출이 막힘) |

그래서 stderr 에 찍고 0 으로 끝나는 검사는 조용한 통과다. 키트의 훅은 이 표를 따른다. 레이어 훅(`kb check-layer`)은
위반이면 2 로 끝나고, 아예 검사하지 못했을 때(훅을 실행한 python 에 PyYAML 이 없거나 레이어 규칙이 없을 때)는
`레이어 검사 안 함` 으로 시작하는 `additionalContext` 를 내고 0 으로 끝난다. 메시지에 훅을 실행한 python 경로가 들어간다.

## 손으로 쓴 로컬 훅

프로젝트가 `.claude/settings.local.json` 에 직접 둔 PostToolUse 훅은 흔히 이렇게 생겼다.

```sh
f=$(cat | "$STRATA_PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")
case "$f" in *.ts|*.tsx|*.css) sh "$STRATA_VAULT/projects/<p>/strata/enforcement/run.sh" diff --file "$f" >&2 || true;; esac
```

이 훅의 결과는 에이전트에게 닿지 않는다. 검사 결과가 stderr 로 가고, `|| true` 가 모든 실패를 0 으로 바꾸며,
`STRATA_PYTHON` 이 비어 있으면 `f` 가 비어 아무 검사도 돌지 않는다. 결과나 실패가 있으면 2 로 끝나게 쓴다.

```sh
py=${STRATA_PYTHON:-}; [ -x "$py" ] || { echo "로컬 훅 실행 안 함: STRATA_PYTHON 없음 — 규칙 검사 안 함" >&2; exit 2; }
f=$(cat | "$py" -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))")
case "$f" in *.ts|*.tsx|*.css)
  out=$(sh "$STRATA_VAULT/projects/<p>/strata/enforcement/run.sh" diff --file "$f" 2>&1) || { printf '%s\n' "$out" >&2; exit 2; };;
esac
```

검사기가 성공할 때도 조언을 찍고 그것을 막지 않고 에이전트에게 전하고 싶다면, stdout 에 `additionalContext` JSON 으로 내고 0 으로 끝낸다.
