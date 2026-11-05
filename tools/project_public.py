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
  python3 tools/project_public.py fingerprint public/docs/ko/<page>.md   # translated_from for the en page
  python3 tools/project_public.py preview --out DIR     # working tree, draft pages included — for building the site
                                                        # locally (DEC-2026-11-02-10); never publish a preview

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


def plan(repo: Path, rev: str = "HEAD", drafts: bool = False) -> tuple[dict, list[tuple[str, str]]]:
    """(manifest, [(source path, target path)]) for the tracked files at rev."""
    m = load_manifest(repo, rev)
    tracked = listed(repo, rev)
    inc, exc = m.get("include") or [], m.get("exclude") or []
    pairs = [(p, p) for p in tracked if matches(p, inc) and not matches(p, exc)]
    have = set(tracked)
    dpairs, m["_docs_problems"] = docs_plan(repo, rev, tracked, drafts)
    pairs += dpairs
    for src, dst in (m.get("map") or {}).items():
        if src.endswith("/**"):   # a whole folder (DEC-2026-11-02-10): public/site/** -> site/
            prefix = src[:-2]
            under = [p for p in tracked if p.startswith(prefix)]
            if not under:
                raise SystemExit(f"map source {src} has no tracked files at {rev}")
            pairs += [(p, dst.rstrip("/") + "/" + p[len(prefix):]) for p in under]
            continue
        if src not in have:
            raise SystemExit(f"map source {src} is not tracked at {rev}")
        pairs.append((src, dst))
    targets = [d for _, d in pairs]
    dup = sorted({d for d in targets if targets.count(d) > 1})
    if dup:
        raise SystemExit("two sources project to the same path: " + ", ".join(dup))
    return m, sorted(pairs, key=lambda x: x[1])


DOCS = "public/docs"


def front(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    try:
        return yaml.safe_load(text.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def fingerprint(data: bytes) -> str:
    """The ko source fingerprint an en translation records as translated_from (first 12 hex of sha256)."""
    import hashlib
    return hashlib.sha256(data).hexdigest()[:12]


def docs_plan(repo: Path, rev: str, tracked: list[str], drafts: bool = False) -> tuple[list[tuple[str, str]], list[str]]:
    """Public docs (DEC-2026-11-02-09): ready ko pages go to docs/ko/, ready en pages to docs/ (English is the default),
    drafts stay out. A ready ko page needs its en page, and the en page's translated_from must match the ko content —
    otherwise the page is 'translation pending' and the build stops. Files that are not pages (images/) go with their
    locale whatever the pages' status (DEC-2026-11-02-10). drafts=True (preview) takes every page and checks nothing."""
    pairs, problems = [], []
    for p in tracked:
        for loc, target in (("ko", "docs/ko/"), ("en", "docs/")):
            if p.startswith(f"{DOCS}/{loc}/") and not p.endswith(".md"):
                pairs.append((p, target + p[len(DOCS) + 4:]))
    if drafts:
        ko_pages = {p[len(DOCS) + 4:]: p for p in tracked if p.startswith(f"{DOCS}/ko/") and p.endswith(".md")}
        en_pages = {p[len(DOCS) + 4:]: p for p in tracked if p.startswith(f"{DOCS}/en/") and p.endswith(".md")}
        pairs += [(p, f"docs/ko/{rel}") for rel, p in ko_pages.items()]
        # an English page not written yet: the Korean draft stands in, so the preview's links still resolve
        pairs += [(en_pages.get(rel, p), f"docs/{rel}") for rel, p in ko_pages.items()]
        pairs += [(p, f"docs/{rel}") for rel, p in en_pages.items() if rel not in ko_pages]
        return pairs, problems
    ko = {p[len(DOCS) + 4:]: p for p in tracked if p.startswith(f"{DOCS}/ko/") and p.endswith(".md")}
    en = {p[len(DOCS) + 4:]: p for p in tracked if p.startswith(f"{DOCS}/en/") and p.endswith(".md")}
    for rel, src in sorted(ko.items()):
        data = read(repo, rev, src)
        if front(data.decode("utf-8", "replace")).get("status") != "ready":
            continue
        pairs.append((src, f"docs/ko/{rel}"))
        if rel not in en:
            problems.append(f"translation pending: {src} is ready but {DOCS}/en/{rel} does not exist")
            continue
        fm = front(read(repo, rev, en[rel]).decode("utf-8", "replace"))
        if str(fm.get("translated_from", "")) != fingerprint(data):
            problems.append(f"translation pending: {DOCS}/en/{rel} was translated from {fm.get('translated_from') or 'nothing'}, "
                            f"the ko page is now {fingerprint(data)} — re-translate, then set translated_from")
            continue
        if fm.get("status") == "ready":
            pairs.append((en[rel], f"docs/{rel}"))
        else:
            problems.append(f"translation pending: {DOCS}/en/{rel} is not marked ready")
    return pairs, problems


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


def scan_tree(out: Path, m: dict) -> list[dict]:
    """Deny scan over generated pages in the built tree (docs/**/reference)."""
    rules = [(re.compile(d["pattern"], re.I), d) for d in m.get("deny") or []]
    hits = []
    for p in sorted(out.glob("docs/**/reference/*.md")):
        rel = str(p.relative_to(out))
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for rx, d in rules:
                if rel not in (d.get("allow") or []) and rx.search(line):
                    hits.append({"file": rel, "line": i, "why": d.get("why", ""), "text": line.strip()[:160]})
    return hits


def summary(hits: list[dict]) -> list[str]:
    by_dir: dict[str, set] = {}
    for h in hits:
        top = "/".join(h["file"].split("/")[:2]) if "/" in h["file"] else h["file"]
        by_dir.setdefault(top, set()).add(h["file"])
    L = [f"deny hits: {len(hits)} lines in {len({h['file'] for h in hits})} files"]
    L += [f"  {len(fs):4d} files  {d}" for d, fs in sorted(by_dir.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    return L


def build(repo: Path, rev: str, out: Path, pairs: list[tuple[str, str]], preview: bool = False) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():
        if child.name == ".git":
            continue
        shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
    for src, dst in pairs:
        target = out / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read(repo, rev, src))
        if rev == WORKTREE:
            target.chmod((repo / src).stat().st_mode & 0o777)
        elif git(repo, "ls-tree", rev, "--", src).split()[0] == "100755":
            target.chmod(0o755)
    # reference tables are generated from the projected sources themselves, so they match this revision exactly
    import importlib.util
    gen_file = out / "tools" / "gen_public_reference.py"
    gen = None
    if gen_file.is_file():
        spec = importlib.util.spec_from_file_location("gen_public_reference", gen_file)
        gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
    for rel, text in (gen.generate(out).items() if gen else []):
        locale, rest = rel.split("/", 1)
        target = out / "docs" / (rest if locale == "en" else f"ko/{rest}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    full = git(repo, "rev-parse", "HEAD" if rev == WORKTREE else rev).strip()
    (out / ".strata-projection.yaml").write_text(
        f"# generated by tools/project_public.py — do not edit; regenerate from the development repository\n"
        f"source_revision: {full}{' + working tree' if rev == WORKTREE else ''}\nfiles: {len(pairs)}\n"
        + ("preview: true   # draft pages included — not for publishing\n" if preview else ""), encoding="utf-8")
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
    ap.add_argument("action", choices=["scan", "build", "preview", "fingerprint"])
    ap.add_argument("path", nargs="?", help="fingerprint: a public/docs/ko page — prints the translated_from value for its en page")
    ap.add_argument("--repo", default=str(KIT))
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--out", help="build: the public working tree")
    ap.add_argument("--test", action="store_true", help="build: run kb and tools tests inside the projection")
    ap.add_argument("--all", action="store_true", help="scan: list every hit, not the first 40")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    if a.action == "fingerprint":
        if not a.path:
            ap.error("fingerprint needs a public/docs/ko page")
        print(fingerprint((repo / a.path).read_bytes()))
        return 0
    if a.action == "preview":
        a.rev = WORKTREE
    m, pairs = plan(repo, a.rev, drafts=a.action == "preview")
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
    problems = m.get("_docs_problems") or []
    for pr in problems:
        print(f"  docs: {pr}")
    if a.action == "fingerprint":
        return 0
    if a.action == "scan":
        return 1 if hits or problems else 0
    if not a.out:
        ap.error("build needs --out")
    if a.rev == WORKTREE and a.action == "build":
        ap.error("build reads a commit, not the working tree — commit first (a projection must be reproducible)")
    if hits or problems:
        print("build refused: " + ("neutralise the deny hits" if hits else "") + (" and " if hits and problems else "")
              + ("finish the pending translations" if problems else "") + " in the development sources first", file=sys.stderr)
        return 1
    out = Path(a.out).resolve()
    if out == repo or repo in out.parents:
        ap.error("--out must be outside the development repository")
    n = build(repo, a.rev, out, pairs, preview=a.action == "preview")
    print(f"wrote {n} files to {out} (+ generated reference pages)")
    late = scan_tree(out, m)
    if late:
        for h in late[:20]:
            print(f"  {h['file']}:{h['line']}  [{h['why']}]  {h['text']}")
        print("build failed: a generated page carries a deny hit — fix its source", file=sys.stderr)
        return 1
    return run_tests(out) if a.test else 0


if __name__ == "__main__":
    sys.exit(main())
