#!/usr/bin/env python3
"""
Strata PreCompact Hook: Compaction 전 상태 스냅샷

Compaction이 발생하기 직전에 실행되어,
현재 진행 중인 작업 상태를 .strata/local/ 파일에 저장합니다 (Tier L — git 제외).

이를 통해 Compaction 후에도 Builder가 상태를 복원할 수 있습니다.

종료 코드:
  0 — 항상 (Compaction을 차단하지 않음)
"""

import os
import sys
import json
import datetime

def get_project_root(start=None):
    """프로젝트 루트 탐색 — .strata 또는 CLAUDE.md 가 있는 가장 가까운 상위"""
    root = start or os.getcwd()
    while root != "/":
        if os.path.isdir(os.path.join(root, ".strata")) or os.path.exists(os.path.join(root, "CLAUDE.md")):
            return root
        root = os.path.dirname(root)
    return start or os.getcwd()

def is_strata_project(project_root):
    """Tier P 가 해석되는 프로젝트만 (플러그인 훅은 모든 프로젝트에서 돈다 — 다른 프로젝트에 .strata 를 만들지 않는다)"""
    try:
        from kb.legacy.strata_paths import resolve_tier_p
        return resolve_tier_p(project_root) is not None
    except Exception:
        return False

def ensure_strata_dir(project_root):
    """'.strata/local/' 디렉토리 존재 보장 (Tier L — git 제외)"""
    strata_dir = os.path.join(project_root, ".strata", "local")
    os.makedirs(strata_dir, exist_ok=True)
    return strata_dir

def active_file(strata_dir, session_id):
    """이 세션의 active 파일 (kb/legacy/active_session.py, 컴팩션 규칙) — 경로와 '없음' 사유.
    다른 세션 파일은 복원 대상으로 쓰지 않는다. 경로가 없으면 (None, 사유)."""
    from pathlib import Path
    from kb.legacy.active_session import pick
    p = pick(Path(strata_dir), session_id, "compact")
    return (str(p.path) if p.path else None), p.label

def decisions_index(project_root):
    """Tier P 인덱스 — detached 면 vault 쪽 (strata_paths resolver)."""
    try:
        from kb.legacy.strata_paths import resolve_tier_p
        tier = resolve_tier_p(project_root)
        if tier is not None:
            return str(tier.decisions_index)
    except Exception:
        pass
    return ".strata/decisions.yaml"

def save_compaction_snapshot(strata_dir, active, decisions, label=""):
    """Compaction 발생 시각과 경고를 기록. active 가 None 이면 '이 세션의 활성 파일 없음'과 사유(label)를 적는다."""
    snapshot_path = os.path.join(strata_dir, "last-compaction.yaml")
    
    now = datetime.datetime.now().isoformat()
    active_rel = (os.path.relpath(active, os.path.dirname(os.path.dirname(strata_dir))) if active
                  else f"(이 세션의 활성 파일 없음 — {label})")
    
    content = f"""# Strata Compaction Snapshot
# 이 파일은 PreCompact Hook에 의해 자동 생성됩니다.
# Builder는 Compaction 후 이 파일을 참조하여 상태를 복원합니다.

compaction:
  occurred_at: "{now}"
  warning: |
    Compaction이 발생했습니다.
    대화 내역이 요약되었을 수 있습니다.
    다음 파일을 참조하여 컨텍스트를 복원하세요:
    - {active_rel}
    - .strata/local/session-plan.yaml
    - {decisions}

recovery_steps:
  - "{active_rel} 에서 현재 진행 중인 태스크 확인"
  - "session-plan.yaml 에서 세션 실행 계획 확인"
  - "decisions.yaml 에서 이번 세션의 결정 사항 확인"
  - "필요한 참조 파일만 최소한으로 다시 로드"
"""
    
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"📸 Strata: Compaction 스냅샷 저장 — {now}")
    print(f"   복원 시 {active_rel} 참조")

def main():
    try:
        hook = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        hook = {}
    hook = hook if isinstance(hook, dict) else {}
    session_id = hook.get("session_id")
    try:   # 컴팩션을 막지 않는다 — 실패는 한 줄로 말하고 0 으로 끝난다
        project_root = get_project_root(hook.get("cwd"))
        if not is_strata_project(project_root):
            return 0
        strata_dir = ensure_strata_dir(project_root)
        active, label = active_file(strata_dir, session_id)
        save_compaction_snapshot(strata_dir, active, decisions_index(project_root), label)
    except Exception as e:
        print(f"strata: compaction snapshot failed — {type(e).__name__}: {e}")
    return 0

if __name__ == "__main__":
    main()
