#!/usr/bin/env python3
"""
Strata PostToolUse Hook: 레이어 의존성 위반 검사

호출 방식:
  1. CLI:    python3 check-layer-violation.py <file_path> [project_type]
  2. Hook:   stdin으로 Claude Code 공식 JSON 입력 — tool_input.file_path 사용
             (https://code.claude.com/docs/en/hooks)

종료 코드:
  0 — 위반 없음 또는 검증 불가
  2 — 위반 발견 (Claude에게 피드백 전달)

규칙 위치 우선순위:
  1. strata-kit core/rules/layer-rules.yaml
  2. {project_root}/docs/architecture/layer-rules.yaml (레거시)
"""

import sys
import os
import re
import json
import subprocess

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "⚠ Strata: PyYAML(yaml) 모듈이 없어 검증을 건너뜁니다.\n"
        "   설치: python3 -m pip install pyyaml\n"
        f"   현재 python: {sys.executable}\n"
    )
    sys.exit(0)


HOOK = {"event": "PostToolUse"}   # 실제로 호출된 이벤트 — additionalContext 는 그 이름으로 적어야 전달된다


def notify_agent(message):
    """exit 0 의 stderr 는 에이전트에게 전달되지 않는다 — additionalContext 로 알리고 stderr 로 사람에게도 남긴다.
    hookEventName 은 호출된 이벤트(PreToolUse·PostToolUse)다 (planning/hook-zones-exceptions)."""
    sys.stderr.write(message + "\n")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": HOOK["event"], "additionalContext": message}},
                     ensure_ascii=False))


def resolve_project_type(project_type, project_root):
    """STRATA_PROJECT_TYPE(또는 CLI 인자)가 없으면 layer-map 의 project_type, 그다음 variant(web·mobile → frontend), 끝으로 backend."""
    if project_type:
        return project_type
    m = load_project_layer_map(project_root) or {}
    if m.get("project_type"):
        return m["project_type"]
    if m.get("variant") in ("web", "mobile"):
        return "frontend"
    return "backend"


def zone_and_exceptions(file_path, layer_map):
    """layer-map 의 legacy 존 여부와 쓸 수 있는 예외 — CI(depcruise-layers.core·StrataLayerMapTest·check-swift-layers)와 같은 뜻:
    존은 부분 문자열 일치, 예외는 status 가 retired 가 아니면 유효(DEC-2026-10-31-20·21). 형식이 깨졌으면 그 사실을 돌려준다."""
    m = layer_map or {}
    problems = []
    zones = m.get("zones") or {}
    legacy = zones.get("legacy") if isinstance(zones, dict) else None
    if legacy is not None and not (isinstance(legacy, list) and all(isinstance(x, str) for x in legacy)):
        problems.append("zones.legacy 가 경로 문자열 목록이 아님")
        legacy = []
    in_legacy = any(z and z in file_path for z in (legacy or []))
    exc = m.get("exceptions") or []
    if not isinstance(exc, list) or not all(isinstance(e, dict) for e in exc):
        problems.append("exceptions 가 항목 목록이 아님")
        exc = []
    live = [e for e in exc if e.get("status") != "retired" and e.get("from_path") and e.get("from_path") in file_path]
    return in_legacy, live, problems


def find_strata_root():
    """규칙 디렉터리 — strata-kit core/rules."""
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "core", "rules")
    return d if os.path.isdir(d) else None


def find_project_root():
    cwd = os.getcwd()
    while cwd != "/":
        for marker in ("AGENTS.md", "CLAUDE.md", ".strata"):
            if os.path.exists(os.path.join(cwd, marker)):
                return cwd
        cwd = os.path.dirname(cwd)
    return os.getcwd()


def load_layer_rules(strata_root, project_root):
    candidates = []
    if strata_root:
        candidates.append(os.path.join(strata_root, "layer-rules.yaml"))
    candidates.append(os.path.join(project_root, "docs", "architecture", "layer-rules.yaml"))
    for c in candidates:
        if not c or not os.path.exists(c):
            continue
        with open(c, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return None


def _layer_map_path(project_root):
    """repo .strata/layer-map.yaml, 없으면 Tier P(detached 는 vault projects/<p>/strata/) — 오더 2026.10.29-02 task-04.
    detached 전환(한 백엔드 프로젝트, 2026-10-28) 뒤 repo 에 맵이 없어 훅이 조용히 아무것도 검사하지 않던 결함."""
    path = os.path.join(project_root, ".strata", "layer-map.yaml")
    if os.path.exists(path):
        return path
    try:
        from kb.legacy.strata_paths import resolve_tier_p
        tier = resolve_tier_p(project_root)
    except Exception:  # noqa: BLE001 — 해석 실패는 맵 없음과 같다
        tier = None
    if tier is not None and (tier.root / "layer-map.yaml").is_file():
        return str(tier.root / "layer-map.yaml")
    return None


def load_project_layer_map(project_root):
    """프로젝트별 layer_map (기계 판독용). 없으면 None."""
    if not project_root:
        return None
    path = _layer_map_path(project_root)
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# PreToolUse: 아직 쓰이지 않은 내용으로 검사한다 (경로 → 쓰일 내용)
CONTENT_OVERRIDE = {}


def _read(file_path):
    key = os.path.abspath(file_path)
    if key in CONTENT_OVERRIDE:
        return CONTENT_OVERRIDE[key]
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def proposed_content(tool_name, tool_input):
    """Write·Edit·MultiEdit 가 적용된 뒤의 파일 내용. 다른 도구면 None."""
    path = tool_input.get("file_path") or ""
    if tool_name == "Write":
        return tool_input.get("content")
    if tool_name not in ("Edit", "MultiEdit"):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    edits = tool_input.get("edits") if tool_name == "MultiEdit" else [tool_input]
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def _normalize_project_type(project_type, rules):
    if not rules:
        return project_type
    if project_type in rules:
        return project_type
    aliases = {
        "backend-jvm": "backend",
        "backend-go": "backend_go",
        "frontend-next": "frontend",
        "frontend-react": "frontend",
        "fullstack": "backend",
    }
    return aliases.get(project_type, "backend" if "backend" in rules else next(iter(rules.keys()), project_type))


def _project_variant(project_root, project_type):
    layer_map = load_project_layer_map(project_root)
    if not layer_map:
        return None, False
    key = _normalize_project_type(project_type, {project_type: {}})
    variant = (
        layer_map.get("variant")
        or layer_map.get(f"{key}_variant")
        or layer_map.get("variants", {}).get(key)
    )
    return variant, variant is not None


def _stack_for_project(rules, project_type, project_root=None):
    key = _normalize_project_type(project_type, rules)
    stack = rules.get(key, rules.get("backend", {}))
    variants = stack.get("variants", {})
    project_variant, explicit = _project_variant(project_root, key)
    variant = project_variant or stack.get("variant") or stack.get("default_variant")
    if variant and variant in variants:
        return variants[variant], variant, explicit
    if explicit:
        return {}, variant, explicit
    return stack, None, explicit


def _compat_stack(rules, project_type):
    key = _normalize_project_type(project_type, rules)
    return rules.get(key, rules.get("backend", {}))


def _resolve_layer_config(layer_name, rules, project_type, project_root=None):
    """Core layer-rules에서 해당 layer의 config(can_reference 등)를 찾는다."""
    if not rules or not layer_name:
        return {}
    stack, _, explicit = _stack_for_project(rules, project_type, project_root)
    layers = stack.get("layers", {}) or {}
    if layer_name in layers:
        return layers.get(layer_name, {}) or {}
    if not explicit:
        compat_layers = _compat_stack(rules, project_type).get("layers", {}) or {}
        return compat_layers.get(layer_name, {}) or {}
    return {}


def identify_layer_from_map(file_path, layer_map):
    """프로젝트 layer-map.yaml에서 우선 매칭. _로 시작하는 layer는 검증 제외."""
    if not layer_map:
        return None
    mappings = layer_map.get("mappings", [])
    for m in mappings:
        path_marker = m.get("path", "")
        if path_marker and path_marker in file_path:
            return m.get("layer")
    return None


def identify_layer(file_path, rules, project_type, project_root=None):
    """레이어 식별. 우선순위:
       1) 프로젝트 .strata/layer-map.yaml (기계 판독)
       2) Core layer-rules.yaml의 directory 필드
       반환: (layer_name, layer_config)
       layer_name이 '_'로 시작하면 검증 대상 외 (검증 스킵 시그널).
    """
    # 1) 프로젝트 layer-map 우선
    if project_root:
        layer_map = load_project_layer_map(project_root)
        layer_name = identify_layer_from_map(file_path, layer_map)
        if layer_name:
            if layer_name.startswith("_"):
                return layer_name, {}, {}  # 스킵 마커
            if not rules:
                return layer_name, {}, {}
            layer_config = _resolve_layer_config(layer_name, rules, project_type, project_root)
            active_layers = _active_layers_for(layer_name, rules, project_type, project_root)
            return layer_name, layer_config, active_layers

    # 2) Core fallback
    if not rules:
        return None, None, None
    stack, _, _ = _stack_for_project(rules, project_type, project_root)
    layers = stack.get("layers", {}) or {}
    for layer_name, layer_config in layers.items():
        directory = layer_config.get("directory", "")
        if directory and directory in file_path:
            return layer_name, layer_config, layers

    return None, None, None


def _active_layers_for(layer_name, rules, project_type, project_root=None):
    stack, _, explicit = _stack_for_project(rules, project_type, project_root)
    layers = stack.get("layers", {}) or {}
    if layer_name in layers:
        return layers
    if not explicit:
        compat_layers = _compat_stack(rules, project_type).get("layers", {}) or {}
        if layer_name in compat_layers:
            return compat_layers
    return layers


def extract_imports(file_path):
    if not os.path.exists(file_path) and os.path.abspath(file_path) not in CONTENT_OVERRIDE:
        return []

    imports = []
    content = _read(file_path)

    if file_path.endswith(".go"):
        # Go: import "a/b" · import alias "a/b" · import ( "a" \n alias "b" )
        for block in re.findall(r'import\s*\((.*?)\)', content, re.S):
            imports.extend(re.findall(r'^\s*(?:[\w.]+\s+)?"([^"]+)"', block, re.M))
        imports.extend(re.findall(r'^import\s+(?:[\w.]+\s+)?"([^"]+)"', content, re.M))
        return imports

    if file_path.endswith(JS_EXT):
        # import … from 'x' (also across lines and `import type`), export … from 'x', side-effect import 'x'
        imports.extend(re.findall(r'^\s*(?:import|export)\s+(?:type\s+)?[^;\'"]*?\bfrom\s+[\'"]([^\'"]+)[\'"]', content, re.M | re.S))
        imports.extend(re.findall(r'^\s*import\s+[\'"]([^\'"]+)[\'"]', content, re.M))
        return list(dict.fromkeys(imports))

    ts_pattern = r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]'
    imports.extend(re.findall(ts_pattern, content))

    jvm_pattern = r'import\s+([\w.]+)'
    imports.extend(re.findall(jvm_pattern, content))

    py_pattern = r'from\s+([\w.]+)\s+import'
    imports.extend(re.findall(py_pattern, content))

    return imports


JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def check_violations(file_path, layer_name, layer_config, active_layers, feature_root=None, layer_map=None, project_root=None):
    """TS/JS with a layer-map: each import is resolved to a path (relative, tsconfig paths, workspace package) and the
    layer-map mappings name its layer — the way dependency-cruiser does in CI (MB-strata-kit-2026-041), so an alias
    import is checked like a relative one. An import that does not resolve and every other language fall back to the
    old guess (imports starting with './' or 'src/', target layer from layer-rules directory names)."""
    violations = []
    can_reference = layer_config.get("can_reference", [])
    cross_reference = layer_config.get("cross_reference", True)
    layers = active_layers or {}
    by_map = bool(layer_map and layer_map.get("mappings")) and file_path.endswith(JS_EXT) and project_root

    for imp in extract_imports(file_path):
        if by_map:
            from kb.legacy.import_resolver import as_file, resolve
            target = resolve(imp, file_path, project_root)
            if target is not None:
                target = as_file(target)
                if not target.endswith(JS_EXT):
                    continue   # styles, images, json: not a module of any layer (CI resolves code only)
                t_layer = identify_layer_from_map(target, layer_map)
                if not t_layer or t_layer.startswith("_") or t_layer not in layers:
                    continue
                if t_layer == layer_name:
                    # same layer: CI isolates Feature_Block domains under feature_root; the hook does so for any layer
                    # that forbids cross references, only when both paths sit under feature_root
                    if not cross_reference and feature_root and feature_root in file_path and feature_root in target:
                        a, b = extract_domain(file_path, feature_root), extract_domain(target, feature_root)
                        if a and b and a != b:
                            violations.append({"import": imp, "target_layer": t_layer, "type": "cross_reference",
                                               "message": f"{layer_name} 간 상호참조 위반: {a} → {b}"})
                elif t_layer not in can_reference:
                    violations.append({"import": imp, "target_layer": t_layer, "type": "dependency_direction",
                                       "message": f"{layer_name}에서 {t_layer} 참조 불가. 허용: {can_reference} — {os.path.relpath(target, project_root)}"})
                continue
        violations += _guess_violations(imp, file_path, layer_name, can_reference, cross_reference, layers, feature_root)
    return violations


def _guess_violations(imp, file_path, layer_name, can_reference, cross_reference, layers, feature_root):
    """The old heuristic for one import: only './' or 'src/' imports, target layer by layer-rules directory names."""
    out = []
    if not imp.startswith(".") and not imp.startswith("src/"):
        return out
    for other_layer_name, other_config in layers.items():
        other_dir = other_config.get("directory", "")
        if not other_dir or other_dir not in imp:
            continue
        if other_layer_name == layer_name and not cross_reference:
            file_domain = extract_domain(file_path, feature_root)
            target = os.path.normpath(os.path.join(os.path.dirname(file_path), imp)) if imp.startswith(".") else imp
            import_domain = extract_domain(target, feature_root)
            if file_domain and import_domain and file_domain != import_domain:
                out.append({"import": imp, "target_layer": other_layer_name, "type": "cross_reference",
                            "message": f"{layer_name} 간 상호참조 위반: {file_domain} → {import_domain}"})
        elif other_layer_name != layer_name and other_layer_name not in can_reference:
            out.append({"import": imp, "target_layer": other_layer_name, "type": "dependency_direction",
                        "message": f"{layer_name}에서 {other_layer_name} 참조 불가. 허용: {can_reference}"})
    return out


def check_query_discipline(file_path):
    """L2 쿼리 통제 관심사 분리 (DEC-2026-08-13-03, layer-rules L2 rules) — kotlin 백엔드 정적 검출.

    - DSLContext 주입은 {Domain}…Template 파일 전용 — Service·Repository 등 다른 파일 금지
    - Repository 의 @Query 금지 — 메서드 네임 파생 쿼리 또는 jOOQ Template 로 대체
    - waiver: user-entity/user_entity (user-api 동결 트랙 — 레거시 파리티 보존)
    """
    if not file_path.endswith(".kt"):
        return []
    norm = file_path.replace("\\", "/")
    if "/build/" in norm or "/user-entity/" in norm or "/user_entity/" in norm:
        return []
    basename = os.path.basename(file_path)
    is_template = re.search(r"Templates?\.kt$", basename) is not None

    try:
        content = _read(file_path)
    except OSError:
        return []

    violations = []
    if not is_template and re.search(r"^import\s+org\.jooq\.DSLContext\b", content, re.M):
        violations.append({
            "import": "org.jooq.DSLContext",
            "target_layer": "L2_DataLayer",
            "type": "query_discipline",
            "message": "DSLContext 는 {Domain}…Template 전용 — Service·Repository 주입 금지 (DEC-2026-08-13-03)"
        })
    if not is_template and re.search(r"^\s*@Query\b", content, re.M):
        violations.append({
            "import": "@Query",
            "target_layer": "L2_DataLayer",
            "type": "query_discipline",
            "message": "@Query 금지 — 메서드 네임 파생 쿼리로, 초과 쿼리는 jOOQ Template 로 (DEC-2026-08-13-03)"
        })
    return violations


def extract_domain(path, feature_root=None):
    """도메인 = layer-map feature_root 다음 경로 조각(CI Feature_Block 격리와 같은 뜻), 없으면 고정 디렉터리 이름 다음 조각."""
    norm = path.replace("\\", "/")
    if feature_root:
        i = norm.find(feature_root)
        if i >= 0:
            rest = norm[i + len(feature_root):].lstrip("/").split("/")
            return rest[0] if rest and rest[0] else None
    parts = norm.split("/")
    for i, part in enumerate(parts):
        if part in (
            "data", "composite", "coordinate", "controller", "hooks", "models",
            "features", "data-state", "contracts", "routes",
        ):
            if i + 1 < len(parts):
                return parts[i + 1]
    return None


def parse_inputs(argv):
    """CLI 인자 또는 stdin Hook JSON에서 file_path/project_type 추출"""
    if len(argv) >= 2 and argv[1] not in ("-", ""):
        file_path = argv[1]
        project_type = argv[2] if len(argv) > 2 else os.environ.get("STRATA_PROJECT_TYPE")
        return file_path, project_type

    if sys.stdin.isatty():
        return None, None

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return None, None
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None, None

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path")
    project_type = os.environ.get("STRATA_PROJECT_TYPE")
    if payload.get("hook_event_name") in ("PreToolUse", "PostToolUse"):
        HOOK["event"] = payload["hook_event_name"]
        HOOK["from_hook"] = True
    if file_path and payload.get("hook_event_name") == "PreToolUse":
        PRE_WRITE["on"] = True
        content = proposed_content(payload.get("tool_name", ""), tool_input)
        if content is None:
            return None, project_type          # 쓰기 도구가 아니면 검사하지 않는다
        CONTENT_OVERRIDE[os.path.abspath(file_path)] = content
    return file_path, project_type


PRE_WRITE = {"on": False}


def _content_before(file_path):
    """The file before this edit: on PreToolUse the file on disk (empty for a new file); on PostToolUse the last
    commit's version (empty when untracked). None when it cannot be known (a hand run, no git) — then every
    violation counts as new, as before."""
    path = os.path.abspath(file_path)
    if PRE_WRITE["on"]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""
    if HOOK["event"] != "PostToolUse" or not HOOK.get("from_hook"):
        return None
    d = os.path.dirname(path)
    top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        return None
    rel = os.path.relpath(path, top.stdout.strip())
    r = subprocess.run(["git", "-C", top.stdout.strip(), "show", f"HEAD:{rel}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def main():
    file_path, project_type = parse_inputs(sys.argv)
    if not file_path:
        sys.exit(0)

    strata_root = find_strata_root()
    project_root = find_project_root()
    project_type = resolve_project_type(project_type, project_root)

    rules = load_layer_rules(strata_root, project_root)
    code_ext = (".kt", ".kts", ".java", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".py", ".swift")
    if not rules and file_path.endswith(code_ext):
        # 조용히 통과하지 않는다 — 검사를 실행하지 못했다는 사실을 알린다 (DEC-2026-09-30-03)
        notify_agent(
            "⚠ Strata 레이어 검사를 실행하지 못했습니다 — layer-rules.yaml 을 찾지 못함 "
            f"(rules={strata_root or 'strata-kit core/rules 없음'}, project={project_root}). "
            "이 편집은 레이어 검증 없이 통과했습니다. CI 의 아키텍처 테스트가 정본 판정입니다."
        )
        sys.exit(0)
    if not rules:
        sys.exit(0)
    if rules:
        stack, variant, explicit = _stack_for_project(rules, project_type, project_root)
        if explicit and variant and not stack.get("layers"):
            print(f"\n❌ Strata frontend variant 미정의 — {variant}", file=sys.stderr)
            print("   layer-rules.yaml의 variants에 등록된 값을 사용하세요.\n", file=sys.stderr)
            sys.exit(2)

    layer_name, layer_config, active_layers = identify_layer(file_path, rules, project_type, project_root)
    if not layer_name:
        sys.exit(0)

    # 검증 제외 마커 (_infrastructure, _pending 등)
    if layer_name.startswith("_"):
        sys.exit(0)

    # Core rules가 없으면 의존성 검증 자체 불가
    if not rules or not layer_config:
        sys.exit(0)

    layer_map = load_project_layer_map(project_root) or {}
    in_legacy, live_exc, problems = zone_and_exceptions(file_path, layer_map)
    if problems:
        # 읽지 못한 존·예외는 없는 것으로 보고 기존대로 검사한다 — 그 사실은 알린다 (DEC-2026-09-30-03)
        notify_agent("⚠ Strata layer-map 의 " + ", ".join(problems) + " — 존·예외 없이 검사했습니다.")
    feature_root = layer_map.get("feature_root") if isinstance(layer_map.get("feature_root"), str) else None
    if feature_root is None:
        # 없으면 layer-rules 의 domain_slice('src/features/(*)/') 접두 — CI 템플릿과 같은 뜻 (DEC-2026-11-01-19)
        sl = layer_config.get("domain_slice")
        if isinstance(sl, str) and "(*)" in sl and "/" in sl:
            feature_root = sl.split("(*)")[0]
    # legacy 존: 레이어 방향·교차 참조 검사에서 뺀다, 경고도 없다 — CI 와 같은 뜻 (DEC-2026-10-31-20)
    violations = [] if in_legacy else check_violations(file_path, layer_name, layer_config, active_layers, feature_root, layer_map, project_root)
    waived = []
    for v in list(violations):
        hit = next((e for e in live_exc if e.get("to_layer") == v["target_layer"]), None)
        if hit:
            violations.remove(v)
            waived.append((v, hit))
    violations += check_query_discipline(file_path)

    # only what this edit adds blocks — violations the file already had are the CI baseline's business, and blocking
    # an unrelated one-line edit on them is what would stall an unattended session (MB-strata-kit-2026-041)
    before = _content_before(file_path)
    kept = []
    if before is not None and violations:
        key = lambda v: (v["type"], v["import"], v["target_layer"])
        path = os.path.abspath(file_path)
        saved = CONTENT_OVERRIDE.get(path)
        CONTENT_OVERRIDE[path] = before
        try:
            old = [] if in_legacy else check_violations(file_path, layer_name, layer_config, active_layers, feature_root, layer_map, project_root)
            old += check_query_discipline(file_path)
        finally:
            if saved is None:
                CONTENT_OVERRIDE.pop(path, None)
            else:
                CONTENT_OVERRIDE[path] = saved
        old_keys = {key(v) for v in old if not any(e.get("to_layer") == v["target_layer"] for e in live_exc)}
        kept = [v for v in violations if key(v) in old_keys]
        violations = [v for v in violations if key(v) not in old_keys]

    if violations:
        # 위반은 stderr — PostToolUse exit 2 는 stderr 만 에이전트에게 전달한다 (stdout 은 보이지 않음)
        err = sys.stderr
        when = "쓰기 전 차단 (파일은 바뀌지 않았다)" if PRE_WRITE["on"] else "쓴 뒤 감지"
        print(f"\n❌ Strata 레이어 위반 — {when} — {file_path}", file=err)
        print(f"   현재 레이어: {layer_name}", file=err)
        print(f"   참조 가능: {layer_config.get('can_reference', [])}\n", file=err)
        for v in violations:
            print(f"   ⚠ [{v['type']}] {v['message']}", file=err)
            print(f"     import: {v['import']}\n", file=err)
        if waived:
            print("   (예외로 뺀 참조: " + ", ".join(f"{e.get('id') or e.get('from_path')} → {v['target_layer']}" for v, e in waived) + ")", file=err)
        sys.exit(2)

    if kept:
        notify_agent(f"Strata 레이어: 이 파일에 원래 있던 위반 {len(kept)}건은 이번 편집이 더한 것이 아니라 막지 않았습니다 — "
                     + "; ".join(v["message"] for v in kept[:3]) + (" …" if len(kept) > 3 else ""))
    if waived:
        notify_agent("Strata 레이어: layer-map 예외로 뺀 참조 — " + "; ".join(
            f"{e.get('id') or e.get('from_path')}({e.get('decision') or '결정 없음'}): {v['import']} → {v['target_layer']}" for v, e in waived))
    sys.exit(0)


if __name__ == "__main__":
    main()
