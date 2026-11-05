"""CISA Known Exploited Vulnerabilities JSON — the whole catalogue goes to the store's kev table (enrichment basis);
entries added since `since` are also records of their own, so a new KEV entry shows in the note even without a match."""
from __future__ import annotations

from kb.security.sources import record

URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"


def parse(doc: dict) -> list[dict]:
    return [{"cve": v.get("cveID"), "date_added": v.get("dateAdded"), "vendor": v.get("vendorProject"), "product": v.get("product"),
             "due": v.get("dueDate"), "ransomware": v.get("knownRansomwareCampaignUse"), "name": v.get("vulnerabilityName")}
            for v in doc.get("vulnerabilities") or []]


def fetch(cfg: dict, since, ctx) -> list[dict]:
    doc = ctx.http.json(cfg.get("url", URL))
    entries = parse(doc)
    ctx.kev_entries = entries   # the collector stores the whole catalogue
    out = []
    for e in entries:
        if e["date_added"] and e["date_added"] >= since.isoformat():
            out.append(record(f"cisa-kev:{e['cve']}", "vuln", "general-db", "cisa-kev", vuln_id=e["cve"], title=f"{e['vendor']} {e['product']}: {e['name']}",
                              source_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog", published=e["date_added"], kev=True,
                              affected=[{"kind": "vendor-product", "identifier": f"{e['vendor']}/{e['product']}"}], severity_label="kev"))
    return out
