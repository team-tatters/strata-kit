"""Engine entry points: build-store (providers → store) and store-stats."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from kb import kit_root, vault_root
from kb.paths import resolve_tier_p
from kb.providers import CodeGraph, DecisionRecords, Orders, VaultScanner
from kb.store import SqliteStore


def kit_revision() -> str:
    kit = kit_root()
    try:
        rev = subprocess.run(["git", "-C", str(kit), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(kit), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def default_project_dirs(vault: Path) -> list[Path]:
    """Repos whose Tier P we can reach: $STRATA_PROJECTS/<name>, workspace/<name> (siblings of the
    vault), and for detached projects the vault itself (projects/<name>/strata/)."""
    projects_dir = vault / "projects"
    if not projects_dir.is_dir():
        return []
    roots = []
    if os.environ.get("STRATA_PROJECTS"):
        roots.append(Path(os.path.expanduser(os.environ["STRATA_PROJECTS"])))
    roots.append(vault.parent)
    found: list[Path] = []
    for p in sorted(d for d in projects_dir.iterdir() if d.is_dir()):
        for root in roots:
            cand = root / p.name
            if cand.is_dir():
                try:
                    if resolve_tier_p(cand) is not None:
                        found.append(cand.resolve())
                        break
                except ValueError:
                    continue
    return found


def build_store(vault: Path, store_path: Path, project: str | None, project_dirs: list[Path] | None) -> SqliteStore:
    dirs = project_dirs if project_dirs is not None else default_project_dirs(vault)
    if project:
        dirs = [d for d in dirs if d.name == project]
    providers = [VaultScanner(vault, project), Orders(vault, project), DecisionRecords(dirs, vault)]
    if os.environ.get("KB_NO_CODE_GRAPH") != "1":
        providers.append(CodeGraph(dirs))
    store = SqliteStore(store_path)
    rev = store.rebuild(providers, kit_rev=kit_revision())
    counts = store.counts()
    kinds = {k: len(store.query(kind=k)) for k in ("doc", "session", "task", "order", "node", "decision", "code")}
    dangling = store.dangling_edges()
    code_dangling = sum(1 for e in dangling if e.dst.startswith("code:"))
    print(f"store: {store_path}")
    print(f"  nodes {counts['nodes']} ({', '.join(f'{k} {v}' for k, v in kinds.items() if v)}) · edges {counts['edges']} · chunks {counts['chunks']}")
    print(f"  decision · code sources: {', '.join(str(d) for d in dirs) or '(none)'}")
    print(f"  dangling edges: {len(dangling)} (targets without a node — ref:*, missing nodes; covers to code surfaces the repos do not have: {code_dangling})")
    print(f"  revision {rev.store_rev} kit {rev.kit_rev} built {rev.built_at}")
    return store


def _source_mtime(vault: Path, project_dirs: list[Path]) -> float:
    """Newest mtime among the store's sources: vault markdown · toc · task yaml · decision records."""
    newest = 0.0
    roots = [vault / "projects", vault / "patterns", vault / "retrospectives", vault / "ideas", vault / "_index", vault / "_meta"]
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.suffix in (".md", ".yaml") and not p.is_symlink():
                try:
                    newest = max(newest, p.stat().st_mtime)
                except OSError:
                    pass
    for d in project_dirs:
        try:
            tier = resolve_tier_p(d)
        except ValueError:
            continue
        if tier and tier.decisions_dir.is_dir():
            for p in tier.decisions_dir.glob("DEC-*.yaml"):
                newest = max(newest, p.stat().st_mtime)
        for probe in (d / ".git" / "index", d / ".git" / "HEAD"):   # the code graph follows commits and staged files
            try:
                newest = max(newest, probe.stat().st_mtime)
            except OSError:
                pass
    return newest


def ensure_fresh_store(store_path: Path | None = None, vault: Path | None = None,
                       project_dirs: list[Path] | None = None, quiet: bool = True) -> SqliteStore:
    """Open the store; rebuild it first when it is missing or any source is newer than its built_at.
    KB_NO_REFRESH=1 opens whatever is there. Failures to rebuild never block the query."""
    vault = vault or vault_root()
    if vault is None:
        from kb.store import StoreError
        raise StoreError("STRATA_VAULT is not set and no --vault/--store was given")
    store_path = store_path or vault / ".kb" / "store.sqlite"
    dirs = project_dirs if project_dirs is not None else default_project_dirs(vault)
    if os.environ.get("KB_NO_REFRESH") == "1" and store_path.is_file():
        return SqliteStore(store_path)
    stale = not store_path.is_file()
    if not stale:
        probe = SqliteStore(store_path)
        rev = probe.revision()
        probe.close()
        if rev is None:
            stale = True
        else:
            from datetime import datetime
            built = datetime.fromisoformat(rev.built_at).timestamp()
            # built_at is stored to the second (store.py now_iso drops microseconds): a source written in the same
            # second before the build looked newer and forced a needless rebuild — allow that truncated second
            stale = _source_mtime(vault, dirs) >= built + 1
    if stale:
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO() if quiet else sys.stdout):
            return build_store(vault, store_path, None, dirs)
    return SqliteStore(store_path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb", description="KB store engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-store", help="rebuild the store from the vault scanner and decision records")
    b.add_argument("--vault", default=None, help="vault root (default $STRATA_VAULT)")
    b.add_argument("--store", default=None, help="store file (default <vault>/.kb/store.sqlite)")
    b.add_argument("--project", default=None, help="limit to one vault project")
    b.add_argument("--project-dir", action="append", default=None, help="repo with Tier P records (repeatable; default: auto)")
    s = sub.add_parser("store-stats", help="counts and last revision")
    s.add_argument("--vault", default=None)
    s.add_argument("--store", default=None)
    args = ap.parse_args(argv)

    vault = Path(args.vault).resolve() if args.vault else vault_root()
    if vault is None:
        print("STRATA_VAULT not set and --vault not given", file=sys.stderr)
        return 2
    store_path = Path(args.store).resolve() if args.store else vault / ".kb" / "store.sqlite"
    if args.cmd == "build-store":
        dirs = [Path(d) for d in args.project_dir] if args.project_dir else None
        build_store(vault, store_path, args.project, dirs).close()
        return 0
    if not store_path.is_file():
        print(f"no store at {store_path}", file=sys.stderr)
        return 1
    store = SqliteStore(store_path)
    print(store.counts())
    print(store.revision())
    store.close()
    return 0
