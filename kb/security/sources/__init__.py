"""Source adapters — one per source id in security/sources.yaml. Each `fetch(cfg, since, ctx)` returns records with the
G2 fields; a value the source does not give stays None (G2: empty stays empty). Errors propagate as exceptions and the
collector turns them into a per-source failure (AC8). ctx: http (kb.security.http.Http), purls (inventory identifiers),
manual_links (target_ref → notice), today (date)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}")


@dataclass
class Ctx:
    http: object
    purls: list[str] = field(default_factory=list)
    manual_links: dict = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    os_releases: list[str] = field(default_factory=list)   # ubuntu codenames in the inventories (noble, jammy …)


def record(rid: str, kind: str, layer: str, source_id: str, **f) -> dict:
    r = {"id": rid, "kind": kind, "layer": layer, "source_id": source_id, "vuln_id": None, "aliases": [], "title": None,
         "source_url": None, "published": None, "modified": None, "affected": [],
         "scores": {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}, "severity_label": None,
         "kev": None, "epss": None, "epss_pct": None, "filled_from": {}, "mentions": [], "version": None, "security_mentioned": None}
    r.update(f)
    return r


def mentions(*texts: str | None) -> list[str]:
    seen, out = set(), []
    for t in texts:
        for m in CVE_RE.findall(t or ""):
            if m not in seen:
                seen.add(m)
                out.append(m)
    return out


def day(s: str | None) -> str | None:
    """'2026-11-02T10:00:00Z' | '30 Oct 2026' → 'YYYY-MM-DD' (None when unparsable)."""
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    for fmt in ("%d %b %Y", "%b %d, %Y", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


ADAPTERS = {
    "nvd": "kb.security.sources.nvd", "cisa-kev": "kb.security.sources.kev", "osv": "kb.security.sources.osv",
    "github-advisories": "kb.security.sources.github", "github-releases": "kb.security.sources.github",
    "ubuntu-usn": "kb.security.sources.usn", "apple-security-releases": "kb.security.sources.apple", "msrc": "kb.security.sources.msrc",
    "oss-security": "kb.security.sources.osssec",
}
# fetch: rss → the generic feed adapter; first-epss is an enrichment, not a collector


def adapter_for(cfg: dict):
    import importlib
    sid, fetch = cfg.get("id"), cfg.get("fetch")
    if sid == "first-epss":
        return None
    if sid in ADAPTERS:
        mod = importlib.import_module(ADAPTERS[sid])
        return getattr(mod, "fetch_releases" if sid == "github-releases" else "fetch")
    if fetch == "rss":
        from kb.security.sources import feed
        return feed.fetch
    return None
