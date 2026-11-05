"""The kit's runtime environment (MB-strata-kit-2026-058): which python each execution path really runs, whether that
python has the kit's dependencies, which runtime managers and version files the machine uses, and — once the person
chooses — one STRATA_PYTHON written the same way into every path.

Execution paths measured (each can pick a different python; the 2026-11-05 audit found launchd's bare python3 was
/usr/bin/python3 without PyYAML while the interactive shell had asdf's):

  interactive_shell   STRATA_PYTHON in this environment, else python3 on this PATH
  claude_hooks        env.STRATA_PYTHON in Claude Code settings (user, project, project local), else bare python3
  mcp                 `uv run --directory $STRATA_KIT` → the kit's .venv python
  launchd             EnvironmentVariables.STRATA_PYTHON in the librarian plist, else python3 on launchd's PATH
  non_interactive_sh  STRATA_PYTHON exported in ~/.zshenv, else python3 on the default PATH

Nothing here edits a person's home files: generate writes snippets and instructions; the person applies them.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

DEFAULT_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"   # launchd's and a bare `sh -c`'s PATH on macOS
REQUIRED = ("yaml", "numpy", "mcp")              # pyproject dependencies (import names)
OPTIONAL = ("sentence_transformers", "torch")    # the embed extra
NEEDS = {"interactive_shell": ("yaml",), "claude_hooks": ("yaml",), "mcp": REQUIRED, "launchd": ("yaml",), "non_interactive_sh": ("yaml",)}
DEFAULT_CHOICE = "uv-venv"

OPTIONS = {
    "uv-venv": {
        "en": {"label": "kit in a uv-managed venv (the kit's own .venv from uv.lock)",
               "pros": "isolated and reproducible from the lockfile; uv downloads a prebuilt python itself, so no python know-how is needed (one `uv sync`); the MCP server already runs this way, so it is one tool instead of two",
               "cons": "one language only; the venv must be synced after the kit's dependencies change (uv sync)"},
        "ko": {"label": "kit 은 uv 가 관리하는 venv (uv.lock 으로 만든 kit 전용 .venv)",
               "pros": "잠금 파일로 격리·재현된다, uv 가 미리 빌드된 python 을 직접 내려받아 python 을 몰라도 된다(uv sync 한 번), MCP 서버가 이미 이 방식이라 도구가 둘이 아니라 하나다",
               "cons": "언어 하나만 다룬다, kit 의존성이 바뀌면 다시 맞춰야 한다(uv sync)"}},
    "asdf": {
        "en": {"label": "asdf python (.tool-versions)",
               "pros": "many languages pinned in one file the person already keeps",
               "cons": "shims are not on launchd's or a non-interactive shell's PATH — needs the absolute install path, rewritten on every python upgrade; python is built from source (build deps, minutes); kit packages land in that python's global site-packages, unlocked; uv is still needed for the MCP server"},
        "ko": {"label": "asdf python (.tool-versions)",
               "pros": "여러 언어의 판을 사람이 이미 쓰는 파일 하나로 고정한다",
               "cons": "shim 이 launchd·비대화 셸 PATH 에 없다 — 설치 절대 경로가 필요하고 python 판을 올릴 때마다 고쳐야 한다, python 을 소스에서 빌드한다(빌드 의존성·몇 분), kit 패키지가 그 python 전역에 잠금 없이 섞인다, MCP 서버 때문에 uv 는 어차피 필요하다"}},
    "mise": {
        "en": {"label": "mise python (.mise.toml or .tool-versions)",
               "pros": "asdf-compatible, plus env variables and tasks in the same file",
               "cons": "the same PATH problem outside an activated shell — needs the absolute install path"},
        "ko": {"label": "mise python (.mise.toml 또는 .tool-versions)",
               "pros": "asdf 와 호환되고 환경 변수·작업도 같은 파일에 둔다",
               "cons": "활성화된 셸 밖에서는 같은 PATH 문제 — 설치 절대 경로가 필요하다"}},
    "pyenv": {
        "en": {"label": "pyenv python (.python-version)",
               "pros": "common for python-only machines",
               "cons": "shims need an initialised shell; packages per version; python only"},
        "ko": {"label": "pyenv python (.python-version)",
               "pros": "python 만 쓰는 기계에서 흔하다",
               "cons": "shim 은 초기화된 셸이 필요하다, 패키지가 판 단위다, python 만 다룬다"}},
    "brew": {
        "en": {"label": "Homebrew python", "pros": "easy to install and on a fixed path",
               "cons": "the version moves with brew upgrade; weak pinning and no isolation (PEP 668 blocks pip install)"},
        "ko": {"label": "Homebrew python", "pros": "설치가 쉽고 경로가 고정된다",
               "cons": "brew upgrade 때 판이 움직인다, 판 고정·격리가 약하다(PEP 668 이 pip install 을 막는다)"}},
    "system": {
        "en": {"label": "system python (/usr/bin/python3)", "pros": "always there, the path every bare python3 falls back to",
               "cons": "old, no PyYAML by default, no pinning or isolation"},
        "ko": {"label": "시스템 python (/usr/bin/python3)", "pros": "항상 있다, 맨 python3 가 결국 닿는 경로다",
               "cons": "오래됐고 PyYAML 이 기본으로 없다, 판 고정·격리가 없다"}},
}
DEFAULT_REASON = {"en": "keep the kit in its own uv venv (reproducible from uv.lock, same python as the MCP server) and keep the person's language runtime manager for their projects",
                  "ko": "kit 은 자기 uv venv 에 두고(uv.lock 으로 재현, MCP 서버와 같은 python), 사람의 언어 런타임 관리자는 그대로 프로젝트에 쓴다"}

LAYER_TEXT = {
    "en": {"languages": "keep it for the person's language runtimes (node, java, go, …) — nothing changes",
           "uv_managed": "{tool} already manages uv ({file}) — keep it",
           "uv_add": "let {tool} install uv too, so every runtime still comes from one manager",
           "uv_installer": "install uv with its own installer (curl -LsSf https://astral.sh/uv/install.sh | sh) or a package manager",
           "kit": "the kit's python and packages live in its uv venv (uv.lock): `uv sync --extra embed` is the only command, no python knowledge needed",
           "asdf_fits": "pick asdf (or mise) python instead only when the team pins every runtime, python included, in one .tool-versions and CI reproduces from that file — accepting that the kit's packages (torch etc.) then share that python's global environment"},
    "ko": {"languages": "사람의 언어 런타임(node·java·go …)은 지금처럼 이것으로 — 바뀌는 것 없음",
           "uv_managed": "uv 는 이미 {tool} 로 관리한다({file}) — 그대로 둔다",
           "uv_add": "uv 도 {tool} 로 설치해 모든 런타임이 관리자 하나에서 오게 한다",
           "uv_installer": "uv 는 자체 설치기(curl -LsSf https://astral.sh/uv/install.sh | sh)나 패키지 관리자로 설치한다",
           "kit": "kit 의 python 과 패키지는 uv venv(uv.lock)에 둔다 — 명령은 uv sync --extra embed 하나, python 을 몰라도 된다",
           "asdf_fits": "asdf(또는 mise) python 을 고르는 것은 팀이 python 까지 모든 런타임을 .tool-versions 하나로 고정하고 CI 도 그 파일로 재현할 때다 — 그 경우 kit 패키지(torch 등)가 그 python 전역에 섞이는 비용을 감수한다"},
}


def layers_advice(mgrs: dict, vfiles: list[dict], lang: str = "en") -> dict:
    """The recommendation as layers rather than one choice: the person's language runtime manager stays, uv comes
    from that manager (or its own installer), the kit runs in a uv venv. asdf/mise users keep one manager for
    everything they install by hand; the kit's python is uv's concern."""
    T = LAYER_TEXT["ko" if lang == "ko" else "en"]
    lang_mgr = next((m for m in ("asdf", "mise", "brew") if mgrs.get(m)), None)
    layers = []
    if lang_mgr:
        layers.append({"layer": "languages", "tool": lang_mgr, "why": T["languages"]})
    uv_file = next((v["file"] for v in vfiles if v.get("uv")), None)
    if uv_file and lang_mgr in ("asdf", "mise"):
        layers.append({"layer": "uv", "tool": lang_mgr, "why": T["uv_managed"].format(tool=lang_mgr, file=uv_file)})
    elif lang_mgr:
        layers.append({"layer": "uv", "tool": lang_mgr, "why": T["uv_add"].format(tool=lang_mgr)})
    else:
        layers.append({"layer": "uv", "tool": "uv installer", "why": T["uv_installer"]})
    layers.append({"layer": "kit", "tool": "uv-venv", "why": T["kit"]})
    return {"layers": layers, "asdf_python_fits_when": T["asdf_fits"]}


_PROBE = ("import importlib.util, json, sys; "
          "print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), 'executable': sys.executable, "
          "'modules': {m: importlib.util.find_spec(m) is not None for m in sys.argv[1:]}}))")


def _which(name: str, path: str | None) -> str | None:
    return shutil.which(name, path=path)


def probe(python: str | None, cache: dict | None = None) -> dict | None:
    """{version, executable, modules: {name: bool}} for a python, or None when it does not run."""
    if not python:
        return None
    cache = cache if cache is not None else {}
    if python in cache:
        return cache[python]
    try:
        r = subprocess.run([python, "-c", _PROBE, *REQUIRED, *OPTIONAL], capture_output=True, text=True, timeout=30)
        out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        out = None
    cache[python] = out
    return out


def _settings_python(files: list[Path]) -> tuple[str | None, str | None]:
    found = (None, None)
    for f in files:   # later files win: user, project, project local
        try:
            env = (json.loads(f.read_text(encoding="utf-8")) or {}).get("env") or {}
        except (OSError, ValueError):
            continue
        if env.get("STRATA_PYTHON"):
            found = (os.path.expanduser(str(env["STRATA_PYTHON"])), str(f))
    return found


def _plist_python(plist: Path) -> str | None:
    try:
        with plist.open("rb") as fh:
            return ((plistlib.load(fh) or {}).get("EnvironmentVariables") or {}).get("STRATA_PYTHON")
    except Exception:
        return None


def _zshenv_python(zshenv: Path, home: Path) -> str | None:
    try:
        text = zshenv.read_text(encoding="utf-8")
    except OSError:
        return None
    m = None
    for m in re.finditer(r"(?m)^\s*export\s+STRATA_PYTHON=([\"']?)([^\"'\n]+)\1", text):
        pass
    if not m:
        return None
    return m.group(2).replace("$HOME", str(home)).replace("${HOME}", str(home)).replace("~", str(home), 1) if m.group(2).startswith(("~", "$HOME", "${HOME}")) else m.group(2)


def version_files(dirs: list[Path]) -> list[dict]:
    out = []
    for d in dirs:
        for name in (".tool-versions", ".python-version", ".mise.toml"):
            p = d / name
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if name == ".tool-versions":
                m = re.search(r"(?m)^python\s+(\S+)", text)
            elif name == ".python-version":
                m = re.search(r"(?m)^\s*(\S+)", text)
            else:
                m = re.search(r"(?m)^\s*python\s*=\s*[\"']?([^\"'\s]+)", text)
            out.append({"file": str(p), "python": m.group(1) if m else None,
                        "uv": bool(re.search(r"(?m)^uv\s", text)) if name == ".tool-versions" else None})
    return out


def managers(home: Path, path: str | None) -> dict:
    return {
        "asdf": bool(_which("asdf", path) or (home / ".asdf").is_dir()),
        "mise": bool(_which("mise", path) or (home / ".local" / "share" / "mise").is_dir()),
        "uv": bool(_which("uv", path)),
        "pyenv": bool(_which("pyenv", path) or (home / ".pyenv").is_dir()),
        "brew": bool(_which("brew", path) or Path("/opt/homebrew/bin/brew").is_file() or Path("/usr/local/bin/brew").is_file()),
        "system": Path("/usr/bin/python3").is_file(),
    }


def detect(project: Path, kit: Path, home: Path | None = None, env: dict | None = None, plist: Path | None = None) -> dict:
    """The runtime facts: managers, version files, and per execution path the python, where it came from, its deps."""
    env = dict(os.environ if env is None else env)
    home = home or Path(env.get("HOME") or Path.home())
    plist = plist or home / "Library" / "LaunchAgents" / f"com.{env.get('USER') or os.environ.get('USER') or 'user'}.strata-librarian.plist"
    shell_path = env.get("PATH")
    cache: dict = {}
    paths = {}

    def add(name: str, python: str | None, source: str):
        info = probe(python, cache)
        need = NEEDS[name]
        missing = [m for m in need if not (info and info["modules"].get(m))]
        paths[name] = {"python": python, "source": source, "runs": info is not None,
                       "version": info and info["version"], "executable": info and info["executable"],
                       "missing": missing if info else list(need),
                       "optional_missing": [m for m in OPTIONAL if not (info and info["modules"].get(m))] if name == "mcp" else []}

    if env.get("STRATA_PYTHON"):
        add("interactive_shell", env["STRATA_PYTHON"], "STRATA_PYTHON in this environment")
    else:
        add("interactive_shell", _which("python3", shell_path), "python3 on this PATH")
    hp, hsrc = _settings_python([home / ".claude" / "settings.json", project / ".claude" / "settings.json", project / ".claude" / "settings.local.json"])
    if hp:
        add("claude_hooks", hp, f"env.STRATA_PYTHON in {hsrc}")
    else:
        add("claude_hooks", _which("python3", shell_path), "bare python3 (STRATA_PYTHON not in Claude Code settings env)")
    venv = kit / ".venv" / "bin" / "python"
    add("mcp", str(venv) if venv.exists() else None, "uv run --directory $STRATA_KIT (.venv)" + ("" if venv.exists() else " — not created yet (uv sync)"))
    lp = _plist_python(plist) if plist.is_file() else None
    if lp:
        add("launchd", lp, f"EnvironmentVariables.STRATA_PYTHON in {plist}")
    else:
        add("launchd", _which("python3", DEFAULT_PATH), "python3 on launchd's PATH" + ("" if plist.is_file() else f" (no plist at {plist})"))
    zp = _zshenv_python(home / ".zshenv", home)
    if zp:
        add("non_interactive_sh", zp, "export STRATA_PYTHON in ~/.zshenv")
    else:
        add("non_interactive_sh", _which("python3", DEFAULT_PATH), "python3 on the default PATH (STRATA_PYTHON not in ~/.zshenv)")
    return {"managers": managers(home, shell_path), "version_files": version_files([project, kit, home]), "paths": paths}


def findings(rt: dict) -> list[str]:
    """Human-readable problems: a path whose python does not run or lacks what it needs, and pythons that differ."""
    out = []
    for name, p in rt["paths"].items():
        if not p["runs"]:
            out.append(f"{name}: python {p['python'] or '없음'} 이 실행되지 않음 ({p['source']})")
        elif p["missing"]:
            out.append(f"{name}: {p['executable']} 에 {', '.join(p['missing'])} 없음 ({p['source']})")
    exes = {n: p["executable"] for n, p in rt["paths"].items() if p["runs"] and p["executable"]}   # a venv's python is its own (not resolved to the base)
    if len(set(exes.values())) > 1:
        out.append("실행 경로마다 python 이 다름: " + ", ".join(f"{n} {e}" for n, e in exes.items()))
    return out


def _tool_version(rt: dict, *names: str) -> str | None:
    for v in rt.get("version_files") or []:
        if Path(v["file"]).name in names and v.get("python"):
            return v["python"]
    return None


def python_for(choice: str, kit: Path, rt: dict, home: Path) -> str:
    """The absolute STRATA_PYTHON a choice means on this machine (never a shim)."""
    if choice == "uv-venv":
        return str(kit / ".venv" / "bin" / "python")
    if choice == "asdf":
        v = _tool_version(rt, ".tool-versions")
        if not v:
            raise ValueError("asdf: .tool-versions 에 python 판이 없다 — --answer strata_python=<절대 경로> 로 준다")
        return str(home / ".asdf" / "installs" / "python" / v / "bin" / "python3")
    if choice == "mise":
        v = _tool_version(rt, ".mise.toml", ".tool-versions")
        if not v:
            raise ValueError("mise: .mise.toml·.tool-versions 에 python 판이 없다 — --answer strata_python=<절대 경로> 로 준다")
        return str(home / ".local" / "share" / "mise" / "installs" / "python" / v / "bin" / "python3")
    if choice == "pyenv":
        v = _tool_version(rt, ".python-version")
        if not v:
            raise ValueError("pyenv: .python-version 이 없다 — --answer strata_python=<절대 경로> 로 준다")
        return str(home / ".pyenv" / "versions" / v / "bin" / "python3")
    if choice == "brew":
        return "/opt/homebrew/bin/python3" if Path("/opt/homebrew/bin").is_dir() else "/usr/local/bin/python3"
    if choice == "system":
        return "/usr/bin/python3"
    raise ValueError(f"runtime: 모르는 선택 {choice!r} ({', '.join(OPTIONS)})")


def setup_steps(choice: str, python: str) -> list[str]:
    """What the person runs once so the chosen python has the kit's dependencies."""
    if choice == "uv-venv":
        return ['uv sync --directory "$STRATA_KIT"   # add --extra embed for hybrid search (sentence-transformers·torch)']
    pip = f'"{python}" -m pip install "pyyaml>=6.0" "numpy>=1.26" "mcp>=1.27.0"'
    if choice == "asdf":
        return ["asdf install python <version in .tool-versions>", pip]
    if choice == "mise":
        return ["mise install python", pip]
    if choice == "pyenv":
        return ["pyenv install <version in .python-version>", pip]
    if choice == "brew":
        return ["brew install python pyyaml   # pip install into brew python is blocked by PEP 668; prefer uv-venv for mcp"]
    return [pip + "   # system python: may need --user"]


def snippets(python: str, kit: str, vault: str | None, project: str, locale: str = "en") -> dict[str, str]:
    """Output files for one STRATA_PYTHON: the person copies them into place (generate never edits home files)."""
    q = json.dumps
    env_sh = "\n".join([
        "# strata-kit runtime (tools/wizard.py generate) — append to ~/.zshenv so every zsh, interactive or not, sees it",
        f"export STRATA_PYTHON={q(python)}",
        f"export STRATA_KIT={q(kit)}",
        *([f"export STRATA_VAULT={q(vault)}"] if vault else []), ""])
    settings = {"env": {"STRATA_PYTHON": python, "STRATA_KIT": kit, **({"STRATA_VAULT": vault} if vault else {})},
                "hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [
                    {"type": "command", "command": '"$STRATA_PYTHON" "$STRATA_KIT/kb" check-layer'}]}]}}
    mcp = {"mcpServers": {"knowledge-base": {"type": "stdio", "command": "uv",
                                             "args": ["run", "--directory", kit, "strata-kb-mcp"],
                                             "env": {"STRATA_KIT": kit, **({"STRATA_VAULT": vault} if vault else {})}}}} \
        if python.endswith("/.venv/bin/python") else \
        {"mcpServers": {"knowledge-base": {"type": "stdio", "command": python, "args": ["-m", "kb.mcp"],
                                           "env": {"STRATA_KIT": kit, "PYTHONPATH": kit, **({"STRATA_VAULT": vault} if vault else {})}}}}
    bindir = str(Path(python).parent)
    plist = "\n".join([
        "<!-- strata-kit runtime: the EnvironmentVariables of the librarian plist (~/Library/LaunchAgents/com.<user>.strata-librarian.plist) -->",
        "<key>EnvironmentVariables</key>", "<dict>",
        f"  <key>STRATA_PYTHON</key><string>{python}</string>",
        f"  <key>STRATA_KIT</key><string>{kit}</string>",
        *([f"  <key>STRATA_VAULT</key><string>{vault}</string>"] if vault else []),
        f"  <key>PATH</key><string>{bindir}:{DEFAULT_PATH}</string>",
        "</dict>", ""])
    ko = locale == "ko"
    readme = "\n".join([
        "# strata-kit 실행 환경 — 사람이 적용할 것" if ko else "# strata-kit runtime — steps for the person",
        "",
        (f"STRATA_PYTHON 하나: `{python}`. 아래 파일은 붙여 넣을 조각이다. 마법사는 홈 파일을 고치지 않는다."
         if ko else f"One STRATA_PYTHON: `{python}`. The files here are snippets to paste; the wizard never edits home files."),
        "",
        ("1. `env.sh` 의 줄을 `~/.zshenv` 에 더한다(비대화 셸·Codex·Quilt 가 읽는다)." if ko else
         "1. Append the lines of `env.sh` to `~/.zshenv` (non-interactive shells, Codex and Quilt read it)."),
        ("2. `claude-settings.json` 의 `env` 를 `~/.claude/settings.json` 의 `env` 에 합친다. 훅 명령은 `\"$STRATA_PYTHON\"` 으로 쓴다." if ko else
         "2. Merge `env` from `claude-settings.json` into `env` in `~/.claude/settings.json`; hook commands use `\"$STRATA_PYTHON\"`."),
        ("3. `mcp.json` 이 knowledge-base MCP 서버를 같은 python 으로 띄우는 명령이다(플러그인이 등록했다면 그대로 둔다)." if ko else
         "3. `mcp.json` starts the knowledge-base MCP server with the same python (keep the plugin's registration if it has one)."),
        ("4. `launchd-environment.plist.xml` 의 EnvironmentVariables 를 librarian plist 에 넣고 `launchctl bootout`·`bootstrap` 으로 다시 올린다." if ko else
         "4. Put the EnvironmentVariables of `launchd-environment.plist.xml` into the librarian plist, then `launchctl bootout` and `bootstrap` it again."),
        ("5. 확인: `python3 tools/doctor.py <project>` 의 runtime 항목이 비어야 한다." if ko else
         "5. Check: the runtime items of `python3 tools/doctor.py <project>` should be gone."), ""])
    return {"env.sh": env_sh, "claude-settings.json": json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            "mcp.json": json.dumps(mcp, ensure_ascii=False, indent=2) + "\n", "launchd-environment.plist.xml": plist,
            f"README.{locale}.md": readme}
