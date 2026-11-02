"""Document rules shared by every KB view — discovery, frontmatter parsing, heading chunks, taxonomy loading and
validation, shared by the store scanner, the write hook and the taxonomy views.
Functions take the vault root as an argument; nothing here reads the environment at import time."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise SystemExit("PyYAML required") from e

COVERS_KINDS = ("paths", "symbols", "endpoints", "tables")

TYPED_LINK_FIELDS = ("sources", "up", "decisions", "supersedes", "superseded_by", "related")

NODE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)*$")

_TOC_CACHE: dict = {}

SKIP_FILENAMES = {"sortspec.md"}

SKIP_DIRS = {"_meta"}

def load_taxonomy(vault_root: Path, project: str = None) -> dict | None:
    """글로벌 + 프로젝트 taxonomy 병합 로딩. 파일 없으면 None 반환."""
    global_path = vault_root / "_meta" / "taxonomy.yaml"
    if not global_path.exists():
        return None

    with open(global_path) as f:
        taxonomy = yaml.safe_load(f) or {}

    if project:
        proj_path = vault_root / "projects" / project / "_meta" / "taxonomy.yaml"
        if proj_path.exists():
            with open(proj_path) as f:
                proj_tax = yaml.safe_load(f) or {}
            taxonomy = _deep_merge_taxonomy(taxonomy, proj_tax)

    return taxonomy

def _deep_merge_taxonomy(base: dict, override: dict) -> dict:
    """프로젝트 taxonomy를 글로벌에 deep merge.

    병합 규칙:
      - categories.{name}.children → deep merge (추가만)
      - document_types → 추가 가능, 기존 재정의 불가
      - tag_namespaces → 추가 가능
      - validation → override 가능
    """
    merged = copy.deepcopy(base)

    # categories children merge
    if "categories" in override:
        for cat_name, cat_val in override["categories"].items():
            if cat_name in merged.get("categories", {}):
                base_children = merged["categories"][cat_name].get("children", {})
                override_children = cat_val.get("children", {})
                if override_children:
                    base_children.update(override_children)
                    merged["categories"][cat_name]["children"] = base_children
            else:
                merged.setdefault("categories", {})[cat_name] = cat_val

    # document_types merge (추가만, 기존 재정의 불가)
    if "document_types" in override:
        for type_name, type_val in override["document_types"].items():
            if type_name not in merged.get("document_types", {}):
                merged.setdefault("document_types", {})[type_name] = type_val

    # tag_namespaces merge (추가만)
    if "tag_namespaces" in override:
        for ns_name, ns_val in override["tag_namespaces"].items():
            if ns_name not in merged.get("tag_namespaces", {}):
                merged.setdefault("tag_namespaces", {})[ns_name] = ns_val

    # validation override
    if "validation" in override:
        merged.setdefault("validation", {}).update(override["validation"])

    return merged

def parse_kb_path(rel_path: str, taxonomy: dict | None) -> dict:
    """KB 상대 경로에서 분류 정보 추출.

    taxonomy 구조:
      projects/{name}/knowledge-base/{category}/{topic}/{subtopic?}/file.md

    legacy NN-section 구조:
      projects/{name}/knowledge-base/{NN-section}/file.md

    Returns dict with:
      category, topic, subtopic,
      category_order, topic_order,
      section_name, section_order (legacy compat)
    """
    parts = rel_path.split("/")
    try:
        kb_idx = parts.index("knowledge-base")
    except ValueError:
        return _empty_path_info()

    after_kb = parts[kb_idx + 1:]  # [{dir1}, {dir2?}, ..., file.md]
    dirs = after_kb[:-1]  # 파일명 제외한 디렉토리들

    if not dirs:
        return _empty_path_info()

    first_dir = dirs[0]
    categories = taxonomy.get("categories", {}) if taxonomy else {}

    # taxonomy 모드: 첫 디렉토리가 taxonomy 카테고리와 매치
    if taxonomy and first_dir in categories:
        cat_def = categories[first_dir]
        cat_order = cat_def.get("order", 99)
        topic = dirs[1] if len(dirs) > 1 else ""
        subtopic = dirs[2] if len(dirs) > 2 else ""

        # topic_order: taxonomy children 에서 조회, 없으면 알파벳 순 fallback
        children = cat_def.get("children", {})
        topic_order = children.get(topic, {}).get("order", 99) if topic else 0

        return {
            "category": first_dir,
            "topic": topic,
            "subtopic": subtopic,
            "category_order": cat_order,
            "topic_order": topic_order,
            "section_name": first_dir,
            "section_order": cat_order,
        }

    # legacy 모드: NN-{section} 패턴
    section_name = first_dir
    section_order = _section_order_from_dir(section_name)
    return {
        "category": "",
        "topic": "",
        "subtopic": "",
        "category_order": 99,
        "topic_order": 99,
        "section_name": section_name,
        "section_order": section_order,
    }

def _empty_path_info() -> dict:
    return {
        "category": "",
        "topic": "",
        "subtopic": "",
        "category_order": 99,
        "topic_order": 99,
        "section_name": "",
        "section_order": 0,
    }

def _section_order_from_dir(dirname: str) -> int:
    """legacy NN-section 순서 파싱."""
    match = re.match(r"^(\d+)-", dirname)
    return int(match.group(1)) if match else 99

section_order_from_dir = _section_order_from_dir

def validate_document(
    taxonomy: dict | None, fm: dict, path_info: dict, rel_path: str,
    line_count: int | None = None, node_ids: set | None = None,
) -> list:
    """taxonomy 규칙 기반 문서 검증. (severity, action, message) 목록 반환.

    action은 taxonomy validation 설정의 action 필드("warn" | "block") — 2026.08.19-05에서
    실집행: block 위반이 있으면 build가 exit 2 (색인은 기록됨 — CI/훅에서 잡는 용도).
    """
    if not taxonomy:
        return []

    results = []
    val_config = taxonomy.get("validation", {})
    doc_type = fm.get("type", "unknown")
    category = path_info["category"]
    type_def = taxonomy.get("document_types", {}).get(doc_type, {})

    def _add(check: dict, default_sev: str, msg: str):
        results.append((
            check.get("severity", default_sev),
            check.get("action", "warn"),
            msg,
        ))

    # 1. 카테고리-타입 교차 검증
    check = val_config.get("category_type_check", {})
    if check.get("enabled") and category:
        cat_def = taxonomy.get("categories", {}).get(category, {})
        allowed = cat_def.get("defaults", {}).get("allowed_types", [])
        if allowed and doc_type not in allowed:
            _add(check, "warning",
                 f"type '{doc_type}' 은 '{category}' 카테고리에 허용되지 않음"
                 f" (허용: {', '.join(allowed)})")

    # 2. 타입별 필수 필드 검증
    check = val_config.get("required_fields_check", {})
    if check.get("enabled"):
        for field in type_def.get("required_fields", []):
            if not fm.get(field):
                _add(check, "warning", f"type '{doc_type}' 에 '{field}' 필드 필수")

    # 3. 태그 네임스페이스 검증
    check = val_config.get("tag_namespace_check", {})
    if check.get("enabled"):
        namespaces = set(taxonomy.get("tag_namespaces", {}).keys())
        for tag in fm.get("tags", []):
            if "/" in str(tag):
                ns = str(tag).split("/")[0]
                if namespaces and ns not in namespaces:
                    _add(check, "warning",
                         f"태그 '{tag}' 의 네임스페이스 '{ns}' 가 taxonomy에 미정의")

    # 4. depth 제한 검증
    check = val_config.get("depth_limit_check", {})
    if check.get("enabled") and category:
        cat_def = taxonomy.get("categories", {}).get(category, {})
        limit = cat_def.get("depth_limit", 3)
        depth = sum(
            1
            for x in [category, path_info["topic"], path_info["subtopic"]]
            if x
        )
        if depth > limit:
            _add(check, "error", f"'{category}' 최대 depth {limit}, 현재 {depth}")

    # 5. 라이프사이클 규칙 검증 (lifecycle_override 지원 — constraint의 retired 등)
    check = val_config.get("lifecycle_transition_check", {})
    if check.get("enabled"):
        status = fm.get("status", "")
        lifecycle = taxonomy.get("lifecycle", {}).get("statuses", {})
        override = type_def.get("lifecycle_override")
        # lifecycle_override 는 {statuses: [...], default: ...} 형태 (constraint·planning). 예전 코드는 dict 의 키를 허용값으로 읽었다 (2026-09-09 수정)
        if isinstance(override, dict):
            override = override.get("statuses") or []
        if status:
            valid = set(str(s) for s in override) if override else set(lifecycle)
            if valid and status not in valid:
                _add(check, "error",
                     f"type '{doc_type}' 의 status '{status}' 는 허용 집합 밖"
                     f" ({', '.join(sorted(valid))})")
            if status in lifecycle:
                # superseded 상태에는 superseded_by 필수 등
                for field in lifecycle[status].get("required_fields", []):
                    if not fm.get(field):
                        _add(check, "error", f"status '{status}' 에는 '{field}' 필드 필수")

    # 6. 본문 길이 검증 (taxonomy에서 enabled 시에만 — 기본 off)
    check = val_config.get("max_lines_check", {})
    if check.get("enabled") and line_count is not None:
        max_lines = type_def.get("max_lines")
        if max_lines and line_count > max_lines:
            _add(check, "warning",
                 f"type '{doc_type}' 최대 {max_lines}줄, 현재 {line_count}줄")

    # 7·8. 주제 노드·covers 검증 (v3 — node_id_check / covers_path_check)
    results.extend(validate_node_fields(taxonomy, fm, node_ids))

    # 9. doc_change 값 검증 (none 이면 사유 필수 — 빈 값 금지)
    if "doc_change" in fm:
        dc = str(fm.get("doc_change"))
        if dc not in ("none", "updated"):
            results.append(("warning", "warn", f"doc_change 값은 none | updated 만 허용: '{dc}'"))
        elif dc == "none" and not str(fm.get("doc_change_reason") or "").strip():
            results.append(("warning", "warn", "doc_change: none 인데 doc_change_reason 없음"))

    return results

def load_toc_node_ids(vault_root: Path, project: str | None) -> set | None:
    """프로젝트 toc.yaml 의 노드 id 집합(별칭 포함). 파일이 없으면 None. 빌드 중 캐시."""
    if not project:
        return None
    if project in _TOC_CACHE:
        return _TOC_CACHE[project]
    toc_path = vault_root / "projects" / project / "_meta" / "toc.yaml"
    ids = None
    if toc_path.is_file():
        try:
            with open(toc_path, encoding="utf-8") as f:
                toc = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            toc = {}
        ids = set()

        def walk(tree: dict, prefix: str):
            for key, spec in (tree or {}).items():
                nid = f"{prefix}.{key}" if prefix else str(key)
                ids.add(nid)
                if isinstance(spec, dict):
                    for alias in spec.get("aliases") or []:
                        ids.add(str(alias))
                    walk(spec.get("children") or {}, nid)

        walk(toc.get("nodes") or {}, "")
    _TOC_CACHE[project] = ids
    return ids

def validate_node_fields(taxonomy: dict | None, fm: dict, node_ids: set | None) -> list:
    """nodes·covers 필드 검증 (taxonomy validation.node_id_check / covers_path_check). Archive 에도 적용."""
    if not taxonomy:
        return []
    results = []
    val_config = taxonomy.get("validation", {})

    check = val_config.get("node_id_check", {})
    if check.get("enabled"):
        nodes = fm.get("nodes")
        if nodes is not None and not isinstance(nodes, list):
            results.append((check.get("severity", "warning"), check.get("action", "warn"),
                            "nodes 는 리스트여야 함"))
        elif nodes:
            for n in nodes:
                n = str(n)
                if not NODE_ID_RE.match(n):
                    results.append((check.get("severity", "warning"), check.get("action", "warn"),
                                    f"노드 id 형식 위반: '{n}'"))
                elif node_ids is None:
                    results.append((check.get("severity", "warning"), check.get("action", "warn"),
                                    f"toc.yaml 없음 — 노드 '{n}' 검증 불가"))
                    break
                elif n not in node_ids:
                    results.append((check.get("severity", "warning"), check.get("action", "warn"),
                                    f"toc.yaml 에 없는 노드: '{n}'"))

    check = val_config.get("covers_path_check", {})
    covers = fm.get("covers")
    if check.get("enabled") and covers is not None:
        sev, act = check.get("severity", "warning"), check.get("action", "warn")
        if fm.get("type") not in ("specification", "concept"):
            results.append((sev, act, f"covers 는 specification·concept 에만 (type={fm.get('type')})"))
        if not isinstance(covers, dict):
            results.append((sev, act, "covers 는 {paths, symbols, endpoints, tables} 맵이어야 함"))
        else:
            for kind, vals in covers.items():
                if kind not in COVERS_KINDS:
                    results.append((sev, act, f"covers 에 허용되지 않은 키: {kind}"))
                    continue
                if not isinstance(vals, list):
                    results.append((sev, act, f"covers.{kind} 는 리스트여야 함"))
                    continue
                if kind == "paths":
                    for p in vals:
                        p = str(p)
                        if p.startswith(("/", "~")):
                            results.append((sev, act, f"covers.paths 는 저장소 상대경로만: '{p}'"))
                        elif re.search(r"\.(kt|kts|ts|tsx|js|jsx|py|java|go|sql|rs)$", p):
                            results.append((sev, act, f"covers.paths 파일 단위 금지: '{p}'"))
    return results

def _link_target(value) -> str:
    """'[[path|alias]]' 또는 'path' → 'path' (섹션·별칭 제거)."""
    s = str(value).strip()
    m = re.match(r"^\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]$", s)
    if m:
        return m.group(1).strip()
    return s.split("#", 1)[0].strip()

def parse_frontmatter(content: str) -> tuple:
    """YAML frontmatter 파싱. (metadata_dict, body_str) 반환."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(content[3:end])
            except yaml.YAMLError:
                fm = {}
            body = content[end + 3 :].strip()
            return fm or {}, body
    return {}, content

def chunk_by_heading(body: str) -> list:
    """## 이상의 heading 기준으로 section 분할."""
    chunks = []
    lines = body.split("\n")
    current_heading = "(intro)"
    current_lines = []
    heading_level = 0
    line_start = 1

    for i, line in enumerate(lines):
        match = re.match(r"^(#{2,4})\s+(.+)", line)
        if match:
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    chunks.append(
                        {
                            "heading": current_heading,
                            "heading_level": heading_level,
                            "content": text,
                            "line_start": line_start,
                            "line_end": i,
                        }
                    )
            current_heading = match.group(2).strip()
            heading_level = len(match.group(1))
            current_lines = []
            line_start = i + 1
        else:
            current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            chunks.append(
                {
                    "heading": current_heading,
                    "heading_level": heading_level,
                    "content": text,
                    "line_start": line_start,
                    "line_end": len(lines),
                }
            )
    return chunks

def extract_links(content: str) -> list:
    """[[wikilink]] 및 [text](path.md) 추출."""
    wiki = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
    md = [path for _, path in re.findall(r"\[([^\]]+)\]\(([^)]+\.md)\)", content)]
    return wiki + md

def file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def discover_kb_files(vault_root: Path, project: str = None) -> list:
    """vault 내 KB 대상 MD 파일 탐색."""
    results = []
    projects_dir = vault_root / "projects"
    if not projects_dir.exists():
        return results

    # 프로젝트 횡단 Knowledge (core/docs/ko/knowledge-base/vault-structure.md 3계층 표: patterns/, _index/glossary.md) — project 는 'vault'
    # 전체 빌드에서만 포함 (--project 부분 빌드는 해당 프로젝트만). 2026-09-08 discover 범위 공백 해소 (TRACK_BOARD I7)
    if not project:
        # retrospectives/: 개인 회고·회고 학습 노트 (DEC-2026-10-30-06). outputs/ 의 회고 묶음은 생성본이라 넣지 않는다
        # ideas/: 아이디에이션 팩의 아이디어 노트 (DEC-2026-11-01-01) — 프로젝트를 넘는 레퍼런스 검색 대상
        for cross in ("patterns", "retrospectives", "ideas"):
            for md_file in sorted((vault_root / cross).glob("*.md")):
                if md_file.name not in SKIP_FILENAMES and not md_file.is_symlink():
                    results.append((md_file, str(md_file.relative_to(vault_root)), "vault"))
        glossary = vault_root / "_index" / "glossary.md"
        if glossary.is_file():
            results.append((glossary, str(glossary.relative_to(vault_root)), "vault"))

    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        if project and proj_dir.name != project:
            continue

        # 프로젝트 overview.md — Knowledge (update-in-place 대상)
        overview = proj_dir / "overview.md"
        if overview.is_file():
            results.append((overview, str(overview.relative_to(vault_root)), proj_dir.name))

        # Archive 계층 (sessions·tasks) — 메타+요약부 색인 (2026.08.19-06 B1)
        # 기획 문서 (planning) — 원문 전문 색인 + 검증, category=planning (DEC-2026-09-09-01)
        # 리뷰 기록 (reviews) — 원문 전문 색인 + 검증, category=review (DEC-2026-10-30-03)
        # 운영 신호 (signals) — 날짜가 붙은 관찰 기록이라 작업 이력으로 색인 (DEC-2026-11-01-14)
        for sub in ("sessions", "tasks", "planning", "reviews", "signals"):
            arc_dir = proj_dir / sub
            if not arc_dir.exists():
                continue
            for md_file in sorted(arc_dir.rglob("*.md")):
                if md_file.name in SKIP_FILENAMES or md_file.is_symlink():
                    continue  # latest.md 심볼릭 링크 등 중복 방지
                rel = md_file.relative_to(vault_root)
                results.append((md_file, str(rel), proj_dir.name))

        kb_dir = proj_dir / "knowledge-base"
        if not kb_dir.exists():
            continue

        for md_file in sorted(kb_dir.rglob("*.md")):
            if md_file.name in SKIP_FILENAMES:
                continue
            # _meta/ 디렉토리 하위 파일 제외
            rel_to_kb = md_file.relative_to(kb_dir)
            if any(part in SKIP_DIRS for part in rel_to_kb.parts[:-1]):
                continue
            rel = md_file.relative_to(vault_root)
            results.append((md_file, str(rel), proj_dir.name))

    return results
