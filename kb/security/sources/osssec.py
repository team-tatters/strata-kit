"""oss-security archive (openwall) — one directory per day, one anchor per message. A post record per message for every
day from `since` to today; a day without messages (404) is simply empty."""
from __future__ import annotations

import html
import re
from datetime import timedelta

from kb.security.http import HttpError
from kb.security.sources import mentions, record

URL = "https://www.openwall.com/lists/oss-security/"
MSG = re.compile(r'<a href="(\d+)">(.*?)</a>', re.S)


def parse(text: str, day_iso: str, base: str = URL) -> list[dict]:
    y, m, d = day_iso.split("-")
    out = []
    for num, title in MSG.findall(text):
        t = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        url = f"{base}{y}/{m}/{d}/{num}"
        out.append(record(f"oss-security:{y}/{m}/{d}/{num}", "post", "trend", "oss-security", title=t, source_url=url, published=day_iso, mentions=mentions(t)))
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    out, d = [], since
    while d <= ctx.today:
        y, m, dd = d.isoformat().split("-")
        try:
            out += parse(ctx.http.text(f"{cfg.get('url', URL)}{y}/{m}/{dd}/", headers={"Accept": "text/html"}), d.isoformat(), cfg.get("url", URL))
        except HttpError as e:
            if "404" not in str(e):
                raise
        d += timedelta(days=1)
    return out
