#!/usr/bin/env python3
"""Validate recommendation cards, the constitution and the profile manifests against core/schemas/card.schema.yaml
and core/schemas/profile.schema.yaml (subset).

Checks: id pattern and file name, strength enum, status enum, evidence >= 1 with kind enum,
localized maps carry en and ko, active must cards carry short_claim, constitution articles exist and are must, supersedes targets exist;
profiles: id equals the folder, status enum, detect keys and shapes, list fields, default/excluded cards exist,
source paths exist.
Exit 2 on any error. Usage: python3 tools/cards_check.py [--root <kit>]
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
import yaml

ID = re.compile(r"^rec\.[a-z0-9-]+(\.[a-z0-9-]+)+$")
PROFILE_ID = re.compile(r"^[a-z]+(\.[a-z0-9-]+)+$")
DETECT = {"any_files", "any_glob", "any_content", "languages"}
FACTS = {"uses_vault", "uses_quilt", "domain_work"}   # project facts the wizard decides (DEC-2026-10-30-01)
STRENGTH, STATUS, KIND = {"must", "should", "may"}, {"draft", "active", "superseded", "withdrawn"}, {"reference", "decision", "measurement"}

def loc_ok(v) -> bool:
    return isinstance(v, dict) and "en" in v and "ko" in v

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=".")
    root = Path(ap.parse_args().root).resolve(); errs = []
    cards = {}
    for p in sorted((root / "core" / "cards").glob("*.yaml")):
        c = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("card")
        if not c: errs.append(f"{p.name}: no 'card' root"); continue
        cid = c.get("id", "")
        if not ID.match(cid): errs.append(f"{p.name}: bad id {cid!r}")
        if p.stem != cid: errs.append(f"{p.name}: file name must equal id")
        if c.get("strength") not in STRENGTH: errs.append(f"{cid}: strength {c.get('strength')!r}")
        ad = c.get("adoption")
        if ad not in (None, "opt_in", "conditional"): errs.append(f"{cid}: adoption {ad!r}")
        if ad and c.get("strength") != "must": errs.append(f"{cid}: adoption is for must cards")
        if ad == "conditional" and c.get("condition") not in FACTS: errs.append(f"{cid}: conditional needs condition in {sorted(FACTS)}")
        if c.get("default_when") is not None and (ad != "opt_in" or c["default_when"] not in FACTS): errs.append(f"{cid}: default_when is for opt_in cards, one of {sorted(FACTS)}")
        if c.get("status") not in STATUS: errs.append(f"{cid}: status {c.get('status')!r}")
        for f in ("title", "claim", "verification"):
            if not loc_ok(c.get(f)): errs.append(f"{cid}: {f} needs en and ko")
        # the entry view carries a must card's short_claim; without it the whole claim is loaded every session (MB-strata-kit-2026-045)
        if c.get("strength") == "must" and c.get("status") == "active" and not loc_ok(c.get("short_claim")):
            errs.append(f"{cid}: an active must card needs short_claim (en and ko) for the entry view")
        ev = c.get("evidence") or []
        if not ev: errs.append(f"{cid}: evidence must have at least one entry")
        for e in ev:
            if e.get("kind") not in KIND or not e.get("ref"): errs.append(f"{cid}: evidence entry invalid {e}")
        for lst in ("applies_when", "not_when", "counter_examples"):
            for x in c.get(lst) or []:
                if not loc_ok(x): errs.append(f"{cid}: {lst} item needs en and ko")
        cards[cid] = c
    for cid, c in cards.items():
        for s in c.get("supersedes") or []:
            if s not in cards: errs.append(f"{cid}: supersedes unknown card {s}")
    const = (yaml.safe_load((root / "core" / "constitution" / "constitution.yaml").read_text(encoding="utf-8")) or {}).get("constitution", {})
    for a in const.get("articles", []):
        if a not in cards: errs.append(f"constitution: unknown article {a}")
        elif cards[a].get("strength") != "must": errs.append(f"constitution: article {a} is not must")
        elif cards[a].get("status") != "active": errs.append(f"constitution: article {a} is not active")
        elif cards[a].get("adoption"): errs.append(f"constitution: article {a} is opt-in (adoption) — an article is never optional")
    # DEC-2026-10-30-01: a must card reaches projects as an article, an opt-in question or a condition — never by nothing
    for cid, c in cards.items():
        if c.get("strength") == "must" and c.get("status") == "active" and cid not in const.get("articles", []) and not c.get("adoption"):
            errs.append(f"{cid}: must card with no delivery path (not an article, adoption missing)")
    for k in ("version", "ratified", "last_amended"):
        if not const.get(k): errs.append(f"constitution: missing {k}")
    profiles = sorted((root / "profiles").glob("*/profile.yaml"))
    for p in profiles:
        errs += [f"profile {p.parent.name}: {m}" for m in check_profile(root, p, cards)]
    for e in errs: print("ERROR", e)
    print(f"cards check: {len(cards)} cards, {len(const.get('articles', []))} articles, {len(profiles)} profiles, {len(errs)} errors")
    return 2 if errs else 0

def check_profile(root: Path, path: Path, cards: dict) -> list[str]:
    pr = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("profile")
    if not isinstance(pr, dict): return ["no 'profile' root"]
    out = []
    pid = pr.get("id", "")
    if not PROFILE_ID.match(str(pid)): out.append(f"bad id {pid!r}")
    if pid != path.parent.name: out.append(f"id {pid!r} must equal the folder name")
    if pr.get("status") not in STATUS: out.append(f"status {pr.get('status')!r}")
    for f in ("title", "note"):
        if not loc_ok(pr.get(f)): out.append(f"{f} needs en and ko")
    det = pr.get("detect")
    if not isinstance(det, dict): out.append("detect must be a map ({} for the fallback profile)")
    else:
        for k, v in det.items():
            if k not in DETECT: out.append(f"detect key {k!r} unknown (allowed: {sorted(DETECT)})")
            elif not isinstance(v, list): out.append(f"detect.{k} must be a list")
            elif k == "any_content" and not all(isinstance(x, list) and len(x) == 2 for x in v): out.append("detect.any_content items are [file, substring]")
    if not isinstance(pr.get("layers"), str): out.append("layers must be a string")
    for f in ("enforcement", "cards_default", "cards_excluded"):
        if not isinstance(pr.get(f), list): out.append(f"{f} must be a list")
    for f in ("cards_default", "cards_excluded"):
        for cid in pr.get(f) or []:
            if cid not in cards: out.append(f"{f}: unknown card {cid}")
    for src in [re.sub(r"\s*\(.*\)\s*$", "", x).strip() for x in str(pr.get("source") or "").split(",") if x.strip()]:
        if not (root / src).exists(): out.append(f"source path {src} does not exist")
    return out


if __name__ == "__main__":
    sys.exit(main())
