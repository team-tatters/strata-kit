"""The collected store: $STRATA_VAULT/.kb/security.sqlite (git-ignored, DEC-2026-11-03-05). Records keep the G2 fields
as collected — empty stays empty; a value filled from another source carries filled_from. matches, first_seen and runs
are also here so a note can be rebuilt from the store; their git copies are security/matches, security/runs."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, vuln_id TEXT, aliases TEXT, layer TEXT NOT NULL, source_id TEXT NOT NULL,
  title TEXT, source_url TEXT, published TEXT, modified TEXT, affected TEXT, scores TEXT, severity_label TEXT,
  kev INTEGER, epss REAL, epss_pct REAL, filled_from TEXT, mentions TEXT, version TEXT, security_mentioned INTEGER,
  collected_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_vuln ON records(vuln_id);
CREATE INDEX IF NOT EXISTS records_published ON records(published);
CREATE TABLE IF NOT EXISTS kev (cve TEXT PRIMARY KEY, date_added TEXT, vendor TEXT, product TEXT, seen_at TEXT);
CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY, day TEXT NOT NULL, target_ref TEXT NOT NULL, record_id TEXT NOT NULL, vuln_id TEXT,
  matched_by TEXT NOT NULL, version_in_range TEXT, grade TEXT, reason TEXT, sort_key TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS matches_day ON matches(day);
CREATE TABLE IF NOT EXISTS first_seen (
  pair TEXT PRIMARY KEY, target_ref TEXT NOT NULL, vuln_id TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  closed TEXT, order_ref TEXT);
CREATE TABLE IF NOT EXISTS runs (day TEXT PRIMARY KEY, started TEXT, finished TEXT, layers TEXT, counts TEXT, note_path TEXT);
"""
JSON_COLS = ("aliases", "affected", "scores", "filled_from", "mentions")


def store_path(vault: Path) -> Path:
    return vault / ".kb" / "security.sqlite"


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    # records ---------------------------------------------------------------
    def upsert_records(self, records: list[dict], collected_at: str) -> int:
        n = 0
        for r in records:
            row = dict(r)
            row.setdefault("collected_at", collected_at)
            for c in JSON_COLS:
                row[c] = json.dumps(row.get(c), ensure_ascii=False) if row.get(c) is not None else None
            if row.get("kev") is not None:
                row["kev"] = 1 if row["kev"] else 0
            if row.get("security_mentioned") is not None:
                row["security_mentioned"] = 1 if row["security_mentioned"] else 0
            cols = [c for c in ("id", "kind", "vuln_id", "aliases", "layer", "source_id", "title", "source_url", "published", "modified",
                                "affected", "scores", "severity_label", "kev", "epss", "epss_pct", "filled_from", "mentions", "version",
                                "security_mentioned", "collected_at") if c in row]
            self.db.execute(f"INSERT OR REPLACE INTO records ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[c] for c in cols])
            n += 1
        self.db.commit()
        return n

    def _row(self, r) -> dict:
        d = dict(r)
        for c in JSON_COLS:
            d[c] = json.loads(d[c]) if d.get(c) else (None if c in ("filled_from",) else [])
        d["kev"] = None if d["kev"] is None else bool(d["kev"])
        d["security_mentioned"] = None if d.get("security_mentioned") is None else bool(d["security_mentioned"])
        return d

    def record(self, rid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return self._row(r) if r else None

    def records(self, where: str = "1=1", args: tuple = ()) -> list[dict]:
        return [self._row(r) for r in self.db.execute(f"SELECT * FROM records WHERE {where}", args)]

    def records_by_vuln(self, vuln_id: str) -> list[dict]:
        return self.records("vuln_id=? OR aliases LIKE ?", (vuln_id, f'%"{vuln_id}"%'))

    def collected_on(self, day: str) -> list[dict]:
        return self.records("collected_at LIKE ?", (day + "%",))

    def update_record(self, rid: str, **fields) -> None:
        row = dict(fields)
        for c in JSON_COLS:
            if c in row and row[c] is not None:
                row[c] = json.dumps(row[c], ensure_ascii=False)
        if "kev" in row and row["kev"] is not None:
            row["kev"] = 1 if row["kev"] else 0
        self.db.execute(f"UPDATE records SET {', '.join(f'{k}=?' for k in row)} WHERE id=?", [*row.values(), rid])
        self.db.commit()

    # kev -------------------------------------------------------------------
    def set_kev(self, entries: list[dict], seen_at: str) -> None:
        self.db.executemany("INSERT OR REPLACE INTO kev (cve, date_added, vendor, product, seen_at) VALUES (?,?,?,?,?)",
                            [(e["cve"], e.get("date_added"), e.get("vendor"), e.get("product"), seen_at) for e in entries])
        self.db.commit()

    def kev_set(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT cve FROM kev")}

    def kev_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM kev").fetchone()[0]

    # matches · first_seen · runs ------------------------------------------
    def replace_matches(self, day: str, matches: list[dict]) -> None:
        self.db.execute("DELETE FROM matches WHERE day=?", (day,))
        for m in matches:
            self.db.execute("INSERT OR REPLACE INTO matches (id, day, target_ref, record_id, vuln_id, matched_by, version_in_range, grade, reason, sort_key, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (m["id"], day, m["target_ref"], m["record_id"], m.get("vuln_id"), m["matched_by"], str(m.get("version_in_range")),
                             m.get("grade"), m.get("reason"), json.dumps(m.get("sort_key")), json.dumps(m.get("detail"), ensure_ascii=False)))
        self.db.commit()

    def matches_on(self, day: str) -> list[dict]:
        out = []
        for r in self.db.execute("SELECT * FROM matches WHERE day=?", (day,)):
            d = dict(r)
            d["sort_key"] = json.loads(d["sort_key"]) if d["sort_key"] else None
            d["detail"] = json.loads(d["detail"]) if d["detail"] else {}
            d["version_in_range"] = {"True": True, "False": False}.get(d.get("version_in_range"), None)
            out.append(d)
        return out

    def touch_first_seen(self, target_ref: str, vuln_id: str, day: str) -> str:
        pair = f"{target_ref}|{vuln_id}"
        r = self.db.execute("SELECT first_seen FROM first_seen WHERE pair=?", (pair,)).fetchone()
        if r:
            self.db.execute("UPDATE first_seen SET last_seen=? WHERE pair=?", (day, pair))
            first = r[0]
        else:
            self.db.execute("INSERT INTO first_seen (pair, target_ref, vuln_id, first_seen, last_seen) VALUES (?,?,?,?,?)", (pair, target_ref, vuln_id, day, day))
            first = day
        self.db.commit()
        return first

    def first_seen_all(self) -> dict[str, dict]:
        return {r["pair"]: dict(r) for r in self.db.execute("SELECT * FROM first_seen")}

    def set_closed(self, target_ref: str, vuln_id: str, day: str | None, order_ref: str | None = None) -> None:
        self.db.execute("UPDATE first_seen SET closed=?, order_ref=COALESCE(?, order_ref) WHERE pair=?", (day, order_ref, f"{target_ref}|{vuln_id}"))
        self.db.commit()

    def set_order_ref(self, target_ref: str, vuln_id: str, order_ref: str) -> None:
        self.db.execute("UPDATE first_seen SET order_ref=? WHERE pair=?", (order_ref, f"{target_ref}|{vuln_id}"))
        self.db.commit()

    def save_run(self, day: str, started: str, finished: str | None, layers: dict, counts: dict, note_path: str | None) -> None:
        self.db.execute("INSERT OR REPLACE INTO runs (day, started, finished, layers, counts, note_path) VALUES (?,?,?,?,?,?)",
                        (day, started, finished, json.dumps(layers, ensure_ascii=False), json.dumps(counts), note_path))
        self.db.commit()

    def run(self, day: str) -> dict | None:
        r = self.db.execute("SELECT * FROM runs WHERE day=?", (day,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["layers"], d["counts"] = json.loads(d["layers"] or "{}"), json.loads(d["counts"] or "{}")
        return d

    def last_success(self) -> str | None:
        r = self.db.execute("SELECT MAX(finished) FROM runs WHERE finished IS NOT NULL").fetchone()
        return r[0] if r else None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso(today: date | None = None) -> str:
    return (today or date.today()).isoformat()
