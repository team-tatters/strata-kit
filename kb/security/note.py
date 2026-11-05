"""The daily note (spec AC5·AC8·AC9, Tech Spec G5): one Markdown page per day at security/notes/<day>.md with four
sections — new items (first seen today), open items (seen before, still open, with their first day), closed items (closed
since the last note), blind targets — then folded no-score and filtered lists. Every line carries the link set
source → record → match (→ order, filled by order 2026.11.03-03). Urgent first, then by (KEV, EPSS, severity). A layer
that failed is named at the top; a day that did not run gets a one-line "오늘은 보지 못했다" note instead.

  python3 -m kb security note [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

from kb.security import match as M
from kb.security.store import Store, store_path

MAX_LINES = 40
GRADE_KO = {"urgent": "긴급", "advisory": "권고", "filtered": "걸러냄"}


def notes_dir(vault: Path) -> Path:
    return vault / "security" / "notes"


def note_path(vault: Path, day: str) -> Path:
    return notes_dir(vault) / f"{day}.md"


def _scores(rec: dict) -> str:
    s = rec.get("scores") or {}
    parts = []
    if rec.get("kev"):
        parts.append("KEV")
    if rec.get("epss") is not None:
        parts.append(f"EPSS {float(rec['epss']):.3f}")
    for k in ("cvss_v4", "cvss_v3", "cna", "vendor"):
        if s.get(k) is not None:
            parts.append(f"{k} {s[k]}")
            break
    if rec.get("severity_label") and not parts:
        parts.append(str(rec["severity_label"]))
    return " · ".join(parts) if parts else "점수 없음"


def _links(m: dict, rec: dict, day: str) -> str:
    mf = f"../matches/{day}.yaml"
    links = [f"[원문]({rec.get('source_url') or '#'})", f"[레코드]({mf}#records.{m['record_id']})", f"[대조]({mf}#{m['id']})"]
    if m.get("order_ref"):
        links.append(f"[오더]({m['order_ref']})")
    return " ".join(links)


def _line(m: dict, rec: dict, day: str, first: str | None = None) -> str:
    detail = m.get("detail") or {}
    tv = detail.get("target_version")
    tvs = detail.get("target_versions") or {}
    if len(tvs) > 1:  # 같은 대상에 버전이 여럿: 위험한 버전(범위 안·모름)을 모두 보인다, 모두 범위 밖이면 전부
        risky = [v for v, r in tvs.items() if r is not False] or list(tvs)
        tv = ", ".join(risky)
    head = f"**{GRADE_KO.get(m.get('grade'), m.get('grade'))}** · {m['target_ref']}" + (f"@{tv}" if tv else "") + f" · {m['vuln_id']}"
    title = (rec.get("title") or "").strip()
    bits = [head, _scores(rec)]
    if first and first != day:
        bits.append(f"처음 {first}")
    if m.get("reason"):
        bits.append(m["reason"])
    if title:
        bits.append(title[:80])
    return "- " + " · ".join(bits) + " · " + _links(m, rec, day)


def _grouped(ms: list[dict], recs: dict, day: str, first_of) -> list[str]:
    """One line per (vuln_id, grade) when many package targets share a notice — keeps the note readable."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for m in ms:
        groups[(m["vuln_id"], m.get("grade"))].append(m)
    out = []
    for (vid, grade), items in groups.items():
        if len(items) == 1:
            out.append(_line(items[0], recs.get(items[0]["record_id"], {}), day, first_of(items[0])))
            continue
        rec = recs.get(items[0]["record_id"], {})
        hosts = sorted({"/".join(i["target_ref"].split("/")[:2]) for i in items})
        names = sorted({i["target_ref"].split("/")[-1] for i in items})
        head = f"**{GRADE_KO.get(grade, grade)}** · {', '.join(hosts)} — 대상 {len(items)}개({', '.join(names[:5])}{' …' if len(names) > 5 else ''}) · {vid}"
        firsts = sorted({first_of(i) for i in items if first_of(i)})
        bits = [head, _scores(rec)] + ([f"처음 {firsts[0]}"] if firsts and firsts[0] != day else []) + ([items[0]["reason"]] if items[0].get("reason") else []) + ([(rec.get("title") or "")[:80]] if rec.get("title") else [])
        out.append("- " + " · ".join(bits) + " · " + _links(items[0], rec, day))
    return out


def build(vault: Path, day: str, store: Store, blind_targets: list[dict] | None = None) -> str:
    matches = store.matches_on(day)
    recs = {m["record_id"]: (store.record(m["record_id"]) or {}) for m in matches}
    fs = store.first_seen_all()
    run = store.run(day) or {}
    layers = run.get("layers") or {}
    failed = [f"{k}({v})" if isinstance(v, str) and v not in ("ok",) else k for k, v in layers.items() if v not in ("ok", "none", None)]

    def first_of(m):
        e = fs.get(f"{m['target_ref']}|{m['vuln_id']}")
        return e["first_seen"] if e else day

    def is_open(m):
        e = fs.get(f"{m['target_ref']}|{m['vuln_id']}")
        return not (e and e.get("closed"))

    for m in matches:
        e = fs.get(f"{m['target_ref']}|{m['vuln_id']}")
        if e and e.get("order_ref"):
            m["order_ref"] = "../../" + e["order_ref"]
    live = [m for m in matches if m.get("grade") in ("urgent", "advisory") and is_open(m)]
    new = [m for m in live if first_of(m) == day and not str(m.get("reason", "")).startswith("no-score")]
    open_ = [m for m in live if first_of(m) != day and not str(m.get("reason", "")).startswith("no-score")]
    no_score = [m for m in live if str(m.get("reason", "")).startswith("no-score")]
    filtered = [m for m in matches if m.get("grade") == "filtered"]
    closed = [e for e in fs.values() if e.get("closed") == day]
    blind = blind_targets if blind_targets is not None else []
    if blind_targets is None:
        mp = M.matches_path(vault, day)
        if mp.is_file():
            blind = (yaml.safe_load(mp.read_text(encoding="utf-8")) or {}).get("blind_targets") or []

    def section(title, ms, group=True):
        lines = _grouped(ms, recs, day, first_of) if group else ms
        if not lines:
            return [f"## {title}", "", "없음.", ""]
        urgent_n = sum(1 for m in ms if m.get("grade") == "urgent")
        if len(lines) > MAX_LINES:
            keep = [l for l in lines if l.startswith("- **긴급**")]
            rest = len(lines) - len(keep)
            lines = keep + [f"- 권고 {rest}줄은 접었다 — [대조 파일](../matches/{day}.yaml) 에 전부 있다 (R7: 사람이 한 번에 읽을 분량)"]
        return [f"## {title}", "", f"긁급 {urgent_n} · 전체 {len(ms)}".replace("긁급", "긴급"), ""] + lines + [""]

    fm = {"title": f"보안 노트 {day}", "type": "security-note", "date": day, "origin": "generated", "run_ref": f"../runs/{day}.yaml",
          "layers_ok": [k for k, v in layers.items() if v == "ok"], "layers_failed": [k for k, v in layers.items() if v in ("failed", "partial")],
          "counts": {"new": len(new), "open": len(open_), "closed": len(closed), "blind": len(blind), "no_score": len(no_score), "filtered": len(filtered),
                     "urgent": sum(1 for m in live if m.get("grade") == "urgent")}}
    out = ["---", yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip(), "---", "", f"# 보안 노트 {day}", ""]
    if failed:
        out += [f"> 오늘 보지 못한 층: {', '.join(failed)} — 나머지 층으로 만들었다.", ""]
    elif not layers:
        out += ["> 실행 기록이 없다 — 수집 없이 저장된 대조 결과로 만든 노트.", ""]
    out += section("새 항목", new)
    out += section("미조치", open_)
    out += ["## 닫힌 항목", ""] + ([f"- {e['target_ref']} · {e['vuln_id']} · 처음 {e['first_seen']} → 닫힘 {e['closed']}" + (f" · [오더]({e['order_ref']})" if e.get("order_ref") else "") for e in closed] or ["없음."]) + [""]
    out += ["## 눈이 없는 대상", ""] + ([f"- {b['target_ref']} ({b.get('kind')} {b.get('version')}) — {b.get('reason')}" for b in blind] or ["없음."]) + [""]
    out += ["<details><summary>점수 없는 항목 " + str(len(no_score)) + "</summary>", ""] + _grouped(no_score, recs, day, first_of) + ["", "</details>", ""]
    out += ["<details><summary>걸러낸 항목 " + str(len(filtered)) + " (지우지 않고 이유와 함께)</summary>", ""] + _grouped(filtered, recs, day, first_of) + ["", "</details>", ""]
    return "\n".join(out)


def write(vault: Path, day: str, store: Store, blind_targets: list[dict] | None = None) -> Path:
    p = note_path(vault, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build(vault, day, store, blind_targets), encoding="utf-8")
    return p


def write_gap(vault: Path, day: str, reason: str) -> Path:
    """AC8: a day without a run gets a one-line note instead of silence."""
    p = note_path(vault, day)
    if p.is_file():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: \"보안 노트 {day}\"\ntype: security-note\ndate: {day}\norigin: generated\nmissed: true\n---\n\n# 보안 노트 {day}\n\n오늘은 보지 못했다 — {reason}\n", encoding="utf-8")
    return p


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m kb security note", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["note"])
    ap.add_argument("--date", type=date.fromisoformat, default=None)
    a = ap.parse_args(argv)
    from kb import vault_root
    vault = vault_root()
    if not vault:
        print("STRATA_VAULT 없음", file=sys.stderr)
        return 2
    day = (a.date or date.today()).isoformat()
    store = Store(store_path(vault))
    try:
        p = write(vault, day, store)
    finally:
        store.close()
    print(f"노트 → {p.relative_to(vault)}")
    return 0
