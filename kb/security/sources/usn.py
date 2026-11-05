"""Ubuntu Security Notices JSON — one record per notice, affected = (codename/package, fixed version) per release; the
CVE ids are aliases. Pages of 20 (the API rejects more), newest first, filtered to one release when the inventories name exactly one, until a notice older than `since`."""
from __future__ import annotations

from kb.security.sources import day, record

URL = "https://ubuntu.com/security/notices.json"


def parse(doc: dict, since_iso: str | None = None, releases: list[str] | None = None) -> tuple[list[dict], bool]:
    """→ (records, reached_older) — reached_older is True when a notice older than since was seen (stop paging)."""
    out, older = [], False
    for n in doc.get("notices") or []:
        pub = day(n.get("published"))
        if since_iso and pub and pub < since_iso:
            older = True
            continue
        affected = []
        for codename, pkgs in (n.get("release_packages") or {}).items():
            if releases and codename not in releases:
                continue
            for p in pkgs or []:
                if p.get("is_source"):
                    continue
                affected.append({"kind": "deb", "identifier": f"{codename}/{p.get('name')}", "fixed": p.get("version"), "codename": codename})
        cves = list(n.get("cves_ids") or [])
        out.append(record(f"ubuntu-usn:{n.get('id')}", "vuln", "os-vendor", "ubuntu-usn", vuln_id=n.get("id"), aliases=cves, title=n.get("title"),
                          source_url=f"https://ubuntu.com/security/notices/{n.get('id')}", published=pub, affected=affected, mentions=cves,
                          severity_label=None))
    return out, older


def fetch(cfg: dict, since, ctx) -> list[dict]:
    out, offset = [], 0
    params = {"order": "newest", "limit": 20}
    if len(ctx.os_releases or []) == 1:
        params["release"] = ctx.os_releases[0]
    while True:
        doc = ctx.http.json(cfg.get("url", URL), params={**params, "offset": offset})
        recs, older = parse(doc, since.isoformat(), ctx.os_releases or None)
        out += recs
        offset += 20
        if older or not doc.get("notices") or offset >= (doc.get("total_results") or 0):
            break
    return out
