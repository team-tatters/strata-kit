"""Match (spec AC3, Tech Spec G3): every inventory item against the store. A library or package matches a record by
identifier (purl base) and version range; a target without an identifier matches through its manual link — the
repository's advisories by range text, its releases as "new post" candidates when newer than ours; an OS matches by
version line (macOS: the latest security release of the same major; Windows: a new monthly update). Items with neither
identifier nor link are blind targets. Every match keeps (target, vulnerability, how it matched, in range or not) so
the note can say why something showed — out-of-range matches stay as filtered, never dropped (soft-delete-only).

  python3 -m kb security match [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

from kb.security import inventory as inv
from kb.security.collect import inventory_items
from kb.security.store import Store, store_path
from kb.security.versions import dotted_cmp, in_range

SCHEME = {"PyPI": "dotted", "npm": "dotted", "Go": "dotted", "Maven": "dotted", "crates.io": "dotted", "deb": "deb"}
MACOS_LINE = re.compile(r"^macOS\b")
RANGE_OP = re.compile(r"(>=|<=|<|>|=)\s*v?([0-9][0-9A-Za-z.\-+]*)")
KERNEL_PKG = re.compile(r"^linux-(?:image|modules|modules-extra|headers|tools|modules-nvidia-[\w-]+?|nvidia-[\w.]+-(?:headers|tools))-(\d+\.\d+\.\d+-\d+)")


def purl_base(purl: str) -> str:
    p = str(purl).split("?", 1)[0]
    return p.rsplit("@", 1)[0] if "@" in p[1:] else p


def purl_version(purl: str) -> str | None:
    p = str(purl).split("?", 1)[0]
    return p.rsplit("@", 1)[1] if "@" in p[1:] else None


def range_text_holds(version: str, text: str) -> bool | None:
    """'>= 2.39.0, <= 2.39.8' | '< 2.45.3' → whether version satisfies every clause; None when unparsable."""
    clauses = RANGE_OP.findall(text or "")
    if not clauses:
        return None
    v = str(version).lstrip("v")
    for op, bound in clauses:
        c = dotted_cmp(v, bound)
        if c is None:
            return None
        if not {"<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0, "=": c == 0}[op]:
            return False
    return True


def _m(day: str, item: dict, rec: dict, how: str, in_r, **detail) -> dict:
    vid = rec.get("vuln_id") or rec["id"]
    return {"id": f"{day}:{item['target_ref']}|{vid}", "day": day, "target_ref": item["target_ref"], "record_id": rec["id"], "vuln_id": vid,
            "matched_by": how, "version_in_range": in_r, "detail": {"target_version": item.get("version"), "kind": item.get("kind"), **detail}}


def match_items(items: list[dict], records: list[dict], manual_links: dict[str, str], day: str, since: str | None = None) -> dict:
    """→ {"matches": [...], "blind_targets": [...]} — matches include in-range, out-of-range and unknown."""
    by_purl: dict[str, list[tuple[dict, dict]]] = {}
    by_deb: dict[str, list[tuple[dict, dict]]] = {}
    by_repo: dict[str, list[tuple[dict, dict]]] = {}
    apple, msrc = [], []
    for r in records:
        for a in r.get("affected") or []:
            k, ident = a.get("kind"), a.get("identifier")
            if k == "purl" and ident:
                by_purl.setdefault(purl_base(ident).lower(), []).append((r, a))
            elif k == "deb" and ident:
                by_deb.setdefault(ident, []).append((r, a))
            elif k == "repo" and ident:
                by_repo.setdefault(ident.lower(), []).append((r, a))
            elif k == "product" and r["source_id"] == "apple-security-releases":
                apple.append((r, a))
            elif k == "product" and r["source_id"] == "msrc":
                msrc.append((r, a))
    kernels = {}
    for it in items:
        if it.get("kind") == "os" and it.get("kernel"):
            kernels["/".join(it["target_ref"].split("/")[:2])] = str(it["kernel"])
    out, blind = [], []
    for it in items:
        ident = str(it.get("identifier") or "none")
        host = "/".join(it["target_ref"].split("/")[:2])
        kv = KERNEL_PKG.search(str(it.get("name", "")))
        not_running = bool(kv) and kernels.get(host) is not None and kv.group(1) not in kernels[host]
        link = manual_links.get(it["target_ref"])
        matched_any = False
        if ident.startswith("pkg:deb/"):
            name = purl_base(ident).rsplit("/", 1)[-1]
            codename = it.get("codename") or (ident.split("distro=")[1] if "distro=" in ident else "")
            for r, a in by_deb.get(f"{codename}/{name}", []):
                in_r = in_range(str(it.get("version")), None, a.get("fixed"), scheme="deb") if a.get("fixed") else None
                out.append(_m(day, it, r, "identifier", in_r, identifier=f"{codename}/{name}", fixed=a.get("fixed"), **({"not_running": True, "running_kernel": kernels.get(host)} if not_running else {})))
                matched_any = True
        elif ident.startswith("pkg:"):
            for r, a in by_purl.get(purl_base(ident).lower(), []):
                v = str(it.get("version"))
                if a.get("versions") and v in a["versions"]:
                    in_r = True
                elif a.get("introduced") is None and a.get("fixed") is None and a.get("last_affected") is None:
                    in_r = True if a.get("versions") == [] else None
                else:
                    in_r = in_range(v, a.get("introduced"), a.get("fixed"), a.get("last_affected"), scheme=SCHEME.get(a.get("ecosystem"), "dotted"))
                out.append(_m(day, it, r, "identifier", in_r, identifier=purl_base(ident), introduced=a.get("introduced"), fixed=a.get("fixed")))
                matched_any = True
        if link and ":" in link and link.split(":", 1)[0] in ("github-releases", "github-advisories"):
            repo = link.split(":", 1)[1].lower()
            for r, a in by_repo.get(repo, []):
                if r["kind"] == "vuln":
                    in_r = range_text_holds(str(it.get("version")), a.get("range_text") or "")
                    out.append(_m(day, it, r, "manual-link", in_r, repo=repo, range_text=a.get("range_text"), fixed=a.get("fixed")))
                elif r["kind"] == "release" and (since is None or (r.get("published") or "") >= since):
                    c = dotted_cmp(str(r.get("version") or ""), str(it.get("version") or ""))
                    in_r = None if c is None else c > 0
                    out.append(_m(day, it, r, "manual-link", in_r, repo=repo, release=r.get("version"), security_mentioned=r.get("security_mentioned"), new_post=True))
                matched_any = True
        if it.get("kind") == "os" and str(it.get("name", "")).lower() == "macos":
            mine = str(it.get("version", "")).split(" ")[0]
            major = mine.split(".")[0]
            newest = None
            for r, a in apple:
                if MACOS_LINE.match(a.get("identifier") or "") and str(r.get("version") or "").split(".")[0] == major:
                    if newest is None or (dotted_cmp(r["version"], newest[0]["version"]) or 0) > 0:
                        newest = (r, a)
            if newest:
                c = dotted_cmp(newest[0]["version"], mine)
                out.append(_m(day, it, newest[0], "version-line", None if c is None else c > 0, line=f"macOS {major}", latest=newest[0]["version"]))
                matched_any = True
        if it.get("kind") == "os" and str(it.get("name", "")).lower() == "windows":
            for r, a in msrc:
                if since is None or (r.get("published") or "") >= since:
                    out.append(_m(day, it, r, "vendor-notice", None, update=r.get("version"), new_post=True))
                    matched_any = True
        has_eye = ident != "none" or link or (it.get("source") not in (None, "none", "")) or it.get("kind") == "os" and str(it.get("name", "")).lower() in ("macos", "windows", "ubuntu")
        if not has_eye and it.get("source") != "internal-build":
            blind.append({"target_ref": it["target_ref"], "kind": it.get("kind"), "version": it.get("version"), "reason": "식별자도 수동 연결도 없음"})
    # 같은 id(날짜:대상|취약점)는 하나만 남는다. 권고 하나에 영향 구간이 여럿이거나(예: 10.0.0~15.5.24 와 16.0.0~16.3.3)
    # 같은 대상의 버전이 둘이면 결과가 여럿 생기는데, 나중 것이 앞의 것을 덮어쓰면 범위 안이 범위 밖으로 바뀐다(2026-11-04 next 누락).
    # 가장 위험한 결과를 남긴다: 범위 안 > 모름 > 범위 밖.
    # 버전이 여럿이면 남긴 결과의 detail.target_versions 에 버전별 판정을 모두 적는다(노트가 위험한 버전을 함께 보인다).
    # id 에는 버전을 넣지 않는다 — first_seen 이 대상·취약점 쌍으로 이어져야 한다.
    rank = {True: 2, None: 1, False: 0}
    best: dict[str, dict] = {}
    versions: dict[str, dict[str, bool | None]] = {}
    for m in out:
        v = (m.get("detail") or {}).get("target_version")
        if v is not None:
            seen = versions.setdefault(m["id"], {})
            k = str(v)
            if k not in seen or rank.get(m["version_in_range"], 1) > rank.get(seen[k], 1):
                seen[k] = m["version_in_range"]
        cur = best.get(m["id"])
        if cur is None or rank.get(m["version_in_range"], 1) > rank.get(cur["version_in_range"], 1):
            best[m["id"]] = m
    for mid, m in best.items():
        if len(versions.get(mid, {})) > 1:
            m["detail"] = {**m["detail"], "target_versions": dict(sorted(versions[mid].items(), key=lambda kv: [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"[.\-+]", kv[0])]))}
    return {"matches": list(best.values()), "blind_targets": blind}


def matches_path(vault: Path, day: str) -> Path:
    return vault / "security" / "matches" / f"{day}.yaml"


def run(vault: Path, day: date, store: Store | None = None, since_days: int = 1) -> dict:
    own = store is None
    store = store or Store(store_path(vault))
    items = inventory_items(vault)
    links = inv.manual_links(vault)
    records = store.records("kind IN ('vuln','release','post')")
    since = (day - timedelta(days=since_days)).isoformat()
    res = match_items(items, records, links, day.isoformat(), since)
    for m in res["matches"]:
        if m["version_in_range"] is not False:
            m["first_seen"] = store.touch_first_seen(m["target_ref"], m["vuln_id"], day.isoformat())
    store.replace_matches(day.isoformat(), res["matches"])
    res["day"] = day.isoformat()
    res["counts"] = {"items": len(items), "candidates": sum(1 for m in res["matches"] if m["version_in_range"] is not False),
                     "out_of_range": sum(1 for m in res["matches"] if m["version_in_range"] is False), "blind_targets": len(res["blind_targets"])}
    if own:
        store.close()
    return res


def write_matches(vault: Path, res: dict, store: Store, graded: list[dict] | None = None) -> Path:
    """The git copy: candidates and filtered with their records (AC9 — the note links here)."""
    p = matches_path(vault, res["day"])
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = graded if graded is not None else res["matches"]
    recs = {m["record_id"]: store.record(m["record_id"]) for m in rows}
    doc = {"day": res["day"], "counts": res["counts"], "matches": rows, "blind_targets": res["blind_targets"],
           "records": {k: v for k, v in recs.items() if v}}
    p.write_text("# 대조 결과·판정 — 생성본(python3 -m kb security match|grade). 노트의 [레코드]·[대조] 링크가 여기를 가리킨다 (DEC-2026-11-03-05)\n"
                 + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security match", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["match"])
    ap.add_argument("--date", type=date.fromisoformat, default=None)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    day = a.date or date.today()
    store = Store(store_path(vault))
    try:
        res = run(vault, day, store)
        p = write_matches(vault, res, store)
    finally:
        store.close()
    c = res["counts"]
    print(f"대조 {res['day']}: 대상 {c['items']} · 후보 {c['candidates']} · 범위 밖 {c['out_of_range']} · 눈이 없는 대상 {c['blind_targets']} → {p.relative_to(vault)}")
    return 0
