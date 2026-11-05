"""Lockfile generator: pnpm-lock.yaml · package-lock.json (npm) · uv.lock (pypi) · go.sum (golang) · CycloneDX json (sbom).
Direct and transitive dependencies both become items; `depth` says which (unknown when the file cannot tell)."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

from kb.security.generators import ECOSYSTEM_SOURCE, item, purl


def _lib(name, version, env, eco, depth, path, namespace=None, identifier=None):
    return item(name, version, env, "library", ECOSYSTEM_SOURCE.get(eco, "none"),
                identifier or purl(eco, name, version, namespace), ecosystem=eco, depth=depth, file=path.name)


def _pnpm(path: Path, env: str) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    direct: set[str] = set()
    for imp in (doc.get("importers") or {}).values():
        for sect in ("dependencies", "devDependencies", "optionalDependencies"):
            direct |= set((imp.get(sect) or {}).keys())
    if not doc.get("importers"):   # lockfile v5 keeps them at the top
        for sect in ("dependencies", "devDependencies"):
            direct |= set((doc.get(sect) or {}).keys())
    out = []
    for key in (doc.get("packages") or {}):
        k = key.lstrip("/")
        if "@" in k[1:]:
            name, version = k[: k.rindex("@")], k[k.rindex("@") + 1:]
        else:                        # v5: /name/version
            name, version = k[: k.rindex("/")], k[k.rindex("/") + 1:]
        version = version.split("(")[0]
        out.append(_lib(name, version, env, "npm", "direct" if name in direct else "transitive", path))
    return out


def _npm(path: Path, env: str) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    pk = doc.get("packages") or {}
    root = pk.get("", {})
    direct = set()
    for sect in ("dependencies", "devDependencies", "optionalDependencies"):
        direct |= set((root.get(sect) or {}).keys())
    out, seen = [], set()
    for key, meta in pk.items():
        if not key or "node_modules/" not in key:
            continue
        name = key[key.rindex("node_modules/") + len("node_modules/"):]
        version = str(meta.get("version", "unknown"))
        if (name, version) in seen:
            continue
        seen.add((name, version))
        out.append(_lib(name, version, env, "npm", "direct" if name in direct and key == f"node_modules/{name}" else "transitive", path))
    return out


def _uv(path: Path, env: str) -> list[dict]:
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    pkgs = doc.get("package") or []
    roots = [p for p in pkgs if isinstance(p.get("source"), dict) and ({"editable", "virtual"} & set(p["source"]))]
    direct = {d.get("name") for r in roots for d in (r.get("dependencies") or [])}
    for r in roots:
        for grp in (r.get("dev-dependencies") or {}).values():
            direct |= {d.get("name") for d in grp}
    out = []
    for p in pkgs:
        if p in roots:
            continue
        name, version = p.get("name"), str(p.get("version", "unknown"))
        out.append(_lib(name, version, env, "pypi", "direct" if name in direct else "transitive", path))
    return out


def _gosum(path: Path, env: str) -> list[dict]:
    seen, out = set(), []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        mod, ver = parts[0], parts[1]
        if ver.endswith("/go.mod"):
            ver = ver[: -len("/go.mod")]
        if (mod, ver) in seen:
            continue
        seen.add((mod, ver))
        out.append(_lib(mod, ver, env, "golang", "unknown", path))
    return out


def _sbom(path: Path, env: str) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for c in doc.get("components") or []:
        name, version, group = c.get("name"), str(c.get("version", "unknown")), c.get("group")
        out.append(_lib(name, version, env, "maven", "unknown", path, namespace=group, identifier=c.get("purl")))
    return out


READERS = {"pnpm-lock.yaml": _pnpm, "package-lock.json": _npm, "uv.lock": _uv, "go.sum": _gosum}


def generate(paths: list[Path], ecosystem, environment: str) -> list[dict]:
    """ecosystem is informational (the file name picks the reader); a list is accepted for mixed targets."""
    out: list[dict] = []
    for p in paths:
        p = Path(p)
        reader = READERS.get(p.name) or (_sbom if p.suffix == ".json" else None)
        if reader is None:
            raise ValueError(f"읽을 수 없는 잠금 파일: {p}")
        out.extend(reader(p, environment))
    return out
