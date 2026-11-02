#!/usr/bin/env python3
"""Build the public projection of strata-kit (DEC-2026-11-02-07).

The development repository is the source of truth. This reads public/projection.yaml, takes the tracked files at a
revision (HEAD by default — never the working tree, so a projection is reproducible from one commit), keeps those
that match an include glob and no exclude glob, places the public-only files listed under `map`, and scans every
projected file — its path and its text — for the `deny` patterns. Any hit fails the build and is listed as
file:line, which is the to-do list for neutralising the development sources; nothing is rewritten here.

  python3 tools/project_public.py scan                  # deny hits only, nothing written
  python3 tools/project_public.py scan --rev WORKTREE   # the same over the working tree, while neutralising
  python3 tools/project_public.py build --out DIR       # write the projection into DIR (its .git is kept)
  python3 tools/project_public.py build --out DIR --test   # and run the test suites inside DIR

`build` refuses to write when there are deny hits. DIR keeps its .git directory; everything else in it is replaced,
and DIR/.strata-projection.yaml records the source revision and the file count.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[1]
MANIFEST = "public/projection.yaml"


def git(repo: Path, *args: str, text: bool = True):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=text, check=True).stdout


def matches(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) or (g.endswith("/**") and path.startswith(g[:-2])) for g in globs)


WORKTREE = "WORKTREE"   # scan the working tree (tracked and new files) — for neutralising; build only from a commit


def load_manifest(repo: Path, rev: str) -> dict:
    if rev == WORKTREE:
        return yaml.safe_load((repo / MANIFEST).read_text(encoding="utf-8")) or {}
    return yaml.safe_load(git(repo, "show", f"{rev}:{MANIFEST}")) or {}


def listed(repo: Path, rev: str) -> list[str]:
    if rev == WORKTREE:
        files = git(repo, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
        return [p for p in files if p and (repo / p).is_file()]
    return [p for p in git(repo, "ls-tree", "-r", "--name-only", rev).splitlines() if p]


def plan(repo: Path, rev: str = "HEAD") -> tuple[dict, list[tuple[str, str]]]:
    """(manifest, [(source path, target path)]) for the tracked files at rev."""
    m = load_manifest(repo, rev)
    tracked = listed(repo, rev)
    inc, exc = m.get("include") or [], m.get("exclude") or []
    pairs = [(p, p) for p in tracked if matches(p, inc) and not matches(p, exc)]
    have = set(tracked)
    for src, dst in (m.get("map") or {}).items():
        if src not in have:
            raise SystemExit(f"map source {src} is not tracked at {rev}")
        pairs.append((src, dst))
    targets = [d for _, d in pairs]
    dup = sorted({d for d in targets if targets.count(d) > 1})
    if dup:
        raise SystemExit("two sources project to the same path: " + ", ".join(dup))
    return m, sorted(pairs, key=lambda x: x[1])


def read(repo: Path, rev: str, path: str) -> bytes:
    if rev == WORKTREE:
        return (repo / path).read_bytes()
    return git(repo, "show", f"{rev}:{path}", text=False)


def scan(repo: Path, rev: str, m: dict, pairs: list[tuple[str, str]]) -> list[dict]:
    rules = [(re.compile(d["pattern"], re.I), d) for d in m.get("deny") or []]
    hits = []
    for src, dst in pairs:
        data = read(repo, rev, src)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None   # binary: the path is still scanned
        for rx, d in rules:
            if dst in (d.get("allow") or []):
                continue
            if rx.search(dst):
                hits.append({"file": dst, "line": 0, "pattern": d["pattern"], "why": d.get("why", ""), "text": dst})
            if text is None:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append({"file": dst, "line": i, "pattern": d["pattern"], "why": d.get("why", ""), "text": line.strip()[:160]})
    return hits


def summary(hits: list[dict]) -> list[str]:
    by_dir: dict[str, set] = {}
    for h in hits:
        top = "/".join(h["file"].split("/")[:2]) if "/" in h["file"] else h["file"]
        by_dir.setdefault(top, set()).add(h["file"])
    L = [f"deny hits: {len(hits)} lines in {len({h['file'] for h in hits})} files"]
    L += [f"  {len(fs):4d} files  {d}" for d, fs in sorted(by_dir.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    return L


def build(repo: Path, rev: str, out: Path, pairs: list[tuple[str, str]]) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():
        if child.name == ".git":
            continue
        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    for src, dst in pairs:
        target = out / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read(repo, rev, src))
        mode = git(repo, "ls-tree", rev, "--", src).split()[0]
        if mode == "100755":
            target.chmod(0o755)
    full = git(repo, "rev-parse", rev).strip()
    (out / ".strata-projection.yaml").write_text(
        f"# generated by tools/project_public.py — do not edit; regenerate from the development repository\n"
        f"source_revision: {full}\nfiles: {len(pairs)}\n", encoding="utf-8")
    return len(pairs)


def run_tests(out: Path) -> int:
    rc = 0
    for args in (["-m", "unittest", "discover", "-s", "kb/tests", "-t", "."], ["-m", "unittest", "discover", "-s", "tools/tests"]):
        p = subprocess.run([sys.executable, *args], cwd=out, capture_output=True, text=True)
        tail = (p.stdout + p.stderr).strip().splitlines()[-3:]
        print(f"{' '.join(args[2:5])}: exit {p.returncode} — " + " | ".join(tail))
        rc = rc or p.returncode
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["scan", "build"])
    ap.add_argument("--repo", default=str(KIT))
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--out", help="build: the public working tree")
    ap.add_argument("--test", action="store_true", help="build: run kb and tools tests inside the projection")
    ap.add_argument("--all", action="store_true", help="scan: list every hit, not the first 40")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    m, pairs = plan(repo, a.rev)
    hits = scan(repo, a.rev, m, pairs)
    label = "working tree" if a.rev == WORKTREE else git(repo, "rev-parse", "--short", a.rev).strip()
    print(f"projection of {repo.name}@{label}: {len(pairs)} files")
    if hits:
        for line in summary(hits):
            print(line)
        for h in hits if a.all else hits[:40]:
            print(f"  {h['file']}:{h['line']}  [{h['why']}]  {h['text']}")
        if not a.all and len(hits) > 40:
            print(f"  … {len(hits) - 40} more (--all)")
    else:
        print("deny hits: 0")
    if a.action == "scan":
        return 1 if hits else 0
    if not a.out:
        ap.error("build needs --out")
    if a.rev == WORKTREE:
        ap.error("build reads a commit, not the working tree — commit first (a projection must be reproducible)")
    if hits:
        print("build refused: neutralise the hits in the development sources first", file=sys.stderr)
        return 1
    out = Path(a.out).resolve()
    if out == repo or repo in out.parents:
        ap.error("--out must be outside the development repository")
    n = build(repo, a.rev, out, pairs)
    print(f"wrote {n} files to {out}")
    return run_tests(out) if a.test else 0


if __name__ == "__main__":
    sys.exit(main())
