#!/bin/sh
# vault-git.sh — vault 동기화 훅 (DEC-2026-08-19-02)
#   pull:        세션 시작 시 — git pull --ff-only. 실패(충돌/오프라인)해도 세션을 차단하지 않는다.
#   commit-push MSG [PATH...]: handoff/ledger close 시 — 명시 경로만 stage 해 commit + push. 경로가 없으면 추적 중인 변경만 (add -A 금지, 2026-10-28).
# 항상 exit 0 (훅 원칙: 작업흐름 무저해). 동시 세션은 spinlock으로 직렬화.
# 예외 하나(MB-strata-kit-2026-049): 올릴 세션 기록(projects/*/sessions/*.md)의 machine 이 이 기계 별칭과 다르면
# 그 파일을 커밋하지 않고 exit 3 — 다른 기계 이름으로 남은 기록은 되돌리기 어렵다. STRATA_MACHINE_CHECK=warn 이면 경고만.
#
# 사용: python -m kb vault-git pull   (strata/scripts/vault-git.sh 에서 이관 (strata-kit 오더 2026.10.29-01 task-03). strata 쪽 같은 이름은 셔틀.)
# 사용: vault-git.sh pull
#       vault-git.sh commit-push "session {project} {date}: {topic}"

set -u

# no guessed default: a wrong guess would commit and push some other repository (MB-strata-kit-2026-048)
VAULT="${STRATA_VAULT:-}"
LOCK_DIR="$VAULT/.local/vault-git.lock"
CMD="${1:-}"

warn() { echo "vault-git 경고: $*" >&2; }

[ -n "$VAULT" ] || { warn "STRATA_VAULT 가 설정되지 않음 — vault 동기화 생략"; exit 0; }
[ -d "$VAULT/.git" ] || { warn "vault git repo 아님: $VAULT"; exit 0; }
mkdir -p "$VAULT/.local" 2>/dev/null || true

# spinlock (mkdir는 원자적 — flock 없는 macOS 호환). 최대 30초 대기 후 포기.
acquire() {
  i=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    i=$((i + 1))
    [ "$i" -ge 60 ] && { warn "락 획득 실패(30s) — 건너뜀"; return 1; }
    sleep 0.5
  done
  trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT INT TERM
  return 0
}

case "$CMD" in
  pull)
    acquire || exit 0
    if ! git -C "$VAULT" pull --ff-only --quiet 2>/dev/null; then
      warn "pull --ff-only 실패 (충돌 또는 오프라인) — 세션은 계속 진행. 수동 확인: git -C $VAULT status"
    else
      echo "vault pull 완료"
    fi
    ;;
  commit-push)
    MSG="${2:-vault sync: $(date +%Y-%m-%d)}"
    shift 2 2>/dev/null || shift $#
    acquire || exit 0
    if [ "$#" -gt 0 ]; then
      # 명시 경로만 stage 한다 (rec.kb.session-records-in-vault / 지식 경계 계획 2단계).
      git -C "$VAULT" add -- "$@" 2>/dev/null || warn "일부 경로를 stage 하지 못함: $*"
    else
      # 경로 없이 호출된 레거시 호출자: 추적 중인 변경만 stage 하고, 남긴 미추적 파일을 경고한다. add -A 는 더 쓰지 않는다.
      git -C "$VAULT" add -u 2>/dev/null
      UNTRACKED=$(git -C "$VAULT" ls-files --others --exclude-standard | head -5)
      [ -n "$UNTRACKED" ] && warn "경로 없이 commit-push 호출 — 미추적 파일은 제외됨: $(echo "$UNTRACKED" | tr '\n' ' ')"
    fi
    # 세션 기록의 기계 값 (MB-strata-kit-2026-049): 이 기계 별칭이 아니면 그 파일을 빼고 거부한다
    if [ "$#" -gt 0 ]; then CAND=$(git -C "$VAULT" diff --cached --name-only -- "$@" 2>/dev/null); else CAND=$(git -C "$VAULT" diff --cached --name-only 2>/dev/null); fi
    REFUSED=""
    KIT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
    for f in $(printf '%s\n' "$CAND" | grep -E '^projects/[^/]+/sessions/[^/]+\.md$' || true); do
      [ -f "$VAULT/$f" ] || continue
      if ! "${STRATA_PYTHON:-python3}" "$KIT_DIR/kb" machine check-session "$VAULT/$f"; then
        if [ "${STRATA_MACHINE_CHECK:-}" = "warn" ]; then
          warn "세션 기록의 machine 이 이 기계와 다름(STRATA_MACHINE_CHECK=warn — 그대로 올림): $f"
        else
          git -C "$VAULT" reset --quiet -- "$f" 2>/dev/null
          REFUSED="$REFUSED $f"
        fi
      fi
    done
    if [ -n "$REFUSED" ]; then
      echo "vault-git 거부: 세션 기록의 machine 을 이 기계 별칭으로 고친 뒤 다시 올리세요 —$REFUSED" >&2
      exit 3
    fi
    # 경로가 있으면 그 경로만 커밋한다 — 다른 세션이 stage 해 둔 파일을 함께 올리지 않는다 (DEC-2026-10-29-04)
    if [ "$#" -gt 0 ]; then STAGED=$(git -C "$VAULT" diff --cached --name-only -- "$@" 2>/dev/null); else STAGED=$(git -C "$VAULT" diff --cached --name-only 2>/dev/null); fi
    if [ -n "$STAGED" ]; then
      if git -C "$VAULT" commit --quiet -m "$MSG" -- "$@" 2>/dev/null; then
        echo "vault commit: $MSG ($(git -C "$VAULT" show --stat --format= HEAD | tail -1 | tr -s ' '))"
      else
        warn "commit 실패"
      fi
    fi
    if ! git -C "$VAULT" push --quiet 2>/dev/null; then
      warn "push 실패 (오프라인?) — 다음 동기화 때 재시도됨"
    else
      echo "vault push 완료"
    fi
    ;;
  *)
    echo "사용법: vault-git.sh {pull|commit-push [message]}" >&2
    ;;
esac
exit 0
