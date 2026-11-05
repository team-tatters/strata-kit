"""Grade (spec AC4, Tech Spec G4, DEC-2026-11-03-02): two grades, urgent and advisory. urgent means the technical severity
(the first of cvss_v4, cvss_v3, cna, vendor that the record has) is at or above the threshold — 9.0 by default, set per
repository in projects/<p>/security/grading.yaml and overridden per environment; every change is kept in history.
KEV and EPSS order the note, they never change the grade. Candidates without any score are advisory with reason
no-score; matches out of range or inside an accepted risk's term are filtered with their reason, never dropped.

  python3 -m kb security grade [--date YYYY-MM-DD]
  python3 -m kb security grading show --project P
  python3 -m kb security grading set --project P [--env E] threshold 8.0 --by NAME
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from kb.security import match as M
from kb.security.store import Store, now_iso, store_path

DEFAULT = {"threshold": 9.0, "severity_order": ["cvss_v4", "cvss_v3", "cna", "vendor"], "due_days": {"kev": 3, "urgent": 14}}
TEMPLATE = Path(__file__).resolve().parents[2] / "core" / "templates" / "vault" / "security" / "grading.yaml"


def grading_path(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "security" / "grading.yaml"


def accepted_path(vault: Path, project: str) -> Path:
    return vault / "projects" / project / "security" / "accepted-risks.yaml"


def load_grading(vault: Path, project: str) -> dict:
    p = grading_path(vault, project)
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else {}
    doc = doc or {}
    doc.setdefault("version", "0.1")
    doc["default"] = {**DEFAULT, **(doc.get("default") or {})}
    doc.setdefault("environments", {}) or doc.__setitem__("environments", {})
    doc.setdefault("history", []) or doc.__setitem__("history", [])
    return doc


def save_grading(vault: Path, project: str, doc: dict) -> Path:
    p = grading_path(vault, project)
    p.parent.mkdir(parents=True, exist_ok=True)
    head = TEMPLATE.read_text(encoding="utf-8").split("version:")[0] if TEMPLATE.is_file() else ""
    p.write_text(head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p


def threshold_for(doc: dict, environment: str | None) -> tuple[float, str]:
    env = (doc.get("environments") or {}).get(environment or "", {})
    if isinstance(env, dict) and env.get("threshold") is not None:
        return float(env["threshold"]), f"environments.{environment}"
    return float(doc["default"]["threshold"]), "default"


def set_threshold(vault: Path, project: str, value: float, by: str, environment: str | None = None, at: str | None = None) -> dict:
    doc = load_grading(vault, project)
    if environment:
        before = (doc["environments"].get(environment) or {}).get("threshold")
        doc["environments"].setdefault(environment, {})["threshold"] = value
        scope = f"environments.{environment}"
    else:
        before = doc["default"]["threshold"]
        doc["default"]["threshold"] = value
        scope = "default"
    doc["history"].append({"at": at or now_iso(), "by": by, "scope": scope, "field": "threshold", "from": before, "to": value})
    save_grading(vault, project, doc)
    return doc


def severity(record: dict, order=DEFAULT["severity_order"]) -> tuple[float | None, str | None]:
    scores = record.get("scores") or {}
    for f in order:
        if scores.get(f) is not None:
            return float(scores[f]), f
    return None, None


def load_accepted(vault: Path, project: str) -> list[dict]:
    p = accepted_path(vault, project)
    if not p.is_file():
        return []
    return list((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("accepted") or [])


def accepted_until(accepted: list[dict], target_ref: str, vuln_id: str, day: str) -> str | None:
    for a in accepted:
        if a.get("target_ref") == target_ref and a.get("vuln_id") == vuln_id and a.get("status", "active") == "active" and str(a.get("until", "")) >= day:
            return str(a["until"])
    return None


def accepted_expired(accepted: list[dict], target_ref: str, vuln_id: str, day: str) -> str | None:
    """The most recent accepted term that has run out — the pair shows again, marked (AC11)."""
    ends = [str(a["until"]) for a in accepted if a.get("target_ref") == target_ref and a.get("vuln_id") == vuln_id and a.get("status", "active") == "active" and str(a.get("until", "")) < day]
    return max(ends) if ends else None


def grade_match(m: dict, record: dict, gdoc: dict, accepted: list[dict], day: str) -> dict:
    """Adds grade · reason · severity · severity_from · threshold · sort_key to a match (returns a new dict)."""
    out = dict(m)
    env = (m.get("detail") or {}).get("environment") or m["target_ref"].split("/")[1] if m["target_ref"].count("/") >= 2 else None
    thr, thr_from = threshold_for(gdoc, env)
    sev, sev_from = severity(record, gdoc["default"].get("severity_order") or DEFAULT["severity_order"])
    kev = bool(record.get("kev"))
    epss = record.get("epss") or 0.0
    out.update({"severity": sev, "severity_from": sev_from, "threshold": thr, "threshold_from": thr_from,
                "sort_key": [1 if kev else 0, float(epss), sev or 0.0, 0.0]})
    until = accepted_until(accepted, m["target_ref"], m["vuln_id"], day)
    if m.get("version_in_range") is False:
        out.update(grade="filtered", reason="out-of-range")
    elif until:
        out.update(grade="filtered", reason=f"accepted-risk until {until}")
    elif (m.get("detail") or {}).get("not_running"):
        out.update(grade="advisory", reason=f"installed-not-running (실행 커널 {(m.get('detail') or {}).get('running_kernel')}) · " + (f"{sev_from} {sev}" if sev is not None else "no-score"))
    elif record.get("kind") in ("release", "post"):
        out.update(grade="advisory", reason="new-post" + (" security-mentioned" if record.get("security_mentioned") else ""))
    elif sev is None:
        out.update(grade="advisory", reason="no-score")
    elif sev >= thr:
        out.update(grade="urgent", reason=f"{sev_from} {sev} ≥ {thr} ({thr_from})")
    else:
        out.update(grade="advisory", reason=f"{sev_from} {sev} < {thr} ({thr_from})" + (" kev" if kev else ""))
    if m.get("version_in_range") is None and out["grade"] != "filtered":
        out["reason"] += " · version-unknown"
    exp = accepted_expired(accepted, m["target_ref"], m["vuln_id"], day)
    if exp and out["grade"] != "filtered":
        out["reason"] += f" · 수용 기한 만료 {exp}"
    return out


def run(vault: Path, day: date, store: Store | None = None) -> dict:
    own = store is None
    store = store or Store(store_path(vault))
    d = day.isoformat()
    matches = store.matches_on(d)
    gdocs, accepted = {}, {}
    graded = []
    for m in matches:
        project = m["target_ref"].split("/")[0]
        if project not in gdocs:
            gdocs[project] = load_grading(vault, project)
            accepted[project] = load_accepted(vault, project)
        rec = store.record(m["record_id"]) or {}
        graded.append(grade_match(m, rec, gdocs[project], accepted[project], d))
    graded.sort(key=lambda g: ({"urgent": 0, "advisory": 1, "filtered": 2}[g["grade"]], [-x for x in g["sort_key"]]))
    store.replace_matches(d, graded)
    counts = {"urgent": sum(g["grade"] == "urgent" for g in graded), "advisory": sum(g["grade"] == "advisory" for g in graded),
              "filtered": sum(g["grade"] == "filtered" for g in graded), "no_score": sum(g.get("reason", "").startswith("no-score") for g in graded)}
    res = {"day": d, "matches": graded, "counts": counts}
    if own:
        store.close()
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grade"); g.add_argument("--date", type=date.fromisoformat, default=None)
    gr = sub.add_parser("grading")
    gsub = gr.add_subparsers(dest="sub", required=True)
    sh = gsub.add_parser("show"); sh.add_argument("--project", required=True)
    st = gsub.add_parser("set"); st.add_argument("--project", required=True); st.add_argument("--env"); st.add_argument("field", choices=["threshold"])
    st.add_argument("value", type=float); st.add_argument("--by", required=True)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    if a.cmd == "grading":
        if a.sub == "show":
            print(yaml.safe_dump(load_grading(vault, a.project), allow_unicode=True, sort_keys=False))
            return 0
        doc = set_threshold(vault, a.project, a.value, a.by, a.env)
        h = doc["history"][-1]
        print(f"{a.project} {h['scope']}.threshold {h['from']} → {h['to']} (by {a.by}, {h['at']}) → {grading_path(vault, a.project).relative_to(vault)}")
        return 0
    day = a.date or date.today()
    store = Store(store_path(vault))
    try:
        res = run(vault, day, store)
        mres = {"day": res["day"], "matches": res["matches"], "blind_targets": [], "counts": res["counts"]}
        existing = M.matches_path(vault, res["day"])
        if existing.is_file():
            prev = yaml.safe_load(existing.read_text(encoding="utf-8")) or {}
            mres["blind_targets"] = prev.get("blind_targets", [])
            mres["counts"] = {**prev.get("counts", {}), **res["counts"]}
        p = M.write_matches(vault, mres, store, graded=res["matches"])
    finally:
        store.close()
    c = res["counts"]
    print(f"판정 {res['day']}: 긴급 {c['urgent']} · 권고 {c['advisory']} (점수 없음 {c['no_score']}) · 걸러냄 {c['filtered']} → {p.relative_to(vault)}")
    return 0
