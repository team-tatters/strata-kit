#!/bin/bash
# Strata 세션 핸드오프 자동화 — vault(Tier V)에 .md 핸드오프 생성 + vault 동기화
# 규격: sync-protocol.md (session-{date}-{slug}.md + type: session frontmatter)
#      slug가 실식별자 (시퀀스 폐지 — DEC-2026-08-19-04, task-01 canonical 규격)
#
# 사용법: python -m kb handoff <slug> [topic]   (strata/scripts/session-handoff.sh 에서 이관 (strata-kit 오더 2026.10.29-01 task-03). strata 쪽 같은 이름은 셔틀.)
#   예:   ./session-handoff.sh vault-restructure "vault 재구조화 Phase 0~2"

set -euo pipefail

case "${1:-}" in
  ""|-*) echo "사용법: python3 \"\$STRATA_KIT/kb\" handoff <slug> [topic] — slug 는 kebab-case, '-' 로 시작할 수 없다" >&2; [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] && exit 0; exit 2 ;;
esac
SLUG="$1"
TOPIC="${2:-}"
case "$SLUG" in
  *[!a-z0-9-]*) echo "오류: slug는 kebab-case ASCII (예: vault-restructure)" >&2; exit 1 ;;
esac

PROJECT_ROOT=$(pwd)
: "${STRATA_VAULT:?STRATA_VAULT 필요 — 핸드오프는 vault(Tier V)에 작성}"
PROJECT_NAME=$(basename "$PROJECT_ROOT")
HANDOFF_DIR="$STRATA_VAULT/projects/$PROJECT_NAME/sessions"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%dT%H:%M:%S)
# 이 기계 별칭: STRATA_ENV, 없으면 ~/.strata/config.yaml machine.alias (MB-strata-kit-2026-049)
MACHINE=$("${STRATA_PYTHON:-python3}" -c 'import sys; sys.path.insert(0, sys.argv[1]); from kb.machine import current_alias; print(current_alias()[0] or "unknown")' "$(cd "$(dirname "$0")/../.." && pwd)" 2>/dev/null || echo "${STRATA_ENV:-unknown}")
KIT=$(cd "$(dirname "$0")/../.." && pwd)

mkdir -p "$HANDOFF_DIR"
HANDOFF_FILE="$HANDOFF_DIR/session-${DATE}-${SLUG}.md"

# 세션 종료 게이트 (DEC-2026-08-21-01): embedded repo .strata/decisions* 에 미커밋 레코드가 있으면 경고.
# vault 동기화는 프로젝트 repo 를 커밋하지 않으므로, 여기서 드러내지 않으면 다른 머신은 정본을 못 읽는다.
# (배경: 2026-08-21 한 프로젝트의 DEC 2건이 빅뱅 커밋에서 누락) — 차단 아님.
PY="${STRATA_PYTHON:-python3}"
"$PY" "$KIT/kb" decision check-uncommitted --project-dir "$PROJECT_ROOT" || true

# 커버리지 게이트 (agent-operations §5.7, DEC-2026-09-08-01): 이 세션의 변경 파일 → 소유 명세·노드.
# 경고만 낸다. 유도된 노드는 아래 frontmatter nodes 에 미리 채운다 (Builder 가 검토·확정).
GATE_NODES="[]"
# 게이트는 한 번만 돌린다 — 보고는 출력하고, 노드 목록·요약 줄은 --save 로 남긴 결과에서 읽는다 (오더 2026.10.31-04)
GATE_JSON=$(mktemp "${TMPDIR:-/tmp}/strata-gate.XXXXXX")
if GATE_OUT=$("$PY" "$KIT/kb" coverage-gate --project-dir "$PROJECT_ROOT" --since "$DATE" --save "$GATE_JSON" 2>/dev/null); then
  echo "$GATE_OUT"
  GATE_NODES=$("$PY" -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("nodes") or [], ensure_ascii=False))' "$GATE_JSON" 2>/dev/null || echo "[]")
  case "$GATE_NODES" in \[*\]) ;; *) GATE_NODES="[]" ;; esac
  # 영향 반경 후보 (오더 2026.10.28-11): '명세 없는 변경 코드 N · 후보 M' 한 줄을 본문에 남긴다.
  # 후보 Inbox 쓰기(--covers-candidates)는 켜지 않는다 — DEC-2026-10-29-03 거르기 뒤 PR 8건 재측정에서 남은 후보 5건이 모두 1표짜리로 약했다.
  # 이 줄의 '새 명세 필요 K'(모듈 묶음)가 지금 쓸모 있는 신호다. 후보 품질이 올라가면(MB-strata-kit-2026-013 covers 정리 뒤) 다시 잰다
  GATE_LINE=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("summary_line") or "")' "$GATE_JSON" 2>/dev/null || true)
  # 등급 판정 (DEC-2026-10-29-08): 훅은 막지 않고 핸드오프가 미해결 default·block 을 no-go 로 드러낸다.
  # 종료 코드로 막지 않는다 — 노드 유도와 핸드오프 생성은 그대로 하고, 본문 머리와 stderr 에 no-go 를 남긴다
  GATE_NOGO=$("$PY" -c '
import json, sys
r = json.load(open(sys.argv[1]))
if r.get("grade_rc"):
    bad = [l for l in (r.get("grades") or []) if l.startswith(("BLOCK", "FAIL"))]
    print(f"no-go — 커버리지 등급 미해결 {len(bad)}건: 명세를 쓰거나(strata.kb-update) Tier P gate-overrides.yaml 에 사유·기한을 남긴 뒤 닫는다")
    for l in r.get("grades") or []:
        print("  " + l.strip())
' "$GATE_JSON" 2>/dev/null || true)
fi
rm -f "$GATE_JSON"
GATE_LINE_MD=""
if [ -n "${GATE_LINE:-}" ]; then
  GATE_LINE_MD="> 커버리지: ${GATE_LINE}"
fi
if [ -n "${GATE_NOGO:-}" ]; then
  echo "$GATE_NOGO" >&2
  GATE_LINE_MD="${GATE_LINE_MD:+$GATE_LINE_MD
}$(printf '%s\n' "$GATE_NOGO" | sed 's/^/> /')"
fi
# 기획과 구현의 어긋남 판정 대기 (DEC-2026-10-31-35) — 판정은 사람만 한다
DV_PENDING=$("$PY" "$KIT/kb" divergence count --project "$PROJECT_NAME" 2>/dev/null || echo 0)
if [ "${DV_PENDING:-0}" != "0" ]; then
  GATE_LINE_MD="${GATE_LINE_MD:+$GATE_LINE_MD
}> 어긋남 판정 대기: ${DV_PENDING}건 — python3 -m kb divergence list --project ${PROJECT_NAME}"
fi

if [ -e "$HANDOFF_FILE" ]; then
  echo "오류: 이미 존재 — $HANDOFF_FILE (다른 slug를 쓰세요)" >&2
  exit 1
fi

# 본문 섹션 제목은 taxonomy document_types.session.body_sections 에서 생성한다 (본문 섹션 리졸버).
# 여기에 제목을 하드코딩하지 않는다 — 2026-09 진단: 스크립트(영문 4종)와 taxonomy(한글 4종)가 어긋나 세션 110건의 헤딩이 발산.
SECTIONS=$("$PY" "$KIT/kb" sections session 2>/dev/null) || SECTIONS=$'완료\n진행 중\n결정 사항\n판단 과정\n사실과 가설\n주의 사항'
# 섹션 제목에 대응하는 기계 판독용 yaml 키 (제목은 사람용, 키는 색인·게이트용).
# 순서가 아니라 제목으로 맞춘다 — 절이 늘면 위치 대응은 블록을 밀어낸다 (판단 과정 절 추가 때 발견, DEC-2026-10-30-03)
section_key() {
  case "$1" in
    완료) echo completed ;;
    "진행 중") echo in_progress ;;
    "결정 사항") echo decisions_made ;;
    "판단 과정") echo judgement ;;
    "사실과 가설") echo findings ;;
    "주의 사항") echo warnings ;;
    *) echo "" ;;
  esac
}

{
cat << EOF
---
title: "session ${DATE} ${SLUG}"
id: "session-${PROJECT_NAME}-${DATE}-${SLUG}"
type: session
project: ${PROJECT_NAME}
machine: ${MACHINE}
created: ${DATE}
topic: "${TOPIC}"
nodes: ${GATE_NODES}   # 커버리지 리졸버가 변경 파일에서 유도 — 검토 후 확정. 코드 변경 없는 세션은 직접 고른다 (toc.yaml)
orders: []        # 이 세션이 실행한 order [[wikilink]] — 스파인 엣지 (DEC-2026-08-19-03)
kb_updates: []    # 이 세션이 갱신한 KB 문서 [[wikilink]]
next_session: null   # 다음 세션 파일명 또는 "none" (사유는 본문 next_session 블록) — null 로 닫지 않는다
# doc_change: none            # 코드는 바꿨으나 최종형상(명세)을 갱신하지 않을 때만 선언 — 빈 값 금지
# doc_change_reason: ""       # none 이면 필수
---

# 세션 핸드오프 — ${DATE} ${SLUG}

> Builder가 아래 섹션을 채운다. 생성: ${TIMESTAMP}
> 섹션 제목은 taxonomy body_sections(session)에서 생성됨 — 제목을 손으로 바꾸지 않는다.
${GATE_LINE_MD}
EOF

while IFS= read -r SEC; do
  [ -n "$SEC" ] || continue
  KEY=$(section_key "$SEC")
  printf '\n## %s\n' "$SEC"
  if [ -n "$KEY" ]; then
    printf '```yaml\n%s: []\n' "$KEY"
    case "$KEY" in
      completed)
        printf '  # - description: ""\n  #   files_created: []\n  #   files_modified: []\n  #   tests_passed: true\n' ;;
      in_progress)
        printf '  # - description: ""\n  #   blocker: ""        # pending 항목에는 blocker + unblocked_by 필수 (절대규칙)\n  #   unblocked_by: ""\n  #   next_steps: []\n' ;;
      decisions_made)
        printf '  # decision writer CLI 로 기록한 DEC id 만 나열 — 상세는 레코드가 정본\n  # - "DEC-YYYY-MM-DD-NN"\n' ;;
      judgement)
        printf '  # 회고 재료 — 사용자에게 물은 것과 답, 뒤집힌 판단과 그 이유 (몇 줄)\n  # - asked: ""\n  #   answered: ""\n  # - reversed: ""\n  #   why: ""\n' ;;
      findings)
        printf '  # 재시작 신호(토큰 경고선·같은 가설 두 번 실패)로 끝난 세션은 채운다 — 다음 세션은 버린 가설을 다시 잡지 않는다 (DEC-2026-10-31-11)\n  # confirmed: []    # 확인된 사실 — 무엇으로 확인했는지와 함께\n  # assumed: []      # 확인하지 못한 추정\n  # discarded: []    # 버린 가설 — 버린 이유와 함께\n' ;;
      warnings)
        printf '  # 다음 세션이 알아야 할 경고·이슈. 형상을 갱신하지 않았으면 doc_change 사유를 여기에도 적는다\n' ;;
    esac
    printf '```\n'
  fi
done <<< "$SECTIONS"

cat << 'EOF'

## next_session
```yaml
next: null        # 다음 세션 파일명 또는 "none" — null 로 닫지 않는다 (agent-operations §5.6)
reason: ""
```
EOF
} > "$HANDOFF_FILE"

echo "📝 핸드오프 생성: $HANDOFF_FILE"
ln -sf "session-${DATE}-${SLUG}.md" "$HANDOFF_DIR/latest.md"

# 노드 페이지 재생성 — 프로젝트 부분 색인(색인 빌더가 끝에 생성기를 호출). 실패해도 진행 (data-placement 노드 페이지 행)
"$PY" "$KIT/kb" build-index --project "$PROJECT_NAME" >/dev/null 2>&1 || true

echo "핸드오프는 vault(Tier V)에 작성됩니다 — 프로젝트 repo 커밋 불필요."
echo "Builder가 내용을 채운 뒤 vault 동기화가 실행됩니다."

# 링크 현행성 (DEC-2026-09-30-03): 핸드오프 생성 시점은 경고만 — 차단은 ledger close 게이트가 한다.
LINK_RC=0; "$PY" "$KIT/kb" link-check --project "$PROJECT_NAME" || LINK_RC=$?
case "$LINK_RC" in
  0) ;;
  1) echo "⚠ 기준선 밖 새 링크 위반 — 세션 종료(ledger close) 전에 고치세요" >&2 ;;
  *) echo "⚠ 링크 검사를 실행하지 못했습니다 (exit $LINK_RC)" >&2 ;;
esac

# DEC-2026-08-19-02: vault 자동 commit+push (실패해도 경고만)
# 생성물(.kb/manifest.json·_index/·노드 페이지)은 세션이 커밋하지 않는다 — 노드 페이지는 librarian 의 kb views-publish 몫 (DEC-2026-10-29-04)
sh "$KIT/kb/legacy/vault_git.sh" commit-push "session ${PROJECT_NAME} ${DATE}: ${TOPIC:-$SLUG}" "projects/${PROJECT_NAME}" ":(exclude)projects/${PROJECT_NAME}/nodes"

echo "✅ 핸드오프 준비 완료"
