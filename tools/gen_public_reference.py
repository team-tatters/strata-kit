#!/usr/bin/env python3
"""Generate the reference pages of the public docs from their sources (DEC-2026-11-02-09).

  python3 tools/gen_public_reference.py --out DIR [--locale ko|en|all]

Writes DIR/<locale>/reference/{cards,skills,cli,profiles}.md. Nothing here is written by hand: cards from
core/cards/*.yaml (their own six-locale fields), skills from skills/*/SKILL.md and skills/*/i18n/ko.md (overview
paragraph), commands from the `kb` and wizard help text, profiles from profiles/*/profile.yaml. Decision and backlog
ids are dropped from the text — public docs explain without pointing into private records. tools/project_public.py
calls this while building the projection, so a published table always matches the revision it came from.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[1]
LOCALES = ("ko", "en")
IDS = re.compile(r"\s*\((?:[^()]*?\b(?:DEC|MB)-[\w-]+[^()]*)\)|\b(?:DEC|MB)-[A-Za-z0-9-]*\d{2,}[A-Za-z0-9-]*")
T = {
    "ko": {"cards": "카드", "skills": "스킬", "cli": "명령", "profiles": "프로필", "gen": "이 문서는 원천에서 생성된다 — 손으로 고치지 않는다.",
           "id": "카드", "strength": "강도", "claim": "주장", "applies": "적용", "skill": "스킬", "what": "무엇을 하나",
           "profile": "프로필", "status": "상태", "layers": "레이어", "checkers": "검사기",
           "cards_lede": "권고 카드 전체. must 는 협상하지 않고, should 는 사유를 남기면 끌 수 있으며, may 는 조언이다.",
           "skills_lede": "에이전트가 따르는 절차. 각 스킬은 증거 요구로 끝난다.",
           "cli_lede": "kit 의 명령줄 도구. 자세한 옵션은 각 명령의 --help.",
           "profiles_lede": "스택별 묶음. active 는 실제 프로젝트에서 검사기가 돈 기록이 있는 프로필이다."},
    "en": {"cards": "Cards", "skills": "Skills", "cli": "Commands", "profiles": "Profiles", "gen": "This page is generated from the sources — do not edit it by hand.",
           "id": "Card", "strength": "Strength", "claim": "Claim", "applies": "Applies when", "skill": "Skill", "what": "What it does",
           "profile": "Profile", "status": "Status", "layers": "Layers", "checkers": "Checkers",
           "cards_lede": "Every recommendation card. `must` is not negotiated, `should` can be switched off with a recorded reason, `may` is advice.",
           "skills_lede": "Procedures the agent follows. Every skill ends with evidence requirements.",
           "cli_lede": "The kit's command-line tools. Each command's --help lists its options.",
           "profiles_lede": "Per-stack bundles. Active means a checker for the profile's rules has run on a real project and left a record."},
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", IDS.sub("", str(text or ""))).strip().replace("|", "\\|")


def loc(v, locale: str) -> str:
    if isinstance(v, dict):
        return v.get(locale) or v.get("en") or ""
    return v or ""


def cards(kit: Path, locale: str) -> str:
    rows = []
    for p in sorted((kit / "core" / "cards").glob("*.yaml")):
        c = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("card") or {}
        if c.get("status") != "active":
            continue
        applies = "; ".join(loc(a, locale) for a in (c.get("applies_when") or [])[:2])
        rows.append((["must", "should", "may"].index(c.get("strength", "may")), c["id"],
                     f"| `{c['id']}` | {c.get('strength')} | {clean(loc(c.get('short_claim') or c.get('claim'), locale))} | {clean(applies)} |"))
    t = T[locale]
    head = [f"| {t['id']} | {t['strength']} | {t['claim']} | {t['applies']} |", "|---|---|---|---|"]
    return "\n".join([t["cards_lede"], "", *head, *[r[2] for r in sorted(rows)]])


def _overview(path: Path) -> str:
    """The first paragraph under the overview heading of a skill body (en: '## Overview', ko: '## 개요')."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## (?:Overview|개요)\s*\n+(.+?)(?:\n\s*\n|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def skills(kit: Path, locale: str) -> str:
    t = T[locale]
    rows = []
    for d in sorted([*(kit / "skills").glob("*/"), *(kit / "skills" / "packs").glob("*/*/")]):
        sk = d / "SKILL.md"
        if not sk.is_file():
            continue
        name = re.search(r"^name:\s*(\S+)", sk.read_text(encoding="utf-8"), re.M)
        if not name:
            continue
        text = _overview(d / "i18n" / "ko.md") if locale == "ko" else ""
        text = text or _overview(sk)
        pack = " (pack)" if "/packs/" in str(d) else ""
        rows.append(f"| `{name.group(1)}`{pack} | {clean(text)} |")
    return "\n".join([t["skills_lede"], "", f"| {t['skill']} | {t['what']} |", "|---|---|", *rows])


def cli(kit: Path, locale: str) -> str:
    t = T[locale]
    kb_help = subprocess.run([sys.executable, str(kit / "kb")], capture_output=True, text=True, cwd=kit)
    kb_text = IDS.sub("", (kb_help.stdout or kb_help.stderr).strip())
    tools = []
    for name in ("wizard.py", "doctor.py", "project_public.py", "gen_claude_plugin.py", "gen_codex_bundle.py"):
        p = kit / "tools" / name
        if p.is_file():
            doc = re.search(r'^"""(.+?)(?:\n\n|""")', p.read_text(encoding="utf-8"), re.S)
            tools.append(f"| `tools/{name}` | {clean(doc.group(1) if doc else '')} |")
    return "\n".join([t["cli_lede"], "", "## python3 -m kb", "", "```text", kb_text, "```", "", "## tools/", "",
                      "| | |", "|---|---|", *tools])


def profiles(kit: Path, locale: str) -> str:
    t = T[locale]
    rows = []
    for p in sorted((kit / "profiles").glob("*/profile.yaml")):
        d = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("profile") or {}
        rows.append(f"| `{d.get('id')}` | {d.get('status')} | {clean(d.get('layers') or '-')} | {clean(', '.join(d.get('enforcement') or []) or '-')} |")
    return "\n".join([t["profiles_lede"], "", f"| {t['profile']} | {t['status']} | {t['layers']} | {t['checkers']} |", "|---|---|---|---|", *rows])


def generate(kit: Path = KIT, locales=LOCALES) -> dict[str, str]:
    out = {}
    for locale in locales:
        t = T[locale]
        for key, fn in (("cards", cards), ("skills", skills), ("cli", cli), ("profiles", profiles)):
            out[f"{locale}/reference/{key}.md"] = (f"---\ntitle: {t[key]}\nstatus: ready\ngenerated: true\n---\n\n# {t[key]}\n\n"
                                                   f"> {t['gen']}\n\n{fn(kit, locale)}\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--locale", default="all", choices=["all", *LOCALES])
    a = ap.parse_args(argv)
    locales = LOCALES if a.locale == "all" else (a.locale,)
    out = Path(a.out)
    for rel, text in generate(KIT, locales).items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8")
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
