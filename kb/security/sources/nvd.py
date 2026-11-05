"""NVD CVE API 2.0 — lastModStartDate/lastModEndDate window (≤120 days), 2000 per page. The primary (NVD) CVSS score goes
to cvss_v3/v4; a secondary (CNA) score goes to cna; absent stays None. cisaExploitAdd marks kev."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kb.security.sources import day, record

URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
KST = timezone(timedelta(hours=9))


def parse(doc: dict) -> list[dict]:
    out = []
    for v in doc.get("vulnerabilities") or []:
        c = v.get("cve") or {}
        cid = c.get("id")
        scores = {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}
        for key, lst in (c.get("metrics") or {}).items():
            for m in lst:
                score = (m.get("cvssData") or {}).get("baseScore")
                if score is None:
                    continue
                if m.get("type") == "Primary":
                    scores["cvss_v4" if key.startswith("cvssMetricV4") else "cvss_v3"] = float(score)
                elif scores["cna"] is None:
                    scores["cna"] = float(score)
        affected = []
        for conf in c.get("configurations") or []:
            for node in conf.get("nodes") or []:
                for cm in node.get("cpeMatch") or []:
                    if cm.get("vulnerable"):
                        affected.append({"kind": "cpe", "identifier": cm.get("criteria"), "introduced": cm.get("versionStartIncluding"),
                                         "fixed": cm.get("versionEndExcluding"), "last_affected": cm.get("versionEndIncluding")})
        desc = next((d.get("value") for d in c.get("descriptions") or [] if d.get("lang") == "en"), None)
        out.append(record(f"nvd:{cid}", "vuln", "general-db", "nvd", vuln_id=cid, title=(desc or "")[:200] or None,
                          source_url=f"https://nvd.nist.gov/vuln/detail/{cid}", published=day(c.get("published")), modified=day(c.get("lastModified")),
                          affected=affected, scores=scores, severity_label=c.get("vulnStatus"), kev=True if c.get("cisaExploitAdd") else None))
    return out


def fetch(cfg: dict, since, ctx) -> list[dict]:
    start = datetime.combine(since, datetime.min.time(), tzinfo=KST)
    end = datetime.now(KST)
    cap = int(cfg.get("max_days", 2))          # NVD without a key is slow: 2000 results per page, minutes per page. The CVE
    if end - start > timedelta(days=cap):     # scores a note needs come per CVE through enrichment; the window is for new CVEs.
        start = end - timedelta(days=cap)
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000") + d.strftime("%z")[:3] + ":" + d.strftime("%z")[3:]
    out, index = [], 0
    while True:
        doc = ctx.http.json(cfg.get("url", URL), params={"lastModStartDate": fmt(start), "lastModEndDate": fmt(end), "resultsPerPage": 2000, "startIndex": index})
        out += parse(doc)
        index += doc.get("resultsPerPage") or 2000
        if index >= (doc.get("totalResults") or 0):
            break
    return out
