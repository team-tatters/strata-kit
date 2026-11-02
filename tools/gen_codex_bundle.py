#!/usr/bin/env python3
"""Generate the Codex bundle (adapter, Layer 2) from the kit.

  python3 tools/gen_codex_bundle.py [--locale ko] [--out dist/codex/strata-kit]

Produces:
  .codex/skills/<name>/SKILL.md     same canonical head as Claude; body in the requested locale (fallback en)
  instructions/<role>.<locale>.md   developer-instructions text per role (Quilt passes it on thread/start)
  AGENTS.snippet.md                 the paragraph a project's root AGENTS.md should carry for Codex
  README.md                         install notes and the revision stamp
Codex has no reliable hook surface in this kit's scope: deterministic checks run in CI, git hooks and the Quilt gate.
"""
from __future__ import annotations
import argparse, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path
import yaml

KIT = Path(__file__).resolve().parents[1]
LOCALES = ["en", "ko", "ja", "zh", "es", "fr"]

def rev() -> str:
    try:
        r = subprocess.run(["git", "-C", str(KIT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip() or "unborn"
        dirty = subprocess.run(["git", "-C", str(KIT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
        return r + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"

def t(m, locale):
    if isinstance(m, str): return m
    return m.get(locale) or m.get("en") or m.get("ko") or ""

def split_skill(md: str):
    m = re.match(r"(---\n.*?\n---\n\n# [^\n]+\n\n```yaml\n.*?```\n)(.*)$", md, re.S)
    if not m: raise SystemExit("skill file does not match the standard head: " + md[:80])
    return m.group(1), m.group(2)

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--locale", default="en", choices=LOCALES)
    ap.add_argument("--out", default=str(KIT / "dist" / "codex" / "strata-kit")); a = ap.parse_args()
    out = Path(a.out); core_rev = rev(); stamp = f"<!-- strata-kit adapter | core_revision: {core_rev} | locale: {a.locale} | {date.today()} -->"
    if out.exists(): shutil.rmtree(out)
    n = 0
    # core skills only: packs reach a person through the user layer (`kb skills install`), never the bundle (DEC-2026-10-31-36)
    for sk in sorted((KIT / "skills").glob("*/SKILL.md")):
        head, body = split_skill(sk.read_text(encoding="utf-8"))
        loc = sk.parent / "i18n" / f"{a.locale}.md"
        if a.locale != "en" and loc.is_file():
            lb = loc.read_text(encoding="utf-8"); body = "\n" + (lb.split("\n", 1)[1] if lb.startswith("# ") else lb).lstrip("\n")
        d = out / ".codex" / "skills" / sk.parent.name; d.mkdir(parents=True)
        (d / "SKILL.md").write_text(head + stamp + "\n" + body, encoding="utf-8")
        for extra in ("references", "scripts"):
            if (sk.parent / extra).is_dir(): shutil.copytree(sk.parent / extra, d / extra)
        n += 1
    roles = yaml.safe_load((KIT / "core" / "roles" / "agent-roles.yaml").read_text(encoding="utf-8"))
    const = yaml.safe_load((KIT / "core" / "constitution" / "constitution.yaml").read_text(encoding="utf-8")).get("constitution", {})
    (out / "instructions").mkdir()
    for r in roles.get("roles", []):
        lines = [stamp, f"# {t(r['label'], a.locale)} ({r['quilt_role']})", "", t(r["duty"], a.locale), "",
                 "## Must not", ""] + [f"- {t(x, a.locale)}" for x in r.get("must_not", [])]
        lines += ["", "## Constitution (must cards)", ""] + [f"- {c}" for c in const.get("articles", [])]
        lines += ["", "## Entry", "", "Invoke `$using-strata` before the first action unless dispatched for one concrete task.", ""]
        (out / "instructions" / f"{r['id']}.{a.locale}.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "AGENTS.snippet.md").write_text("\n".join([stamp, "## Codex", "",
        "- Skills are installed under `.codex/skills/`; invoke them by name (`$using-strata`, `$strata.spec`, ...).",
        "- `$using-strata` runs first in every thread; it prints the strata header and routes the task.",
        "- Hooks are not relied on: layer and naming checkers run in CI and git pre-commit; approvals go through the Quilt gate when the thread runs under Quilt.",
        f"- Constitution {const.get('version')} ({len(const.get('articles', []))} must cards), core revision `{core_rev}`.", ""]), encoding="utf-8")
    (out / "README.md").write_text("\n".join([stamp, "# strata-kit (Codex bundle)", "",
        f"Generated from strata-kit core revision `{core_rev}` for locale `{a.locale}`. Regenerate with `tools/gen_codex_bundle.py`.", "",
        "Install: copy `.codex/skills/` into the project (or `~/.codex/skills/` for all projects); append `AGENTS.snippet.md` to the root AGENTS.md; Quilt passes `instructions/<role>.<locale>.md` as developer instructions on thread/start.", ""]), encoding="utf-8")
    print(f"codex bundle written to {out}: {n} skills, {len(roles.get('roles', []))} role instructions, core {core_rev}, locale {a.locale}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
