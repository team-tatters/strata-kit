"""Apple security releases — the HTML table at support.apple.com/100100: name (with link), available for, date. One release
record per row since `since`; the product and version are split from the name ('macOS Tahoe 26.0.1' → macOS, 26.0.1).
HTML only: when the page changes the parser fails and the run records the layer as failed (accepted, order 02)."""
from __future__ import annotations

import html
import re

from kb.security.sources import day, record

URL = "https://support.apple.com/en-us/100100"
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
TAG = re.compile(r"<[^>]+>")
HREF = re.compile(r'href="([^"]+)"')
VER = re.compile(r"\b(\d+(?:\.\d+)+)\b")


def parse(text: str, since_iso: str | None = None) -> list[dict]:
    out = []
    for row in ROW.findall(text):
        cells = CELL.findall(row)
        if len(cells) < 3:
            continue
        name = html.unescape(TAG.sub("", cells[0])).strip()
        avail = html.unescape(TAG.sub("", cells[1])).strip()
        pub = day(html.unescape(TAG.sub("", cells[2])).strip())
        if not name or not pub or (since_iso and pub < since_iso):
            continue
        link = HREF.search(cells[0])
        m = VER.search(name)
        product = name[: m.start()].strip() if m else name
        out.append(record(f"apple:{re.sub(r'[^A-Za-z0-9.]+', '-', name)}", "release", "os-vendor", "apple-security-releases", title=name,
                          source_url=link.group(1) if link else URL, published=pub, version=m.group(1) if m else None, security_mentioned=True,
                          affected=[{"kind": "product", "identifier": product, "available_for": avail}]))
    if not out and "<table" not in text:
        raise ValueError("Apple security releases: 표를 찾지 못함 — 화면이 바뀜")
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    return parse(ctx.http.text(cfg.get("url", URL), headers={"Accept": "text/html"}), since.isoformat())
