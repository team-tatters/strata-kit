"""Collect (spec AC2, Tech Spec G2): every enabled source in security/sources.yaml is asked for what is new or changed
since `since`; records go to the store as the source gave them. Then enrich: KEV flag from the catalogue, EPSS from
FIRST, and a score copied from another record of the same vulnerability — each with filled_from naming the source. A
source that fails is recorded as failed and the others continue (AC8).

  python3 -m kb security collect [--since YYYY-MM-DD] [--layer L] [--source S] [--no-enrich]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from kb.security import inventory as inv
from kb.security.http import Http, HttpError
from kb.security.sources import Ctx, adapter_for
from kb.security.store import Store, store_path

LAYERS = ("general-db", "ecosystem", "os-vendor", "trend")
UBUNTU_CODENAMES = {"16.04": "xenial", "18.04": "bionic", "20.04": "focal", "22.04": "jammy", "24.04": "noble", "25.04": "plucky",
                    "25.10": "questing", "26.04": "resolute", "26.10": "stonking"}


def load_sources(vault: Path) -> dict:
    p = inv.sources_path(vault)
    if not p.is_file():
        raise FileNotFoundError(f"원천 등록 없음: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def inventory_items(vault: Path) -> list[dict]:
    """Every item of every inventory file, with target_ref = project/environment/name."""
    out = []
    for f in sorted((vault / "projects").glob("*/security/inventory/*.yaml")):
        if f.name.endswith(".template.yaml"):
            continue
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if "items" not in doc and "devices" in doc:      # hand-written desktop shape
            from kb.security.generators import manual
            items, _ = manual.load(f, doc.get("environment") or f.stem)
        else:
            items = list(doc.get("items") or [])
        project = doc.get("project") or f.parents[2].name
        env = doc.get("environment") or f.stem
        for i in items:
            i = dict(i)
            i.setdefault("environment", env)
            i["project"] = project
            i["target_ref"] = f"{project}/{env}/{i.get('name')}"
            i["inventory_file"] = str(f.relative_to(vault))
            out.append(i)
    return out


def os_releases(items: list[dict]) -> list[str]:
    out = []
    for i in items:
        if i.get("kind") == "os" and str(i.get("name", "")).lower() == "ubuntu":
            ver = str(i.get("version", ""))[:5]
            if ver in UBUNTU_CODENAMES and UBUNTU_CODENAMES[ver] not in out:
                out.append(UBUNTU_CODENAMES[ver])
    return out


def run_stamp(today: date) -> str:
    """collected_at for one collect run: taken once, and on the run's own day. enrich() picks the run's records by that
    day, so a run for another day (daily --date, a test's fixed today) or one that crosses midnight must not stamp the
    wall-clock date — the records would fall outside the day and get no KEV, EPSS or score."""
    now = datetime.now().replace(microsecond=0)
    return now.isoformat() if now.date() == today else f"{today.isoformat()}T{now.time().isoformat()}"


def enrich(store: Store, http: Http, day_iso: str, epss_cfg: dict | None) -> dict:
    """KEV flag · EPSS · a score from a sibling record of the same vulnerability — each with filled_from."""
    from kb.security.sources import epss as E
    todays = [r for r in store.collected_on(day_iso) if r["kind"] == "vuln"]
    counts = {"kev": 0, "epss": 0, "score": 0, "epss_error": None}
    kev = store.kev_set()
    if kev:
        for r in todays:
            if r.get("kev") is None:
                flag = (r["vuln_id"] in kev) or any(a in kev for a in r.get("aliases") or [])
                store.update_record(r["id"], kev=flag, filled_from={**(r.get("filled_from") or {}), "kev": "cisa-kev"})
                counts["kev"] += 1
    cves = sorted({c for r in todays if r.get("epss") is None for c in [r.get("vuln_id"), *(r.get("aliases") or [])] if c and c.startswith("CVE-")})
    if cves and epss_cfg is not None:
        try:
            table = E.lookup(http, cves, epss_cfg.get("url", E.URL))
        except HttpError as e:
            table, counts["epss_error"] = {}, str(e)
        for r in todays:
            if r.get("epss") is not None:
                continue
            hit = next((table[c] for c in [r.get("vuln_id"), *(r.get("aliases") or [])] if c in table), None)
            if hit:
                store.update_record(r["id"], epss=hit[0], epss_pct=hit[1], filled_from={**(store.record(r["id"]).get("filled_from") or {}), "epss": "first-epss"})
                counts["epss"] += 1
    # OSV CVE records for notices that carry only CVE ids (USN): the max CVSS v3 of the CVEs becomes the record's score
    from kb.security.cvss import base_score
    need = [r for r in todays if r.get("source_id") == "ubuntu-usn" and not any(v is not None for v in (r.get("scores") or {}).values())
            and any(a.startswith("CVE-") for a in r.get("aliases") or [])]
    cves = sorted({a for r in need for a in r["aliases"] if a.startswith("CVE-")})
    counts["osv_cve"] = 0
    if cves and getattr(http, "_fetch", None) is not None:
        from concurrent.futures import ThreadPoolExecutor
        def _one(cve):
            try:
                d = http.json("https://api.osv.dev/v1/vulns/" + cve)
            except HttpError:
                return cve, None
            vec = next((s.get("score") for s in d.get("severity") or [] if s.get("type") == "CVSS_V3"), None)
            return cve, base_score(vec) if vec else None
        with ThreadPoolExecutor(max_workers=6) as ex:
            table = dict(ex.map(_one, cves))
        for r in need:
            vals = [table.get(a) for a in r["aliases"] if table.get(a) is not None]
            if vals:
                scores = dict(r["scores"] or {})
                scores["cvss_v3"] = max(vals)
                store.update_record(r["id"], scores=scores, filled_from={**(store.record(r["id"]).get("filled_from") or {}), "scores.cvss_v3": f"osv:max-of-{len(vals)}-cves"})
                counts["osv_cve"] += 1
    for r in todays:
        cur = store.record(r["id"])
        if any(v is not None for v in (cur.get("scores") or {}).values()):
            continue
        for sib in store.records_by_vuln(r["vuln_id"]):
            if sib["id"] == r["id"]:
                continue
            for field in ("cvss_v4", "cvss_v3", "cna", "vendor"):
                if (sib.get("scores") or {}).get(field) is not None:
                    scores = dict(cur["scores"] or {})
                    scores[field] = sib["scores"][field]
                    store.update_record(r["id"], scores=scores, filled_from={**(cur.get("filled_from") or {}), f"scores.{field}": sib["source_id"]})
                    counts["score"] += 1
                    break
            else:
                continue
            break
    return counts


def collect(vault: Path, since: date, today: date, http: Http | None = None, store: Store | None = None,
            layers: list[str] | None = None, sources: list[str] | None = None, do_enrich: bool = True, log=None) -> dict:
    cfg = load_sources(vault)
    http = http or Http(pause=0.2)
    own = store is None
    store = store or Store(store_path(vault))
    items = inventory_items(vault)
    ctx = Ctx(http=http, purls=sorted({str(i.get("identifier")) for i in items if str(i.get("identifier", "")).startswith("pkg:")}),
              manual_links=inv.manual_links(vault), today=today, os_releases=os_releases(items))
    ctx.known_modified = {r["id"].split(":", 1)[1]: (r.get("modified") or "") for r in store.records("source_id='osv'")}
    result = {"since": since.isoformat(), "today": today.isoformat(), "sources": {}, "layers": {}, "records": 0}
    stamp = run_stamp(today)
    epss_cfg = None
    for s in cfg.get("sources") or []:
        sid, layer = s.get("id"), s.get("layer")
        if sid == "first-epss":
            epss_cfg = s
        if layers and layer not in layers or sources and sid not in sources:
            continue
        if s.get("enabled") is False:
            result["sources"][sid] = {"layer": layer, "status": "skipped", "count": 0, "error": "enabled: false"}
            continue
        fn = adapter_for(s)
        if fn is None:
            result["sources"][sid] = {"layer": layer, "status": "skipped", "count": 0, "error": "어댑터 없음" if sid != "first-epss" else "enrichment"}
            continue
        t0 = time.monotonic()
        try:
            recs = fn(s, since, ctx)
            n = store.upsert_records(recs, stamp)
            if sid == "cisa-kev" and getattr(ctx, "kev_entries", None):
                store.set_kev(ctx.kev_entries, stamp)
            result["sources"][sid] = {"layer": layer, "status": "ok", "count": n, "error": None, "seconds": round(time.monotonic() - t0, 1)}
            result["records"] += n
        except Exception as e:   # noqa: BLE001 — one source must not stop the others (AC8)
            result["sources"][sid] = {"layer": layer, "status": "failed", "count": 0, "error": f"{type(e).__name__}: {str(e)[:200]}", "seconds": round(time.monotonic() - t0, 1)}
        if log:
            log(f"  {sid}: {result['sources'][sid]['status']} {result['sources'][sid]['count']} ({result['sources'][sid]['seconds']}s)")
    for layer in LAYERS:
        st = [v["status"] for v in result["sources"].values() if v["layer"] == layer and v["status"] != "skipped"]
        result["layers"][layer] = "ok" if st and all(x == "ok" for x in st) else "failed" if st and all(x == "failed" for x in st) else "partial" if st else "none"
    if do_enrich:
        result["enrich"] = enrich(store, http, today.isoformat(), epss_cfg)
    if own:
        store.close()
    return result


def render(result: dict) -> list[str]:
    lines = [f"수집 {result['since']} → {result['today']}: 레코드 {result['records']}"]
    for layer in LAYERS:
        parts = [f"{sid} {v['count']}" if v["status"] == "ok" else f"{sid} ✗({v['error']})" if v["status"] == "failed" else f"{sid} —"
                 for sid, v in result["sources"].items() if v["layer"] == layer]
        lines.append(f"  {layer} [{result['layers'].get(layer)}]: " + " · ".join(parts))
    if result.get("enrich"):
        e = result["enrich"]
        lines.append(f"  보강: kev {e['kev']} · epss {e['epss']} · 점수 {e['score']} · USN←OSV {e.get('osv_cve', 0)}" + (f" · epss 오류 {e['epss_error']}" if e.get("epss_error") else ""))
    return lines


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security collect", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["collect"])
    ap.add_argument("--since", type=date.fromisoformat, default=None)
    ap.add_argument("--layer", action="append")
    ap.add_argument("--source", action="append")
    ap.add_argument("--no-enrich", action="store_true")
    ap.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    today = a.today or date.today()
    store = Store(store_path(vault))
    since = a.since
    if since is None:
        last = store.last_success()
        since = date.fromisoformat(last[:10]) if last else today - timedelta(days=1)
    try:
        result = collect(vault, since, today, store=store, layers=a.layer, sources=a.source, do_enrich=not a.no_enrich, log=lambda m: print(m, flush=True))
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    finally:
        store.close()
    print("\n".join(render(result)))
    return 0 if all(v["status"] != "failed" for v in result["sources"].values()) else 1
