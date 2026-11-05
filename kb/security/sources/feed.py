"""Generic RSS 2.0 / Atom adapter for the trend layer — one post record per entry since `since`, CVE ids mentioned in
the title or summary as `mentions`. No identifiers: these never match a target by themselves."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from kb.security.sources import day, mentions, record

ATOM = "{http://www.w3.org/2005/Atom}"


def _text(el) -> str | None:
    return (el.text or "").strip() if el is not None else None


def parse(text: str, source_id: str, layer: str = "trend", since_iso: str | None = None) -> list[dict]:
    root = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", text.strip(), count=1))
    out = []
    if root.tag == f"{ATOM}feed":
        for e in root.findall(f"{ATOM}entry"):
            title = _text(e.find(f"{ATOM}title"))
            link_el = e.find(f"{ATOM}link[@rel='alternate']")  # an Element with no children is falsy — compare with None
            if link_el is None:
                link_el = e.find(f"{ATOM}link")
            link = link_el.get("href") if link_el is not None else None
            pub = day(_text(e.find(f"{ATOM}published")) or _text(e.find(f"{ATOM}updated")))
            summary = _text(e.find(f"{ATOM}summary")) or _text(e.find(f"{ATOM}content"))
            if since_iso and pub and pub < since_iso:
                continue
            out.append(record(f"{source_id}:{link or title}", "post", layer, source_id, title=title, source_url=link, published=pub, mentions=mentions(title, summary)))
        return out
    for it in root.iter("item"):
        title, link = _text(it.find("title")), _text(it.find("link"))
        pub = day(_text(it.find("pubDate")) or _text(it.find("{http://purl.org/dc/elements/1.1/}date")))
        if since_iso and pub and pub < since_iso:
            continue
        out.append(record(f"{source_id}:{link or title}", "post", layer, source_id, title=title, source_url=link, published=pub,
                          mentions=mentions(title, _text(it.find("description")))))
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    return parse(ctx.http.text(cfg["url"], headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"}),
                 cfg["id"], cfg.get("layer", "trend"), since.isoformat())
