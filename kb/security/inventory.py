"""Inventory (spec AC1, Tech Spec G1): one file per project and environment at projects/<p>/security/inventory/<env>.yaml,
built from the targets in $STRATA_VAULT/security/registry.yaml. Without --write the generated list is compared with the
file and the difference (added · removed · version changed) is printed — exit 0 when nothing differs, 1 when something
does; with --write the file is written and the same difference printed. Manual targets are only checked.

  python3 -m kb security inventory --project P --env E [--write]
  python3 -m kb security inventory --all [--write]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from kb.security.generators import SIX, compose, lockfile, manual


def registry_path(vault: Path) -> Path:
    return vault / "security" / "registry.yaml"


def sources_path(vault: Path) -> Path:
    return vault / "security" / "sources.yaml"


def inventory_path(vault: Path, project: str, environment: str) -> Path:
    return vault / "projects" / project / "security" / "inventory" / f"{environment}.yaml"


def load_registry(vault: Path) -> dict:
    p = registry_path(vault)
    if not p.is_file():
        raise FileNotFoundError(f"등록 파일 없음: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def manual_links(vault: Path) -> dict[str, str]:
    p = sources_path(vault)
    if not p.is_file():
        return {}
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(l["target_ref"]): str(l["notice"]) for l in (doc.get("manual_links") or []) if l.get("target_ref") and l.get("notice")}


def resolve(src: str, vault: Path) -> Path:
    s = str(src).replace("{workspace}", str(vault.parent)).replace("{vault}", str(vault))
    p = Path(s).expanduser()
    return p if p.is_absolute() else vault / p


def key(i: dict) -> str:
    """Identifier without its version (purl up to the last @), else device/name."""
    ident = str(i.get("identifier") or "none")
    if ident != "none" and "@" in ident[1:]:
        return ident.rsplit("@", 1)[0]
    return f"{i.get('device', '')}/{i.get('name')}"


def diff(old: list[dict], new: list[dict]) -> dict:
    """Keyed by identifier-without-version (or device/name): added · removed · changed [(name, old_version, new_version)].
    A key that appears more than once on either side (the same package at two versions in one lockfile) is compared by
    its full identifier instead, so it shows as added/removed, never as a false version change."""
    from collections import Counter
    co, cn = Counter(key(i) for i in old), Counter(key(i) for i in new)
    multi = {k for k, c in (co + cn).items() if co[k] > 1 or cn[k] > 1}

    def k2(i):
        k = key(i)
        return (k + "@" + str(i.get("version"))) if k in multi else k
    o = {k2(i): i for i in old}
    n = {k2(i): i for i in new}
    added = [n[k] for k in n if k not in o]
    removed = [o[k] for k in o if k not in n]
    changed = [(n[k]["name"], str(o[k].get("version")), str(n[k].get("version"))) for k in n if k in o and str(o[k].get("version")) != str(n[k].get("version"))]
    return {"added": added, "removed": removed, "changed": changed}


def render_diff(label: str, d: dict) -> list[str]:
    if not (d["added"] or d["removed"] or d["changed"]):
        return [f"{label}: 차이 없음"]
    lines = [f"{label}: +{len(d['added'])} -{len(d['removed'])} ~{len(d['changed'])}"]
    lines += [f"  + {i['name']}@{i.get('version')}" for i in d["added"]]
    lines += [f"  - {i['name']}@{i.get('version')}" for i in d["removed"]]
    lines += [f"  ~ {n} {a} → {b}" for n, a, b in d["changed"]]
    return lines


def generate(target: dict, vault: Path, links: dict[str, str]) -> list[dict]:
    kind, env, project = target.get("kind"), target["environment"], target["project"]
    paths = [resolve(s, vault) for s in (target.get("sources") or [])]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"{project}/{env}: 원본 파일 없음 — {', '.join(missing)}")
    if kind in ("lockfile", "sbom"):
        return lockfile.generate(paths, target.get("ecosystem"), env)
    if kind == "compose":
        pk = resolve(target["packages"], vault) if target.get("packages") else None
        if pk and not pk.is_file():
            raise FileNotFoundError(f"{project}/{env}: 패키지 목록 없음 — {pk}")
        return compose.generate(paths, env, project, os_spec=target.get("os"), manual_links=links,
                                internal_prefixes=target.get("internal_image_prefixes"), packages=pk)
    raise ValueError(f"{project}/{env}: 모르는 kind {kind!r}")


def read_items(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(doc.get("items") or [])


def write_inventory(path: Path, project: str, env: str, items: list[dict], source_ref: list[str], today: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blind = sum(1 for i in items if i.get("blind_candidate"))
    doc = {"project": project, "environment": env, "origin": "generated", "generated_at": today.isoformat(),
           "source_ref": source_ref, "counts": {"items": len(items), "blind_candidates": blind}, "items": items}
    path.write_text("# 대상 목록 — 생성본. 손으로 고치지 않는다: python3 -m kb security inventory --write (DEC-2026-11-03-05)\n"
                    + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def run_target(target: dict, vault: Path, links: dict[str, str], write: bool, today: date) -> tuple[list[str], bool]:
    """Returns (lines, differs_or_problem)."""
    project, env = target["project"], target["environment"]
    label = f"{project}/{env}"
    if target.get("status") in ("pending", "manual-input") and not target.get("sources"):
        return [f"{label}: 건너뜀 — {target.get('status')}: {target.get('note', '')}".rstrip()], False
    if target.get("kind") == "manual":
        src = resolve(target["sources"][0], vault)
        if not src.is_file():
            return [f"{label}: 손으로 적은 파일 없음 — {src.relative_to(vault) if src.is_relative_to(vault) else src}"], True
        items, problems = manual.load(src, env)
        lines = [f"{label}: 손 목록 {len(items)}항목, 빠진 값 {len(problems)}건"] + [f"  ! {p}" for p in problems]
        return lines, bool(problems)
    items = generate(target, vault, links)
    path = inventory_path(vault, project, env)
    d = diff(read_items(path), items)
    lines = render_diff(label, d)
    differs = bool(d["added"] or d["removed"] or d["changed"])
    if write:
        refs = [str(p.relative_to(vault.parent)) if p.is_relative_to(vault.parent) else str(p) for p in (resolve(s, vault) for s in target.get("sources") or [])]
        write_inventory(path, project, env, items, refs, today)
        lines.append(f"  → {path.relative_to(vault)} ({len(items)}항목, 눈이 없는 대상 후보 {sum(1 for i in items if i.get('blind_candidate'))})")
    return lines, differs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--project")
    inv.add_argument("--env")
    inv.add_argument("--all", action="store_true")
    inv.add_argument("--write", action="store_true")
    inv.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    today = a.today or date.today()
    try:
        reg = load_registry(vault)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    targets = reg.get("targets") or []
    if not a.all:
        if not (a.project and a.env):
            print("--project 와 --env 를 함께 주거나 --all", file=sys.stderr)
            return 2
        targets = [t for t in targets if t.get("project") == a.project and t.get("environment") == a.env]
        if not targets:
            print(f"등록에 없는 대상: {a.project}/{a.env} — {registry_path(vault).relative_to(vault)}", file=sys.stderr)
            return 2
    links = manual_links(vault)
    rc = 0
    for t in targets:
        try:
            lines, differs = run_target(t, vault, links, a.write, today)
        except (FileNotFoundError, ValueError) as e:
            lines, differs = [f"! {e}"], True
        print("\n".join(lines))
        rc = rc or (1 if differs else 0)
    return rc
