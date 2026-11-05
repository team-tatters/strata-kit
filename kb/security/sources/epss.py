"""FIRST EPSS — enrichment only: score and percentile for a list of CVE ids, 100 per call."""
from __future__ import annotations

URL = "https://api.first.org/data/v1/epss"


def lookup(http, cves: list[str], url: str = URL) -> dict[str, tuple[float, float, str]]:
    out: dict[str, tuple[float, float, str]] = {}
    ids = sorted({c for c in cves if c})
    for i in range(0, len(ids), 100):
        doc = http.json(url, params={"cve": ",".join(ids[i:i + 100])})
        for d in doc.get("data") or []:
            try:
                out[d["cve"]] = (float(d["epss"]), float(d["percentile"]), d.get("date"))
            except (KeyError, TypeError, ValueError):
                continue
    return out
