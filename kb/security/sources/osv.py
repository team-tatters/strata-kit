"""OSV.dev — queried by the inventories' purls (querybatch, 1000 per call), then each new or modified vulnerability is
read in full. Severity comes as a vector: v3 vectors are scored (kb.security.cvss), v4 vectors are kept as text, and
the GHSA label (database_specific.severity) goes to severity_label."""
from __future__ import annotations

from kb.security.cvss import base_score
from kb.security.sources import day, record

BATCH = "https://api.osv.dev/v1/querybatch"
VULN = "https://api.osv.dev/v1/vulns/"


def parse_vuln(v: dict) -> dict:
    aliases = list(v.get("aliases") or [])
    cve = next((a for a in aliases if a.startswith("CVE-")), None)
    scores = {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}
    vectors = {}
    for s in v.get("severity") or []:
        if s.get("type") == "CVSS_V3":
            scores["cvss_v3"] = base_score(s.get("score"))
            vectors["v3"] = s.get("score")
        elif s.get("type") == "CVSS_V4":
            vectors["v4"] = s.get("score")
    affected = []
    for a in v.get("affected") or []:
        pkg = a.get("package") or {}
        base = pkg.get("purl") or f"pkg:{(pkg.get('ecosystem') or '').lower()}/{pkg.get('name')}"
        ranges = a.get("ranges") or []
        if not ranges:
            affected.append({"kind": "purl", "identifier": base, "ecosystem": pkg.get("ecosystem"), "versions": a.get("versions") or []})
        for r in ranges:
            ev = {"kind": "purl", "identifier": base, "ecosystem": pkg.get("ecosystem"), "range_type": r.get("type"), "introduced": None, "fixed": None,
                  "last_affected": None, "versions": a.get("versions") or []}
            for e in r.get("events") or []:
                for k in ("introduced", "fixed", "last_affected"):
                    if k in e:
                        ev[k] = e[k]
            affected.append(ev)
    label = (v.get("database_specific") or {}).get("severity")
    r = record(f"osv:{v['id']}", "vuln", "ecosystem", "osv", vuln_id=cve or v["id"], aliases=[v["id"], *aliases],
               title=v.get("summary") or (v.get("details") or "")[:200], source_url=f"https://osv.dev/vulnerability/{v['id']}",
               published=day(v.get("published")), modified=day(v.get("modified")), affected=affected, scores=scores,
               severity_label=label.lower() if label else None)
    return _with_vectors(r, vectors)


def _with_vectors(r: dict, vectors: dict) -> dict:
    if vectors:
        r["filled_from"] = {**(r.get("filled_from") or {}), "vectors": vectors}
    return r


def fetch(cfg: dict, since, ctx) -> list[dict]:
    purls = [p for p in ctx.purls if p and p.startswith("pkg:")]
    ids: dict[str, str] = {}
    for i in range(0, len(purls), 1000):
        doc = ctx.http.post_json(cfg.get("url", BATCH), {"queries": [{"package": {"purl": p}} for p in purls[i:i + 1000]]})
        for res in doc.get("results") or []:
            for v in res.get("vulns") or []:
                ids[v["id"]] = (v.get("modified") or "")
    known = getattr(ctx, "known_modified", {})   # id → modified already in the store
    todo = [vid for vid, mod in sorted(ids.items()) if not (known.get(vid) and known[vid] >= (mod[:19] if mod else ""))]
    if not todo:
        return []
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as ex:   # 373 vulnerabilities for 2,300 purls on 2026-11-03 — one at a time was minutes
        docs = list(ex.map(lambda vid: ctx.http.json(VULN + vid), todo))
    return [parse_vuln(d) for d in docs]
