"""python3 -m kb vault-init <dir> [--project NAME] [--detached] — a starter vault (MB-strata-kit-2026-048).

Creates the global settings from core/templates/vault (_meta/taxonomy.yaml, env-config.yaml), the index folder, a
.gitignore for the store and per-machine files, and — with --project — one project laid out as the onboarding
procedure in core/docs/en/knowledge-base/vault-structure.md describes: overview.md, _meta/taxonomy.yaml and toc.yaml
from the templates, the four knowledge-base categories, sessions/ and tasks/, and strata/profile.yaml for a detached
project. Existing files are never overwritten; the command lists what it created and what it left alone.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
TEMPLATES = KIT / "core" / "templates" / "vault"
NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

GITIGNORE = """# strata vault — generated and per-machine files
.kb/store.sqlite
.kb/store.sqlite-*
.local/
.DS_Store
"""


def _write(path: Path, text: str, made: list[str], kept: list[str], root: Path) -> None:
    rel = str(path.relative_to(root))
    if path.exists():
        kept.append(rel)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    made.append(rel)


def _dir(path: Path, made: list[str], root: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True)
        made.append(str(path.relative_to(root)) + "/")


def _env_config(today: str) -> str:
    """The environment registry with this machine filled in — the template's {{…}} placeholders are not valid YAML."""
    import os, platform
    alias = re.sub(r"[^a-z0-9-]+", "-", (os.environ.get("STRATA_ENV") or platform.node().split(".")[0] or "this-machine").lower()).strip("-") or "this-machine"
    values = {"MACHINE_ALIAS": alias, "MACHINE_DESC": "registered by kb vault-init", "OS": platform.system().lower() or "unknown",
              "SHELL": Path(os.environ.get("SHELL", "sh")).name, "DATE": today}
    from kb.machine import current_fingerprint   # MB-strata-kit-2026-049
    values["FINGERPRINT"] = current_fingerprint() or ""
    text = (TEMPLATES / "env-config.yaml.template").read_text(encoding="utf-8")
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)


def init(root: Path, project: str | None = None, detached: bool = False, today: str | None = None) -> tuple[list[str], list[str]]:
    today = today or date.today().isoformat()
    made: list[str] = []
    kept: list[str] = []
    root.mkdir(parents=True, exist_ok=True)
    _write(root / ".gitignore", GITIGNORE, made, kept, root)
    _write(root / "_meta" / "taxonomy.yaml", (TEMPLATES / "_meta" / "taxonomy.yaml").read_text(encoding="utf-8"), made, kept, root)
    _write(root / "env-config.yaml", _env_config(today), made, kept, root)
    _write(root / "_index" / "projects.md", "# Projects\n\n" + (f"- [[{project}/overview|{project}]]\n" if project else ""), made, kept, root)
    _dir(root / "projects", made, root)
    if project:
        p = root / "projects" / project
        _write(p / "overview.md",
               f"---\ntitle: \"{project}\"\ntype: overview\nproject: {project}\ntags: []\ncreated: {today}\nupdated: {today}\nstatus: active\n---\n\n"
               "# Purpose\n\n# Tech stack\n\n# Strata layer mapping\n\n# What is never included\n", made, kept, root)
        _write(p / "_meta" / "taxonomy.yaml", (TEMPLATES / "_meta" / "taxonomy.project.yaml.template").read_text(encoding="utf-8"), made, kept, root)
        _write(p / "_meta" / "toc.yaml", (TEMPLATES / "_meta" / "toc.yaml.template").read_text(encoding="utf-8"), made, kept, root)
        for cat in ("domain", "architecture", "guides", "references"):
            _write(p / "knowledge-base" / cat / "_index.md", f"# {cat.capitalize()}\n", made, kept, root)
        _write(p / "knowledge-base" / "_index.md", f"# {project} knowledge base\n", made, kept, root)
        for d in ("sessions", "tasks"):
            _dir(p / d, made, root)
        if detached:
            _write(p / "strata" / "profile.yaml",
                   f"# placement profile manifest — detached (Tier P lives here, not in the code repository)\nprofile: detached\nproject: {project}\n",
                   made, kept, root)
    return made, kept


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kb vault-init", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", help="the vault folder (created if missing)")
    ap.add_argument("--project", help="also lay out one project (lowercase, digits, . _ -)")
    ap.add_argument("--detached", action="store_true", help="the project keeps its Tier P in the vault (strata/profile.yaml)")
    a = ap.parse_args(argv)
    if a.project and not NAME.match(a.project):
        ap.error(f"--project {a.project!r}: use lowercase letters, digits, '.', '_' or '-'")
    if a.detached and not a.project:
        ap.error("--detached needs --project")
    root = Path(a.dir).expanduser().resolve()
    made, kept = init(root, a.project, a.detached)
    for m in made:
        print(f"created  {m}")
    for k in kept:
        print(f"kept     {k} (exists)")
    print(f"\nvault: {root}\nnext: export STRATA_VAULT={root} — and `git init` there if you want history and sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
