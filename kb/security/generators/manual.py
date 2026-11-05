"""Manual generator: a hand-written inventory is read and checked, never regenerated. Two shapes are accepted — flat
`items:` or the desktop template's nested `devices:` (os + software per device). Placeholders (<…>) and missing values
among the six are reported as problems."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from kb.security.generators import SIX, item

PLACEHOLDER = re.compile(r"^\s*<.*>\s*$")


def _norm_device(dev: dict, environment: str) -> list[dict]:
    out, device = [], dev.get("device", "?")
    env = dev.get("environment") or environment
    os_ = dev.get("os") or {}
    if os_:
        ver = str(os_.get("version", "")) + (f" ({os_['build']})" if os_.get("build") else "")
        out.append(item(str(os_.get("name", "")), ver.strip(), env, "os", str(os_.get("source", "")), str(os_.get("identifier", "")), device=device))
    for s in dev.get("software") or []:
        out.append(item(str(s.get("name", "")), str(s.get("version", "")), env, str(s.get("kind", "app")), str(s.get("source", "")),
                        str(s.get("identifier", "")), device=device))
    return out


def load(path: Path, environment: str) -> tuple[list[dict], list[str]]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    if "devices" in doc:
        for dev in doc["devices"] or []:
            items.extend(_norm_device(dev, environment))
    for i in doc.get("items") or []:
        items.append(item(str(i.get("name", "")), str(i.get("version", "")), i.get("environment") or environment, str(i.get("kind", "")),
                          str(i.get("source", "")), str(i.get("identifier", "")), **{k: v for k, v in i.items() if k not in SIX}))
    problems = []
    if doc.get("origin") != "manual":
        problems.append(f"{Path(path).name}: origin 이 manual 이 아님 — 손으로 적은 목록은 origin: manual 로 표시한다")
    for it in items:
        bad = [k for k in SIX if not str(it.get(k, "")).strip() or PLACEHOLDER.match(str(it.get(k, "")))]
        if bad:
            problems.append(f"{it.get('device', '')}/{it.get('name') or '?'}: 빠진 값 {', '.join(bad)}")
    return items, problems
