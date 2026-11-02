#!/usr/bin/env python3
"""
본문 섹션 리졸버 — taxonomy `document_types.{type}.body_sections` 를 돌려준다.

역할 (scripts/README.md): 생성기(핸드오프 스켈레톤·노드 페이지 등)가 본문 제목을 여기서 얻는다.
제목을 스크립트마다 하드코딩하면 taxonomy 와 어긋난다 (2026-09 진단: 핸드오프 스크립트가
영문 4종을 찍고 taxonomy 는 한글 4종을 규정 → 세션 110건 헤딩 발산). One Fact in One File.

해석 순서:
  1. $STRATA_VAULT/_meta/taxonomy.yaml           (운영 인스턴스)
  2. strata-kit core/templates/vault/_meta/taxonomy.yaml  (인스턴스에 body_sections 가 없을 때 폴백)

CLI:
  kb_sections.py <type>            → 섹션 제목을 한 줄씩 출력 (없으면 exit 1)
  kb_sections.py <type> --json     → JSON 배열
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # 훅·생성기에서 조용히 실패하지 않도록 명시
    sys.stderr.write("⚠ Strata: PyYAML 이 없어 body_sections 를 해석할 수 없습니다.\n")
    sys.exit(1)


def _load(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _candidates(vault: str | None) -> list[Path]:
    from kb.legacy._kit import VAULT_TAXONOMY_TEMPLATE
    return ([Path(vault) / "_meta" / "taxonomy.yaml"] if vault else []) + [VAULT_TAXONOMY_TEMPLATE]


def body_sections(doc_type: str, vault: str | None = None) -> list[str]:
    """타입의 본문 섹션 제목 목록. 정의가 없으면 빈 리스트."""
    vault = vault or os.environ.get("STRATA_VAULT")
    for path in _candidates(vault):
        data = _load(path)
        if not data:
            continue
        spec = (data.get("document_types") or {}).get(doc_type) or {}
        sections = spec.get("body_sections")
        if isinstance(sections, list) and sections:
            return [str(s) for s in sections]
    return []


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1].startswith("-"):
        sys.stderr.write("사용법: kb_sections.py <type> [--json]\n")
        return 2
    sections = body_sections(argv[1])
    if not sections:
        sys.stderr.write(f"⚠ body_sections 미정의: type={argv[1]}\n")
        return 1
    if "--json" in argv:
        print(json.dumps(sections, ensure_ascii=False))
    else:
        print("\n".join(sections))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
