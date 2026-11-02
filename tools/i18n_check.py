#!/usr/bin/env python3
"""i18n parity check for strata-kit (LOCALES.md).

Checks, for every YAML under core/ profiles/ skills/ and every core/docs/en/**/*.md and profiles/*/docs/en/**/*.md:
  1. localized maps carry the same key set across locales (en, ko required; others warn)
  2. placeholders like {name} match across locales
  3. docs/<locale>/<path>.md exists for each docs/en/<path>.md or is listed in i18n/pending.yaml; a ko-only doc warns

Exit 2 on a `must` violation (missing en/ko or placeholder mismatch), 0 otherwise (warnings printed).
Usage: python3 tools/i18n_check.py [--root <kit-root>]
"""
from __future__ import annotations
import argparse, re, sys
from pathlib import Path
try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required", file=sys.stderr); sys.exit(1)

LOCALES = ["en", "ko", "ja", "zh", "es", "fr"]
REQUIRED = {"en", "ko"}
PH = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")

def _text(v) -> bool:
    return isinstance(v, str) or (isinstance(v, list) and all(isinstance(x, str) for x in v))

def is_locale_map(v) -> bool:
    # a locale map holds a string, or a list of strings (trigger phrases), per locale
    return isinstance(v, dict) and bool(v) and set(v.keys()) <= set(LOCALES) and all(_text(x) for x in v.values())

def _joined(v) -> str:
    return " ".join(v) if isinstance(v, list) else v

def walk(node, path, out):
    if is_locale_map(node):
        out.append((path, node)); return
    if isinstance(node, dict):
        for k, v in node.items(): walk(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node): walk(v, f"{path}[{i}]", out)

def doc_roots(root: Path) -> list[Path]:
    """Document trees with one folder per locale: core/docs and each profile's docs."""
    return [d for d in [root / "core" / "docs", *sorted(root.glob("profiles/*/docs"))] if d.is_dir()]


def doc_parity(root: Path, pending: dict) -> tuple[list[str], list[str]]:
    """Every <docs>/en/**/*.md needs a sibling per locale (ko required, others warn) unless i18n/pending.yaml lists it
    for that locale, by path relative to the locale folder or by bare file name. A ko document with no en is reported:
    en is canonical (LOCALES.md)."""
    errors, warnings = [], []
    for docs in doc_roots(root):
        for en_doc in sorted((docs / "en").glob("**/*.md")):
            rel = en_doc.relative_to(docs / "en").as_posix()
            for loc in LOCALES:
                if loc == "en":
                    continue
                listed = pending.get(loc) or []
                if not (docs / loc / rel).exists() and rel not in listed and en_doc.name not in listed:
                    (errors if loc == "ko" else warnings).append(
                        f"{(docs / loc / rel).relative_to(root).as_posix()}: missing (mark in i18n/pending.yaml or translate)")
        for ko_doc in sorted((docs / "ko").glob("**/*.md")):
            rel = ko_doc.relative_to(docs / "ko").as_posix()
            if not (docs / "en" / rel).exists():
                warnings.append(f"{ko_doc.relative_to(root).as_posix()}: no canonical en ({(docs / 'en' / rel).relative_to(root).as_posix()})")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=".")
    root = Path(ap.parse_args().root).resolve()
    errors, warnings = [], []
    for y in list(root.glob("core/**/*.yaml")) + list(root.glob("profiles/**/*.yaml")) + list(root.glob("skills/**/*.yaml")):
        if y.name.endswith(".schema.yaml"): continue
        try: data = yaml.safe_load(y.read_text(encoding="utf-8"))
        except Exception as e: errors.append(f"{y}: yaml error {e}"); continue
        maps: list[tuple[str, dict]] = []; walk(data, y.relative_to(root).as_posix(), maps)
        for path, m in maps:
            missing_req = REQUIRED - set(m)
            if missing_req: errors.append(f"{path}: missing required locales {sorted(missing_req)}")
            missing_opt = set(LOCALES) - REQUIRED - set(m)
            if missing_opt: warnings.append(f"{path}: pending locales {sorted(missing_opt)} (falls back to en)")
            base = set(PH.findall(_joined(m.get("en", ""))))
            for loc, text in m.items():
                if set(PH.findall(_joined(text))) != base:
                    errors.append(f"{path}.{loc}: placeholders differ from en {sorted(base)}")
    pending = {}
    pf = root / "i18n" / "pending.yaml"
    if pf.exists(): pending = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
    e, w = doc_parity(root, pending)
    errors += e; warnings += w
    for w in warnings: print(f"warn  {w}")
    for e in errors: print(f"ERROR {e}")
    print(f"i18n check: {len(errors)} errors, {len(warnings)} warnings")
    return 2 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
