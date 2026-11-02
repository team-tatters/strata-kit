"""Resolve a TypeScript/JavaScript import to a file path the way the bundler would (MB-strata-kit-2026-041).

The edit hook used to see only imports starting with './' or 'src/' and to guess the target layer from layer-rules
directory names, so an alias import ('@/…', 'src/…' from tsconfig paths, '@shared/ui' workspace packages) passed
whatever it pointed at — and an agent blocked on a relative import could pass by rewriting it as an alias. Here an
import becomes a path: relative to the importing file; through the nearest tsconfig.json's compilerOptions.paths
(baseUrl, and a local 'extends' chain); or through a workspace package's package.json name. Bare third-party
packages resolve to None. The caller applies the layer-map mappings to the path, as dependency-cruiser does in CI.
"""
from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def strip_jsonc(text: str) -> str:
    """tsconfig is JSON with comments and trailing commas; strings may contain '/*' (as in "src/*")."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True; out.append(c); i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2
        else:
            out.append(c); i += 1
    s = "".join(out)
    import re
    return re.sub(r",(\s*[}\]])", r"\1", s)


@lru_cache(maxsize=256)
def tsconfig_paths(path: str) -> tuple[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    """(directory paths resolve from, ((pattern, targets), …)) for one tsconfig, following local 'extends'."""
    p = Path(path)
    try:
        d = json.loads(strip_jsonc(p.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return str(p.parent), ()
    base_dir, paths = str(p.parent), ()
    ext = d.get("extends")
    if isinstance(ext, str) and ext.startswith("."):
        parent = (p.parent / ext).resolve()
        if parent.suffix != ".json":
            parent = parent.with_suffix(".json")
        if parent.is_file():
            base_dir, paths = tsconfig_paths(str(parent))
    co = d.get("compilerOptions") or {}
    if co.get("baseUrl") is not None:
        base_dir = os.path.normpath(os.path.join(p.parent, co["baseUrl"]))
    if isinstance(co.get("paths"), dict):
        paths = tuple((k, tuple(v)) for k, v in co["paths"].items() if isinstance(v, list))
        if co.get("baseUrl") is None:
            base_dir = str(p.parent)
    return base_dir, paths


def nearest_tsconfig(start: Path, stop: Path) -> Path | None:
    d = start
    while True:
        f = d / "tsconfig.json"
        if f.is_file():
            return f
        if d == stop or d.parent == d:
            return None
        d = d.parent


@lru_cache(maxsize=16)
def workspace_packages(root: str) -> tuple[tuple[str, str, str], ...]:
    """(package name, directory, package.json text) for package.json files the repository tracks, longest name first."""
    r = subprocess.run(["git", "-C", root, "ls-files", "*package.json"], capture_output=True, text=True)
    out = []
    for rel in r.stdout.splitlines():
        if "node_modules/" in rel or rel.count("/") > 3:
            continue
        try:
            text = (Path(root) / rel).read_text(encoding="utf-8")
            name = json.loads(text).get("name")
        except (OSError, ValueError):
            continue
        if name:
            out.append((name, str((Path(root) / rel).parent), text))
    return tuple(sorted(out, key=lambda x: -len(x[0])))


def resolve(imp: str, file_path: str, root: str) -> str | None:
    """The path an import points at (no extension guessing), or None for a third-party package."""
    here = Path(os.path.abspath(file_path)).parent
    if imp.startswith("."):
        return os.path.normpath(os.path.join(here, imp))
    ts = nearest_tsconfig(here, Path(root))
    if ts:
        base, paths = tsconfig_paths(str(ts))
        for pattern, targets in paths:
            if not targets:
                continue
            if pattern.endswith("*") and imp.startswith(pattern[:-1]):
                return os.path.normpath(os.path.join(base, targets[0].replace("*", imp[len(pattern) - 1:])))
            if pattern == imp:
                return os.path.normpath(os.path.join(base, targets[0]))
    for name, d, text in workspace_packages(root):
        if imp == name or imp.startswith(name + "/"):
            return _package_entry(d, json.loads(text), imp[len(name):])
    return None


def _package_entry(d: str, pkg: dict, sub: str) -> str:
    """'' or '/x' inside a workspace package: its exports entry, else main for the package itself, else the path
    under the package (or under its src/)."""
    exports = pkg.get("exports")
    if isinstance(exports, str) and not sub:
        exports = {".": exports}
    if isinstance(exports, dict):
        v = exports.get("." + sub)
        while isinstance(v, dict):   # conditions: prefer types, then import, then default
            v = v.get("types") or v.get("import") or v.get("default") or next(iter(v.values()), None)
        if isinstance(v, str):
            return os.path.normpath(os.path.join(d, v))
    if not sub and isinstance(pkg.get("main") or pkg.get("types"), str):
        return os.path.normpath(os.path.join(d, pkg.get("main") or pkg.get("types")))
    for base in (d, os.path.join(d, "src")):
        cand = os.path.normpath(os.path.join(base, sub.lstrip("/")))
        if as_file(cand) != cand or os.path.isfile(cand):
            return cand
    return os.path.normpath(os.path.join(d, sub.lstrip("/")))


def as_file(path: str) -> str:
    """The file a resolved import loads, when it exists (path, path.ext, path/index.ext); else the path itself."""
    for cand in (path, *(path + e for e in EXTS), *(os.path.join(path, "index" + e) for e in EXTS)):
        if os.path.isfile(cand):
            return cand
    return path
