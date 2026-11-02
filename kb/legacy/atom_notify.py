#!/usr/bin/env python3
"""
atom-notify — Claude Code Hook → M5Stack Atom Matrix 알림 (strata/scripts/atom-notify.py 에서 이관, 오더 2026.10.29-11)

사용법:
  python3 "$STRATA_KIT/kb" atom-notify <state>
  python3 "$STRATA_KIT/kb" atom-notify thinking

환경변수:
  ATOM_PORT   시리얼 포트 (기본: /dev/cu.usbserial-8152A2505B)
  ATOM_BAUD   보드레이트 (기본: 115200)
  ATOM_TIMEOUT 응답 대기 시간 초 (기본: 1.0)

종료 코드:
  0 — 항상 (LED 실패해도 hook 플로우 차단 안 함)
"""

import sys
import os
import json

PORT    = os.environ.get("ATOM_PORT",    "/dev/cu.usbserial-8152A2505B")
BAUD    = int(os.environ.get("ATOM_BAUD",    "115200"))
TIMEOUT = float(os.environ.get("ATOM_TIMEOUT", "1.0"))

def notify(state):
    try:
        import serial
    except ImportError:
        # pyserial 없으면 조용히 종료 (hook 플로우 유지)
        sys.exit(0)

    try:
        s = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
        msg = json.dumps({"state": state}) + "\n"
        s.write(msg.encode())
        s.flush()
        # 응답 읽기 (선택적 — 타임아웃 내 수신 시만)
        resp = s.readline().decode("utf-8", "ignore").strip()
        if resp:
            try:
                data = json.loads(resp)
                if not data.get("ok"):
                    pass  # 알 수 없는 state 등 — 조용히 무시
            except Exception:
                pass
        s.close()
    except Exception:
        # 포트 없음, 보드 미연결 등 — hook 플로우 차단 안 함
        pass

def main() -> int:
    state = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "idle"
    notify(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
