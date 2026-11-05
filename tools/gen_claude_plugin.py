#!/usr/bin/env python3
"""Generate the Claude Code plugin (adapter, Layer 2) from the kit.

  python3 tools/gen_claude_plugin.py [--locale ko] [--out dist/claude/strata-kit] [--allow-dirty]

Refuses a dirty kit working tree unless --allow-dirty, so the stamped core_revision is a commit.

Produces:
  .claude-plugin/plugin.json      plugin manifest (name, version, description)
  skills/<name>/SKILL.md          frontmatter + yaml block (English) + body in the requested locale (fallback en)
  agents/<role>.md                one agent profile per role from core/roles/agent-roles.yaml
  hooks/hooks.json                SessionStart prints the strata header (tools/wizard.py header)
  .mcp.json                       knowledge-base MCP server = uv run --directory $STRATA_KIT --extra embed strata-kb-mcp (hybrid search needs the embed extra)
  README.md                       install notes and the revision stamp
Every generated file carries core_revision so a project can detect a stale adapter.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys
from datetime import date, datetime, timezone
from pathlib import Path
import yaml

KIT = Path(__file__).resolve().parents[1]
LOCALES = ["en", "ko", "ja", "zh", "es", "fr"]

HEADER_HOOK = ('K="${STRATA_KIT:-$HOME/workspace/strata-kit}"; '
               '[ -f "$K/tools/wizard.py" ] || { echo "strata: wizard not found at $K (set STRATA_KIT)"; exit 0; }; '
               'out=$("${STRATA_PYTHON:-python3}" "$K/tools/wizard.py" header "$PWD" 2>&1) && printf "%s\\n" "$out" '
               '|| printf "strata: wizard header failed — %s\\n" "$(printf "%s" "$out" | tail -1)"')
# PreCompact: snapshot this session's active file (planning/active-file-and-compact-hooks). Never blocks compaction —
# a missing kit or a failing snapshot is one line and exit 0; outside a strata project it writes nothing.
PRECOMPACT_HOOK = ('K="${STRATA_KIT:-$HOME/workspace/strata-kit}"; '
                   '[ -f "$K/kb/__main__.py" ] || { echo "strata: kb not found at $K (set STRATA_KIT)"; exit 0; }; '
                   '"${STRATA_PYTHON:-python3}" "$K/kb" pre-compact || echo "strata: pre-compact snapshot failed"; exit 0')
# Both hooks run the kit with STRATA_PYTHON (Claude Code settings env) when it is set — the one python the wizard's
# runtime step chose for every execution path (MB-strata-kit-2026-058) — and fall back to python3 otherwise.
# what the plugin registers, for the generated guidance's harness event table (tools/wizard.py _claude_hooks_section)
PLUGIN_HOOKS = {"SessionStart": "plugin: wizard header", "PreCompact": "plugin: kb pre-compact"}


def stamp_revision(allow_dirty: bool, kit: Path | None = None) -> str:
    """The core_revision to stamp: the HEAD commit of a clean tree. A dirty tree is refused unless allow_dirty — then
    the stamp says `+dirty`, because an adapter built from uncommitted files names no commit anyone can check out
    (audit 2026-11-05: the installed plugin carried 0a49bd1fba0e+dirty)."""
    kit = kit or KIT
    try:
        r = subprocess.run(["git", "-C", str(kit), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip() or "unborn"
        dirty = [l[3:] for l in subprocess.run(["git", "-C", str(kit), "status", "--porcelain"], capture_output=True, text=True).stdout.splitlines() if l.strip()]
    except Exception:
        return "unknown"
    if dirty and not allow_dirty:
        raise SystemExit(f"refused: the kit working tree is dirty ({len(dirty)} paths: {', '.join(dirty[:5])}{' …' if len(dirty) > 5 else ''}) — "
                         "commit or stash first, or pass --allow-dirty for a local trial (stamped +dirty)")
    return r + ("+dirty" if dirty else "")

def plugin_version() -> str:
    """0.1.<kit commit count>, plus -dev.<UTC stamp> on a dirty tree. A fixed version made `claude plugin update`
    report 'already at the latest version' and keep a stale cache (order 2026.10.29-01 task-05)."""
    try:
        n = subprocess.run(["git", "-C", str(KIT), "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout.strip() or "0"
        dirty = subprocess.run(["git", "-C", str(KIT), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    except Exception:
        n, dirty = "0", "?"
    return f"0.1.{n}" + (f"-dev.{datetime.now(timezone.utc):%Y%m%d%H%M%S}" if dirty else "")

def t(m, locale):
    if isinstance(m, str): return m
    return m.get(locale) or m.get("en") or m.get("ko") or ""

def split_skill(md: str):
    """frontmatter+H1+yaml block (canonical head) | body"""
    m = re.match(r"(---\n.*?\n---\n\n# [^\n]+\n\n```yaml\n.*?```\n)(.*)$", md, re.S)
    if not m: raise SystemExit("skill file does not match the standard head: " + md[:80])
    return m.group(1), m.group(2)

def write_marketplace(root: Path, core_rev: str) -> None:
    """A directory marketplace next to the plugins so Claude Code can install them:
         claude plugin marketplace add <root>   →   claude plugin install strata-kit@strata-kit
    Every plugin directory under root (one per locale) becomes an entry. After regenerating, run
    `claude plugin marketplace update strata-kit` and `claude plugin update strata-kit@strata-kit`."""
    plugins = sorted(d for d in root.iterdir() if (d / ".claude-plugin" / "plugin.json").is_file())
    entries = []
    for d in plugins:
        meta = json.loads((d / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        entries.append({"name": meta["name"], "source": f"./{d.name}", "description": meta["description"]})
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
        "name": "strata-kit", "description": f"strata-kit adapters generated from core {core_rev} (one plugin per locale)",
        "owner": {"name": "n0roo"}, "plugins": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--locale", default="en", choices=LOCALES)
    ap.add_argument("--allow-dirty", action="store_true", help="generate from a dirty working tree (stamped +dirty; local trials only)")
    ap.add_argument("--out", default=str(KIT / "dist" / "claude" / "strata-kit")); a = ap.parse_args()
    out = Path(a.out); core_rev = stamp_revision(a.allow_dirty); stamp = f"<!-- strata-kit adapter | core_revision: {core_rev} | locale: {a.locale} | {date.today()} -->"
    if out.exists(): shutil.rmtree(out)
    (out / ".claude-plugin").mkdir(parents=True)
    (out / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": out.name, "version": plugin_version(),
        "description": f"Strata methodology kit: recommendation cards, profiles, skills and the guidance wizard (core {core_rev}, locale {a.locale})",
        "author": {"name": "n0roo"}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # skills
    n = 0
    # core skills only: packs reach a person through the user layer (`kb skills install`), never the plugin (DEC-2026-10-31-36)
    for sk in sorted((KIT / "skills").glob("*/SKILL.md")):
        head, body = split_skill(sk.read_text(encoding="utf-8"))
        loc = sk.parent / "i18n" / f"{a.locale}.md"
        if a.locale != "en" and loc.is_file():
            lb = loc.read_text(encoding="utf-8")
            body = lb.split("\n", 1)[1] if lb.startswith("# ") else lb   # drop the localized H1
            body = "\n" + body.lstrip("\n")
        d = out / "skills" / sk.parent.name; d.mkdir(parents=True)
        (d / "SKILL.md").write_text(head + stamp + "\n" + body, encoding="utf-8")
        for extra in ("references", "scripts"):
            if (sk.parent / extra).is_dir(): shutil.copytree(sk.parent / extra, d / extra)
        n += 1
    # agents from roles
    roles = yaml.safe_load((KIT / "core" / "roles" / "agent-roles.yaml").read_text(encoding="utf-8"))
    (out / "agents").mkdir()
    for r in roles.get("roles", []):
        lines = ["---", f"name: strata-{r['id']}", f"description: {t(r['label'], 'en')} ({r['quilt_role']}). {t(r['duty'], 'en')}", "---", "",
                 stamp, f"# {t(r['label'], a.locale)}", "", t(r["duty"], a.locale), "", "## Must not", ""]
        lines += [f"- {t(x, a.locale)}" for x in r.get("must_not", [])]
        lines += ["", "## Tools", ""] + [f"- {x}" for x in r.get("tools", [])]
        lines += ["", "## Entry", "", "Start with the `using-strata` skill unless dispatched as a subagent for one concrete task.", ""]
        (out / "agents" / f"strata-{r['id']}.md").write_text("\n".join(lines), encoding="utf-8")
    # MCP: the knowledge-base server lives in the kit (DEC-2026-10-28-11); STRATA_KIT names the checkout
    (out / ".mcp.json").write_text(json.dumps({"knowledge-base": {
        # DEC-2026-10-29-20: light by default; STRATA_KB_EMBED=1 in the environment adds the embed extra (bge-m3 hybrid search)
        "type": "stdio", "command": "sh", "args": ["-c", 'exec uv run --directory "$STRATA_KIT" ${STRATA_KB_EMBED:+--extra embed} strata-kb-mcp'], "env": {}}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # hooks: SessionStart header — a missing kit and a failing header are told apart, the failure's last line is shown (order 2026.10.29-14)
    (out / "hooks").mkdir()
    (out / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {
        "SessionStart": [{"matcher": "", "hooks": [{"type": "command", "command": HEADER_HOOK, "timeout": 10}]}],
        "PreCompact": [{"matcher": "", "hooks": [{"type": "command", "command": PRECOMPACT_HOOK, "timeout": 10}]}]}},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "README.md").write_text("\n".join([stamp, "# strata-kit (Claude Code plugin)", "",
        f"Generated from strata-kit core revision `{core_rev}` for locale `{a.locale}`. Do not edit here; regenerate with `tools/gen_claude_plugin.py`.", "",
        "Install for local development: `claude --plugin-dir <this directory>`. Permanent install: `claude plugin marketplace add <parent directory>` then `claude plugin install " + out.name + "@strata-kit`; after regenerating run `claude plugin marketplace update strata-kit` and `claude plugin update " + out.name + "@strata-kit`.", "",
        "Hooks: SessionStart prints the strata header, and after a compaction (source `compact`) a short restore note instead — this session's next action and the latest handoff's. PreCompact snapshots this session's active file into `.strata/local/last-compaction.yaml`, only in strata projects, and never blocks compaction. This session's active file is the one named for the harness session id or holding it in `harness_session_id`. Set `STRATA_KIT` if the kit is not at `~/workspace/strata-kit`.", "",
        "The plugin also registers the `knowledge-base` MCP server (`uv run --directory $STRATA_KIT strata-kb-mcp`): `STRATA_KIT` and `STRATA_VAULT` must be in the environment, and `uv` on PATH. Embeddings are optional (DEC-2026-10-29-20): set `STRATA_KB_EMBED=1` to start it with the embed extra (sentence-transformers·torch, bge-m3 hybrid search); without it search runs on FTS and says so in each result's mode. The methodology's tools (`python3 -m kb` decision, order, handoff gates, coverage, enforce) do not need the MCP server. Remove any older global `knowledge-base` registration (`claude mcp remove knowledge-base -s user`).", ""]), encoding="utf-8")
    write_marketplace(out.parent, core_rev)
    print(f"plugin written to {out}: {n} skills, {len(roles.get('roles', []))} agents, core {core_rev}, locale {a.locale}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
