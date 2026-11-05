"""MSRC CVRF updates — the monthly list only (one post record per update since `since`); the CVRF documents
themselves are large and matching Windows builds is a later task. Enough to show the layer in the note."""
from __future__ import annotations

from kb.security.sources import day, record

URL = "https://api.msrc.microsoft.com/cvrf/v3.0/updates"


def parse(doc: dict, since_iso: str | None = None) -> list[dict]:
    out = []
    for u in doc.get("value") or []:
        pub = day(u.get("CurrentReleaseDate") or u.get("InitialReleaseDate"))
        if since_iso and pub and pub < since_iso:
            continue
        out.append(record(f"msrc:{u.get('ID')}", "post", "os-vendor", "msrc", title=u.get("DocumentTitle"), source_url=u.get("CvrfUrl"), published=pub,
                          version=u.get("ID"), affected=[{"kind": "product", "identifier": "Windows"}], severity_label=(u.get("Severity") or None)))
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    return parse(ctx.http.json(cfg.get("url", URL)), since.isoformat())
