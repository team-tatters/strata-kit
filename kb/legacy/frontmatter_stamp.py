#!/usr/bin/env python3
"""
Strata PostToolUse Hook: KB frontmatter 스탬프·검증 (역할: "쓰기 훅")

vault 안의 마크다운이 Write/Edit 된 직후 실행된다. 규칙의 정본은
core/docs/ko/knowledge-base/document-format.md("노드·커버리지 필드" 포함)와 taxonomy.yaml 이며, 이 스크립트는 그것을 집행한다.

strata/scripts/kb-frontmatter-stamp.py 에서 이관(오더 2026.10.29-11, MB-strata-kit-2026-011).

호출 방식:
  1. Hook: stdin 으로 Claude Code 공식 JSON — tool_input.file_path 사용  (`python3 "$STRATA_KIT/kb" stamp`)
  2. CLI:  python3 "$STRATA_KIT/kb" stamp <file> [--no-stamp] [--json]

동작:
  - $STRATA_VAULT 밖 / .md 아님 / frontmatter 없음 → 아무것도 하지 않고 exit 0 (빠른 경로)
  - Knowledge 계층(knowledge-base/, patterns/, _index/glossary.md, overview.md)이면
    `updated: 오늘` 스탬프 (갱신 시 updated 필수 — core/docs/ko/knowledge-base/vault-structure.md 3계층 규율)
  - Index 계층(decisions/, nodes/, _index.md, sortspec.md, GENERATED 배너)은 스탬프하지 않고
    "생성 전용 문서 손편집" 경고
  - taxonomy(글로벌 + 프로젝트 확장) 기준 검증 — 전부 경고:
      type 존재 · 타입별 required_fields · status enum(constraint 는 lifecycle_override)
      · status 값 오염(따옴표·인라인 주석) · superseded ↔ superseded_by
      · doc_change none ↔ doc_change_reason · nodes ↔ toc.yaml(node_id_check)
      · covers 구조(specification·concept 만) · Knowledge 문서의 sources

종료 코드: 항상 0. 경고는 hookSpecificOutput.additionalContext 로 에이전트에게, stderr 로 사람에게.
탈출구: KB_NO_STAMP=1 (스탬프만 생략, 검증은 수행) / KB_NO_HOOK=1 (전부 생략)
"""

from __future__ import annotations

import datetime as _dt
import json
import socket
import subprocess
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("⚠ Strata: PyYAML 이 없어 KB frontmatter 검증을 건너뜁니다.\n")
    sys.exit(0)

FM_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|\Z)", re.S)
COVERS_KINDS = {"paths", "symbols", "endpoints", "tables"}
NODE_REQUIRED_TYPES = {"decision", "session", "specification", "concept", "constraint"}   # 폴백 — taxonomy required_fields 에 nodes 가 있는 타입이 정본 (planning 등 신규 타입 자동 반영)
NODE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)*$")
GENERATED_MARK = "GENERATED"


# ---------------------------------------------------------------- 입력 · 경로

def read_target_path(argv: list[str]) -> str | None:
    """CLI 인자 또는 stdin JSON(tool_input.file_path)에서 대상 경로를 얻는다."""
    args = [a for a in argv[1:] if not a.startswith("--")]
    if args:
        return args[0]
    if sys.stdin.isatty():
        return None
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("file_path") or tool_input.get("path")


def vault_root() -> Path | None:
    v = os.environ.get("STRATA_VAULT")
    if v and Path(v).is_dir():
        return Path(v).resolve()
    return None


def classify(rel: Path) -> tuple[str, str | None]:
    """(계층, 프로젝트명). 계층: knowledge | archive | planning | index | other"""
    parts = rel.parts
    project = parts[1] if len(parts) > 2 and parts[0] == "projects" else None
    name = rel.name
    if name in ("_index.md", "sortspec.md"):
        return "index", project
    if parts[0] == "_index":
        return ("knowledge" if name == "glossary.md" else "index"), project
    if parts[0] == "patterns":
        return "knowledge", project
    if project:
        sub = parts[2] if len(parts) > 3 else None
        if sub in ("decisions", "nodes"):
            return "index", project
        if sub in ("sessions", "tasks", "relays"):
            return "archive", project
        if sub == "planning":                      # 기획 문서 — 원문 불변, '구현 검토' 절 갱신 시 updated 스탬프 (DEC-2026-09-09-01)
            return "planning", project
        if sub == "knowledge-base":
            return "knowledge", project
        if len(parts) == 3 and name == "overview.md":
            return "knowledge", project
    return "other", project


# ---------------------------------------------------------------- taxonomy · toc

def _load_yaml(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def _merge(base: dict, ext: dict) -> dict:
    out = dict(base)
    for k, v in ext.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_taxonomy(vault: Path, project: str | None) -> dict | None:
    g = _load_yaml(vault / "_meta" / "taxonomy.yaml")
    if g is None:
        return None
    if project:
        p = _load_yaml(vault / "projects" / project / "_meta" / "taxonomy.yaml")
        if p:
            g = _merge(g, {k: v for k, v in p.items() if k in ("document_types", "validation", "categories", "tag_namespaces")})
    return g


def load_node_ids(vault: Path, project: str | None) -> set[str] | None:
    """toc.yaml 의 노드 id(별칭 포함). 파일이 없으면 None."""
    if not project:
        return None
    toc = _load_yaml(vault / "projects" / project / "_meta" / "toc.yaml")
    if toc is None:
        return None
    ids: set[str] = set()

    def walk(tree: dict, prefix: str) -> None:
        for key, spec in (tree or {}).items():
            nid = f"{prefix}.{key}" if prefix else str(key)
            ids.add(nid)
            if isinstance(spec, dict):
                for alias in spec.get("aliases") or []:
                    ids.add(str(alias))
                walk(spec.get("children") or {}, nid)

    walk(toc.get("nodes") or {}, "")
    return ids


# ---------------------------------------------------------------- 검증

def node_required_types(taxonomy: dict | None) -> set[str]:
    """nodes 가 필수인 타입 — taxonomy document_types.*.required_fields 에서 파생, 없으면 폴백 상수."""
    types = {name for name, spec in ((taxonomy or {}).get("document_types") or {}).items()
             if isinstance(spec, dict) and "nodes" in (spec.get("required_fields") or [])}
    return types or set(NODE_REQUIRED_TYPES)


def validate(fm: dict, raw_fm: str, layer: str, taxonomy: dict | None, node_ids: set[str] | None) -> list[str]:
    warns: list[str] = []
    doc_type = fm.get("type")

    for key in ("title", "type", "created"):
        if key not in fm:
            warns.append(f"필수 필드 누락: {key}")
    if "id" not in fm and layer != "index":
        warns.append("안정 ID 누락: id (core/docs/ko/knowledge-base/vault-structure.md 안정 ID 절)")

    types = (taxonomy or {}).get("document_types") or {}
    spec = types.get(doc_type) if doc_type else None
    if taxonomy and doc_type and spec is None:
        warns.append(f"taxonomy 에 없는 type: {doc_type}")

    if spec:
        for key in spec.get("required_fields") or []:
            if key not in fm:
                warns.append(f"type={doc_type} 필수 필드 누락: {key}")

    # status
    status = fm.get("status")
    if status is not None:
        s = str(status)
        raw_line = next((ln for ln in raw_fm.splitlines() if ln.lstrip().startswith("status:")), "")
        if "#" in raw_line.split("status:", 1)[1]:
            warns.append("status 값에 인라인 주석이 붙어 있음 — 값만 남기고 설명은 본문으로")
        if " " in s or "." in s:
            warns.append(f"status 값이 자유 서술임: {s!r} — lifecycle enum 만 허용")
        allowed = None
        if spec and isinstance(spec.get("lifecycle_override"), dict):
            allowed = set(spec["lifecycle_override"].get("statuses") or [])
        elif taxonomy:
            allowed = set(((taxonomy.get("lifecycle") or {}).get("statuses") or {}).keys())
        if allowed and s not in allowed and layer != "archive":
            warns.append(f"status enum 밖: {s!r} (허용: {', '.join(sorted(allowed))})")
        if s == "superseded" and not fm.get("superseded_by"):
            warns.append("status: superseded 인데 superseded_by 없음")

    # doc_change
    if "doc_change" in fm:
        dc = str(fm.get("doc_change"))
        if dc not in ("none", "updated"):
            warns.append(f"doc_change 값은 none | updated 만 허용: {dc!r}")
        if dc == "none" and not str(fm.get("doc_change_reason") or "").strip():
            warns.append("doc_change: none 인데 doc_change_reason 없음 — 빈 값 금지")

    # nodes
    nodes = fm.get("nodes")
    if doc_type in node_required_types(taxonomy) and "nodes" in fm and nodes == []:
        # 키 자체가 없는 경우는 위 required_fields 검사가 이미 알린다 — 빈 배열만 따로 짚는다
        warns.append("nodes: [] — 주제 노드 소속 필요 (의도적 비움이면 본문에 사유)")
    if nodes:
        if not isinstance(nodes, list):
            warns.append("nodes 는 리스트여야 함")
        else:
            for n in nodes:
                n = str(n)
                if not NODE_ID_RE.match(n):
                    warns.append(f"노드 id 형식 위반: {n!r} (kebab segment 를 점으로 연결)")
                elif node_ids is None:
                    warns.append(f"노드 트리 없음 — projects/{{p}}/_meta/toc.yaml 을 만들어야 {n!r} 를 검증할 수 있음")
                    node_ids = set()  # 같은 경고 반복 방지
                elif node_ids and n not in node_ids:
                    warns.append(f"toc.yaml 에 없는 노드: {n!r}")

    # covers
    covers = fm.get("covers")
    if covers is not None:
        if doc_type not in ("specification", "concept"):
            warns.append(f"covers 는 specification·concept 에만 — type={doc_type}")
        if not isinstance(covers, dict):
            warns.append("covers 는 {paths, symbols, endpoints, tables} 맵이어야 함")
        else:
            bad = set(covers) - COVERS_KINDS
            if bad:
                warns.append(f"covers 에 허용되지 않은 키: {', '.join(sorted(bad))}")
            for kind, vals in covers.items():
                if kind in COVERS_KINDS and not isinstance(vals, list):
                    warns.append(f"covers.{kind} 는 리스트여야 함")
                if kind == "paths":
                    for pth in vals if isinstance(vals, list) else []:
                        p = str(pth)
                        if p.startswith("/") or p.startswith("~"):
                            warns.append(f"covers.paths 는 저장소 상대경로만: {p!r}")
                        elif re.search(r"\.(kt|ts|tsx|js|py|java|go|sql)$", p):
                            warns.append(f"covers.paths 파일 단위 금지(모듈·패키지·라우트 접두 사용): {p!r}")

    # supersedes
    if "supersedes" in fm and doc_type != "decision":
        warns.append(f"supersedes 는 decision 에만 — type={doc_type}")

    # Knowledge 출처
    if layer == "knowledge" and doc_type not in ("moc", "node", "overview", "glossary", "reference") and not fm.get("sources"):
        warns.append("Knowledge 문서에 sources 없음 — 근거 세션·태스크 링크 (DEC-2026-08-19-03)")

    return warns


# ---------------------------------------------------------------- 스탬프

def _set_line(lines: list[str], key: str, value: str, after: tuple[str, ...]) -> bool:
    """frontmatter 줄 목록에서 key 를 value 로. 없으면 after 중 첫 키 뒤에 넣는다. (바뀌었는가)"""
    for i, ln in enumerate(lines):
        if re.match(rf"^{key}:\s*", ln):
            if re.match(rf"^{key}:\s*['\"]?{re.escape(value)}['\"]?\s*(#.*)?$", ln):
                return False
            lines[i] = f"{key}: {value}"
            return True
    for a in after:
        idx = next((i for i, ln in enumerate(lines) if re.match(rf"^{a}:\s*", ln)), None)
        if idx is not None:
            lines.insert(idx + 1, f"{key}: {value}")
            return True
    lines.append(f"{key}: {value}")
    return True


def updated_by_value(vault: Path) -> str:
    """누가 — git identity @ 머신 alias (DEC-2026-09-09-05). 실패하면 OS 사용자."""
    try:
        name = subprocess.run(["git", "config", "user.name"], cwd=str(vault), capture_output=True, text=True).stdout.strip()
    except (OSError, ValueError):
        name = ""
    name = name or os.environ.get("USER") or "unknown"
    machine = os.environ.get("STRATA_ENV") or socket.gethostname().split(".")[0]
    return f"{name}@{machine}"


def stamp_updated(text: str, m: re.Match, today: str, by: str | None = None) -> tuple[str, bool]:
    """frontmatter 의 updated 를 오늘로, updated_by 를 '사람@머신' 으로. (새 본문, 바뀌었는가)"""
    fm_text = m.group(1)
    lines = fm_text.split("\n")
    changed = _set_line(lines, "updated", today, ("created",))
    if by:
        changed = _set_line(lines, "updated_by", by, ("updated", "created")) or changed
    if not changed:
        return text, False
    new_fm = "\n".join(lines)
    return text[: m.start(1)] + new_fm + text[m.end(1):], True


# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    if os.environ.get("KB_NO_HOOK"):
        return 0
    target = read_target_path(argv)
    vault = vault_root()
    if not target or not vault:
        return 0
    path = Path(target)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        path = path.resolve()
        rel = path.relative_to(vault)
    except (ValueError, OSError):
        return 0
    if path.suffix != ".md" or not path.is_file():
        return 0

    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return 0

    layer, project = classify(rel)
    notes: list[str] = []

    try:
        fm = yaml.safe_load(m.group(1)) or {}
        if not isinstance(fm, dict):
            raise yaml.YAMLError("frontmatter 가 매핑이 아님")
    except yaml.YAMLError as e:
        notes.append(f"frontmatter YAML 파싱 실패: {e}")
        return emit(rel, notes, "--json" in argv)

    generated = layer == "index" or fm.get("type") in ("moc", "node") or (GENERATED_MARK in text[m.end():m.end() + 400])
    if generated:
        notes.append("생성 전용(Index 계층) 문서를 손편집함 — 정본에서 재생성되면 사라진다")

    taxonomy = load_taxonomy(vault, project)
    node_ids = load_node_ids(vault, project)
    notes.extend(validate(fm, m.group(1), layer, taxonomy, node_ids))

    today = _dt.date.today().isoformat()
    stamp_layer = layer in ("knowledge", "other", "planning") and fm.get("type") not in ("session", "moc", "node", "decision")
    if stamp_layer and not generated and not os.environ.get("KB_NO_STAMP") and "--no-stamp" not in argv:
        by = updated_by_value(vault)
        new_text, changed = stamp_updated(text, m, today, by)
        if changed:
            path.write_text(new_text, encoding="utf-8")
            notes.insert(0, f"updated 스탬프: {today} · updated_by: {by}")

    return emit(rel, notes, "--json" in argv)


def emit(rel: Path, notes: list[str], as_json: bool) -> int:
    if not notes:
        return 0
    head = f"Strata KB 쓰기 훅 — {rel.as_posix()}"
    body = "\n".join(f"- {n}" for n in notes)
    sys.stderr.write(head + "\n" + body + "\n")
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": head + "\n" + body}}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
