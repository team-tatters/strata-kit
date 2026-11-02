#!/usr/bin/env python3
"""strata_paths — Tier P 위치 resolver (placement profile 공용 모듈).

정본 규칙: strata-kit core/docs/ko/environment/data-placement.md §1.5 (DEC-2026-08-19-01, cross-review 반영 2026-08-19)

해석 순서 (역할명: Tier P resolver):
  1. repo `.strata/profile.yaml` (git 추적 manifest) — embedded 명시 선언 (신규 프로젝트 bootstrap)
  2. repo `.strata/decisions.yaml` 또는 `.strata/decisions/` 존재 — legacy embedded 감지
  3. repo `.strata/local/vault-link.yaml` — detached 로컬 캐시 (머신 로컬, 선택)
  4. `$STRATA_VAULT/projects/{basename}/strata/profile.yaml` — detached vault manifest
     → 새 PC에서 vault pull만으로 detached가 복원되는 bootstrap 경로 (Finding 1 해소)
  5. 전부 없으면 Strata 미적용 프로젝트 (None)
  git linked worktree 이고 그 안에 `.strata/` 가 없으면(.gitignore 로 제외된 경우) 메인 체크아웃으로 다시 해석한다.

vault 프로젝트 이름(resolve_project_name): profile.yaml project → vault-link 경로 → detached Tier P 의 상위
→ 메인 체크아웃 basename → basename. worktree basename 으로 vault projects/ 가 오염되던 문제의 해소
(strata-feedback/decision-notes-worktree-basename.md).

소비자: decision writer(decision.py), DEC projection generator(gen-decision-notes.py),
        레이어 검증 훅 등 — 매핑: scripts/README.md
"""
from __future__ import annotations

import os
from pathlib import Path


class TierP:
    """resolve 결과 — profile과 Tier P 루트 경로."""

    def __init__(self, profile: str, root: Path):
        self.profile = profile  # "embedded" | "detached"
        self.root = root        # decisions/ 등이 위치하는 디렉토리

    @property
    def decisions_dir(self) -> Path:
        return self.root / "decisions"

    @property
    def decisions_index(self) -> Path:
        return self.root / "decisions.yaml"

    @property
    def constraint_registry(self) -> Path:
        return self.root / "constraint-registry.yaml"

    @property
    def layer_map(self) -> Path:
        return self.root / "layer-map.yaml"

    def __repr__(self) -> str:
        return f"TierP(profile={self.profile!r}, root={str(self.root)!r})"


def _expand(path_str: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path_str)))


def _parse_flat_yaml(f: Path) -> dict:
    """profile.yaml / vault-link.yaml 최소 파서 — 외부 의존 없이 key: value 만 해석."""
    data: dict = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("\"'")
    return data


def _vault_root() -> Path | None:
    v = os.environ.get("STRATA_VAULT")
    return _expand(v) if v else None


def main_worktree(base: Path) -> Path | None:
    """base 가 git linked worktree 이면 메인 체크아웃 경로, 아니면 None (git 실행 없이 .git 파일만 읽는다)."""
    dotgit = base / ".git"
    if not dotgit.is_file():
        return None
    line = dotgit.read_text(encoding="utf-8").strip()
    if not line.startswith("gitdir:"):
        return None
    gitdir = (base / line.split(":", 1)[1].strip()).resolve()
    common = gitdir / "commondir"
    if not common.is_file():
        return None
    common_dir = (gitdir / common.read_text(encoding="utf-8").strip()).resolve()
    return common_dir.parent if common_dir.name == ".git" else None


def resolve_project_name(project_dir: str | os.PathLike | None = None) -> str:
    """vault projects/{name} 의 name. worktree 에서도 메인 프로젝트 이름을 돌려준다."""
    base = Path(project_dir or os.getcwd()).resolve()
    main = main_worktree(base)
    for cand in [base] + ([main] if main else []):
        manifest = cand / ".strata" / "profile.yaml"
        if manifest.is_file():
            name = _parse_flat_yaml(manifest).get("project")
            if name:
                return name
        link = cand / ".strata" / "local" / "vault-link.yaml"
        if link.is_file():
            vault_path = _parse_flat_yaml(link).get("vault_project_path")
            if vault_path:
                return _expand(vault_path).name
    try:
        tier = resolve_tier_p(base)
    except ValueError:
        tier = None
    if tier is not None and tier.profile == "detached" and tier.root.name == "strata":
        return tier.root.parent.name
    return (main or base).name


def resolve_tier_p(project_dir: str | os.PathLike | None = None) -> TierP | None:
    """프로젝트의 Tier P 위치를 해석한다. 미적용 프로젝트면 None."""
    base = Path(project_dir or os.getcwd()).resolve()
    strata_dir = base / ".strata"
    if not strata_dir.is_dir():
        main = main_worktree(base)
        if main is not None:
            return resolve_tier_p(main)

    # 1) repo manifest — embedded 명시 선언 (결정이 아직 없는 신규 프로젝트 포함)
    manifest = strata_dir / "profile.yaml"
    if manifest.is_file():
        profile = _parse_flat_yaml(manifest).get("profile")
        if profile == "embedded":
            return TierP("embedded", strata_dir)
        raise ValueError(
            f"repo manifest의 profile은 embedded만 허용 (detached 선언은 vault manifest): {manifest}")

    # 2) legacy embedded 감지 — Tier P 실물이 repo에 존재
    if (strata_dir / "decisions.yaml").is_file() or (strata_dir / "decisions").is_dir():
        return TierP("embedded", strata_dir)

    # 3) detached 로컬 캐시 (머신 로컬, 선택 — vault manifest보다 빠른 경로일 뿐 SoT 아님)
    link_file = strata_dir / "local" / "vault-link.yaml"
    if link_file.is_file():
        data = _parse_flat_yaml(link_file)
        if data.get("profile") != "detached":
            raise ValueError(f"vault-link.yaml profile이 detached가 아님: {data.get('profile')!r} ({link_file})")
        vault_path = data.get("vault_project_path")
        if not vault_path:
            raise ValueError(f"vault-link.yaml에 vault_project_path 없음 ({link_file})")
        return TierP("detached", _expand(vault_path) / "strata")

    # 4) vault manifest — 새 PC bootstrap: vault pull만으로 detached 복원
    vault = _vault_root()
    if vault is not None:
        cand = vault / "projects" / base.name / "strata" / "profile.yaml"
        if cand.is_file() and _parse_flat_yaml(cand).get("profile") == "detached":
            return TierP("detached", cand.parent)

    return None


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    result = resolve_tier_p(target)
    if result is None:
        print("(strata 미적용 프로젝트)")
        sys.exit(1)
    print(f"profile: {result.profile}")
    print(f"tier_p:  {result.root}")
