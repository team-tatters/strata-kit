#!/usr/bin/env python3
"""
Strata PreToolUse Hook: 네이밍 컨벤션 검증

호출 방식:
  1. CLI:    python3 validate-naming.py <file_path> [project_type]
  2. Hook:   stdin으로 Claude Code 공식 JSON 입력 — tool_input.file_path 사용
             (https://code.claude.com/docs/en/hooks)

종료 코드:
  0 — 컨벤션 준수 또는 검증 불가 (통과)
  2 — 위반 발견 (Claude에게 피드백 전달)

규칙 위치 우선순위:
  1. strata-kit core/rules/{naming-convention,layer-rules}.yaml
  2. {project_root}/docs/architecture/{naming-convention,layer-rules}.yaml (레거시)
"""

import sys
import os
import re
import json

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "⚠ Strata: PyYAML(yaml) 모듈이 없어 검증을 건너뜁니다.\n"
        "   설치: python3 -m pip install pyyaml\n"
        f"   현재 python: {sys.executable}\n"
    )
    sys.exit(0)


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


def _read_yaml(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_naming_rules(strata_root, project_root):
    candidates = []
    if strata_root:
        candidates.append(os.path.join(strata_root, "naming-convention.yaml"))
    candidates.append(os.path.join(project_root, "docs", "architecture", "naming-convention.yaml"))
    for c in candidates:
        data = _read_yaml(c)
        if data is not None:
            return data
    return None


def load_layer_rules(strata_root, project_root):
    candidates = []
    if strata_root:
        candidates.append(os.path.join(strata_root, "layer-rules.yaml"))
    candidates.append(os.path.join(project_root, "docs", "architecture", "layer-rules.yaml"))
    for c in candidates:
        data = _read_yaml(c)
        if data is not None:
            return data
    return None


def load_project_layer_map(project_root):
    """프로젝트별 layer_map (기계 판독용). repo .strata 에 없으면 Tier P(detached 는 vault) — 오더 2026.10.29-02 task-04."""
    if not project_root:
        return None
    from kb.legacy.check_layer_violation import load_project_layer_map as load_translated
    return load_translated(project_root)   # the same file and the same kit names as check-layer (MB-strata-kit-2026-018)


def _normalize_project_type(project_type, rules):
    """{project_type}을 layer-rules.yaml의 top-level 키로 정규화"""
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
    variant = (
        layer_map.get("variant")
        or layer_map.get(f"{project_type}_variant")
        or layer_map.get("variants", {}).get(project_type)
    )
    return variant, variant is not None


def _stack_for_project(rules, project_type, project_root=None):
    key = _normalize_project_type(project_type, rules)
    stack = rules.get(key, rules.get("backend", {}))
    variants = stack.get("variants", {})
    project_variant, explicit = _project_variant(project_root, key)
    variant = project_variant or stack.get("variant") or stack.get("default_variant")
    if variant and variant in variants:
        return variants[variant], explicit
    if explicit:
        return {}, explicit
    return stack, explicit


def _compat_stack(rules, project_type):
    key = _normalize_project_type(project_type, rules)
    return rules.get(key, rules.get("backend", {}))


def identify_layer(file_path, layer_rules, project_type, project_root=None):
    """우선순위: 프로젝트 layer-map → Core layer-rules.directory."""
    # 1) 프로젝트 layer-map 우선
    layer_map = load_project_layer_map(project_root)
    if layer_map:
        for m in layer_map.get("mappings", []):
            marker = m.get("path", "")
            if marker and marker in file_path:
                layer_name = m.get("layer")
                if not layer_name:
                    return None
                if not layer_rules:
                    return layer_name
                stack, explicit = _stack_for_project(layer_rules, project_type, project_root)
                if layer_name in (stack.get("layers", {}) or {}):
                    return layer_name
                if not explicit and layer_name in (_compat_stack(layer_rules, project_type).get("layers", {}) or {}):
                    return layer_name
                return layer_name

    # 2) Core fallback
    if not layer_rules:
        return None
    stack, _ = _stack_for_project(layer_rules, project_type, project_root)
    layers = stack.get("layers", {}) or {}
    for name, config in layers.items():
        directory = config.get("directory", "")
        if directory and directory in file_path:
            return name
    return None


def check_case(name, expected_case):
    if expected_case == "PascalCase":
        return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
    elif expected_case == "camelCase":
        return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name))
    elif expected_case == "kebab-case":
        return bool(re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', name))
    elif expected_case == "snake_case":
        return bool(re.match(r'^[a-z][a-z0-9]*(_[a-z0-9]+)*$', name))
    elif expected_case == "UPPER_SNAKE":
        return bool(re.match(r'^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$', name))
    return True


FRONTEND_DOT_SUFFIXES = (".const", ".type", ".types", ".util", ".utils",
                        ".stories", ".story", ".style", ".styles", ".module",
                        ".test", ".spec", ".api", ".dto")


def validate_file_name(file_path, layer_name, naming_rules, project_type):
    warnings = []
    file_name = os.path.basename(file_path)
    name_without_ext = os.path.splitext(file_name)[0]

    common = naming_rules.get("common", {})
    case_styles = common.get("case_styles", {})
    default_file_case = case_styles.get("file", "PascalCase")

    if ".test." in file_name or ".spec." in file_name:
        return warnings

    # 1) 금지 패턴은 stack/layer 무관하게 항상 적용 (Manager/Helper/Impl 등)
    prohibited = common.get("prohibited_patterns", [])
    for pattern in prohibited:
        if pattern.lower() in name_without_ext.lower():
            warnings.append(
                f"파일명에 금지 패턴 '{pattern}' 포함. "
                f"대안: Manager→Coordinator/Service, Helper→Util, Impl→(인터페이스명 그대로)"
            )

    # 2) 레이어별 네이밍 패턴이 매칭되면 common.case_styles 검사 스킵
    key = _normalize_project_type(project_type, naming_rules)
    stack_rules = naming_rules.get(key, naming_rules.get("backend", {}))
    layer_naming = stack_rules.get(layer_name, {}) if layer_name else {}
    layer_pattern_matched = False

    if layer_naming:
        examples = layer_naming.get("examples", [])
        if examples and any(_matches_pattern(file_name, ex) for ex in examples):
            layer_pattern_matched = True

    if layer_pattern_matched:
        return warnings

    # 3) Frontend stack은 dot-suffix(.types.ts, .const.ts 등) 파일을 허용 —
    #    PascalCase 강제는 backend-style 파일에만 적용해야 한다.
    if key == "frontend":
        # base.suffix.ext 구조에서 suffix가 FE 컨벤션이면 스킵
        parts = name_without_ext.split(".")
        if len(parts) > 1 and ("." + parts[-1]) in FRONTEND_DOT_SUFFIXES:
            return warnings
        # use{Name} (Hook) — camelCase 시작
        if parts and parts[0].startswith("use") and len(parts[0]) > 3 and parts[0][3].isupper():
            return warnings
        # FE에서는 PascalCase 강제 안 함 (Atomic은 PascalCase, util/hook은 다름)
        return warnings

    # 4) Backend default — PascalCase 검사
    base_name = name_without_ext.split(".")[0]
    if not check_case(base_name, default_file_case):
        warnings.append(
            f"파일명 '{file_name}'이 {default_file_case} 규칙을 따르지 않습니다."
        )

    if layer_naming:
        examples = layer_naming.get("examples", [])
        if examples and not any(_matches_pattern(file_name, ex) for ex in examples):
            warnings.append(
                f"레이어 '{layer_name}'의 네이밍 패턴과 불일치. "
                f"예시: {', '.join(examples[:3])}"
            )

    return warnings


def _matches_pattern(filename, example):
    name = os.path.splitext(filename)[0]
    ex_name = os.path.splitext(example)[0]
    for suffix in ["CommandService", "QueryService", "Repository", "Template",
                   "Controller", "Router", "Coordinator", "CompositeService",
                   "Listener", "Task", "Document", "Entity", "Config",
                   "Component", "Const", "Type", "Util", "Enum",
                   "ViewModel", "DTO", "Api", "Interface",
                   "Partial", "Page", "Layout", "Block", "Panel", "Dialog",
                   "Table", "Route", "Shell", "Provider"]:
        if suffix in ex_name and suffix in name:
            return True
    return False


HOOK_DEF = re.compile(r"\b(?:function\s+|(?:const|let|var)\s+)(use[A-Z]\w*)")
FRONTEND_EXT = (".ts", ".tsx", ".js", ".jsx")
HOOK = {"event": None, "tool": None, "input": {}}   # 호출된 이벤트와 도구 입력 — CLI 실행이면 비어 있다


COMPONENT_DEF = re.compile(r"(?:\b(?:function|class|const|let|var)\s+|\bas\s+)([A-Z]\w*)")


def hook_defs(text):
    return set(HOOK_DEF.findall(text or ""))


def component_defs(text):
    return set(COMPONENT_DEF.findall(text or ""))


def added_hook_defs(file_path, defs=hook_defs):
    """새로 들어가는 훅 정의 이름 — CI diff 규칙(추가된 줄의 정의만)과 같은 뜻. Edit·MultiEdit 는 바뀌어 들어가는 텍스트에서
    바뀌기 전 텍스트에 없던 정의, Write 는 기존 파일에 없던 정의. CLI 실행은 파일 전체."""
    tool, ti = HOOK["tool"], HOOK["input"]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            before = f.read()
    except OSError:
        before = ""
    if tool == "Write":
        return defs(ti.get("content")) - defs(before)
    if tool in ("Edit", "MultiEdit"):
        edits = ti.get("edits") if tool == "MultiEdit" else [ti]
        out = set()
        for e in edits or []:
            out |= defs(e.get("new_string")) - defs(e.get("old_string"))
        return out - defs(before)
    if tool is None:
        return defs(before)
    return set()


def forbidden_hook_warnings(file_path, naming_rules, project_type):
    """naming-convention.yaml frontend.DataState.forbidden_hook_prefixes — HTTP 동사는 transport 어휘다. 목록은 규칙 파일에서만 읽는다."""
    if not file_path.endswith(FRONTEND_EXT) or _normalize_project_type(project_type, naming_rules) != "frontend":
        return []
    ds = ((naming_rules or {}).get("frontend") or {}).get("DataState") or {}
    prefixes = ds.get("forbidden_hook_prefixes") or []
    out = []
    for name in sorted(added_hook_defs(file_path)):
        hit = next((p for p in prefixes if name.startswith(p) and (len(name) == len(p) or name[len(p)].isupper())), None)
        if hit:
            out.append(f"훅 '{name}' 이 금지 접두 '{hit}' 로 시작합니다 — HTTP 동사는 transport 어휘입니다. "
                       f"대안: {ds.get('query_adapter', 'use{Entity}Query')} · {ds.get('mutation_adapter', 'use{Entity}{Action}Mutation')}")
    return out


def forbidden_suffix_warnings(file_path, naming_rules, project_type):
    """naming-convention.yaml frontend.Feature_Block.forbidden_suffixes — Block·Container·Partial 은 모두 Section 이다
    (DEC-2026-11-01-19). 새로 들어가는 선언(export 별칭 포함)만 본다 — CI diff 규칙과 같은 뜻. 목록은 규칙 파일에서만 읽는다."""
    if not file_path.endswith((".tsx", ".jsx")) or _normalize_project_type(project_type, naming_rules) != "frontend":
        return []
    fb = ((naming_rules or {}).get("frontend") or {}).get("Feature_Block") or {}
    suffixes = fb.get("forbidden_suffixes") or []
    out = []
    for name in sorted(added_hook_defs(file_path, component_defs)):
        hit = next((s for s in suffixes if name.endswith(s) and len(name) > len(s)), None)
        if hit:
            out.append(f"컴포넌트 '{name}' 이 금지 접미 '{hit}' 로 끝납니다 — Feature Block 은 {fb.get('section', '{UseCase}Section')}"
                       f"(형태별 Panel·Dialog·Table), 렌더 절반은 {{Domain}}{{Purpose}}View")
    return out


def notify_agent(message):
    """exit 0 의 표준 출력은 에이전트에게 닿지 않는다 — 훅이면 additionalContext(호출된 이벤트 이름)로, CLI 면 그대로 출력."""
    if HOOK["event"]:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": HOOK["event"], "additionalContext": message}}, ensure_ascii=False))
    else:
        print(message)


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
    HOOK["event"] = payload.get("hook_event_name") if payload.get("hook_event_name") in ("PreToolUse", "PostToolUse") else "PreToolUse"
    HOOK["tool"], HOOK["input"] = payload.get("tool_name") or "", tool_input
    return file_path, project_type


# agent-harness folders: a file's name there is a command, an agent or a setting, not a code identifier
HARNESS_DIRS = {".claude", ".codex", ".cursor", ".agents", ".strata"}


def main():
    file_path, project_type = parse_inputs(sys.argv)
    if not file_path:
        sys.exit(0)
    if HARNESS_DIRS & set(file_path.replace("\\", "/").split("/")):
        sys.exit(0)   # .claude/commands/handoff.md is the /handoff command (2026-11-02)

    strata_root = find_strata_root()
    project_root = find_project_root()
    from kb.legacy.check_layer_violation import resolve_project_type
    project_type = resolve_project_type(project_type, project_root)

    naming_rules = load_naming_rules(strata_root, project_root)
    if not naming_rules:
        sys.exit(0)

    layer_rules = load_layer_rules(strata_root, project_root)
    layer_name = identify_layer(file_path, layer_rules, project_type, project_root)

    # 검증 제외 마커 (_infrastructure, _pending 등)
    if layer_name and layer_name.startswith("_"):
        sys.exit(0)

    warnings = validate_file_name(file_path, layer_name, naming_rules, project_type)
    warnings += forbidden_hook_warnings(file_path, naming_rules, project_type)
    warnings += forbidden_suffix_warnings(file_path, naming_rules, project_type)

    if warnings:
        # 네이밍은 warning 수준 — 차단하지 않는다. 에이전트에게 닿는 경로로 낸다 (planning/hook-zones-exceptions)
        lines = [f"⚠ Strata 네이밍 컨벤션 경고 — {os.path.basename(file_path)}"]
        if layer_name:
            lines.append(f"  레이어: {layer_name}")
        lines += [f"  → {w}" for w in warnings]
        notify_agent("\n".join(lines))

    sys.exit(0)


if __name__ == "__main__":
    main()
