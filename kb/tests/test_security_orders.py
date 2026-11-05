"""Security core, order 2026.11.03-03 task-01 (spec AC6, DEC-2026-11-03-04): one order per urgent (vulnerability, host) with
targets, evidence, due, priority and attribution infra by default; advisories get no order; the same pair on the next day
updates last_seen instead of a second order; promote makes an order from an advisory with the person named; assign
changes attribution and leaves a history row; the note links the order."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.security import note as N, orders as O  # noqa: E402
from kb.security.sources import record  # noqa: E402
from kb.security.store import Store  # noqa: E402

D1, D2 = "2026-11-03", "2026-11-04"


def m(day, target, vuln, rid, grade, sev=9.8):
    return {"id": f"{day}:{target}|{vuln}", "target_ref": target, "record_id": rid, "vuln_id": vuln, "matched_by": "identifier", "version_in_range": True,
            "grade": grade, "reason": f"cvss_v3 {sev} ≥ 9.0 (default)", "severity": sev, "severity_from": "cvss_v3", "threshold": 9.0,
            "sort_key": [0, 0.1, sev, 0], "detail": {"target_version": "1.0", "fixed": "1.1"}}


class OrdersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "security").mkdir()
        self.store = Store(self.vault / ".kb" / "security.sqlite")
        self.store.upsert_records([
            record("ubuntu-usn:USN-1", "vuln", "os-vendor", "ubuntu-usn", vuln_id="USN-1", title="OpenSSH vulnerabilities", source_url="https://usn/1", kev=True,
                   scores={"cvss_v3": 9.8, "cvss_v4": None, "cna": None, "vendor": None}),
            record("osv:X", "vuln", "ecosystem", "osv", vuln_id="CVE-2", title="low thing", source_url="https://osv/X", scores={"cvss_v3": 5.0, "cvss_v4": None, "cna": None, "vendor": None}),
        ], collected_at=D1 + "T08:00:00")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def day(self, day, rows):
        for r in rows:
            r["first_seen"] = self.store.touch_first_seen(r["target_ref"], r["vuln_id"], day)
        self.store.replace_matches(day, rows)

    def test_urgent_grouped_per_host_advisory_none_dedupe_next_day(self):
        self.day(D1, [m(D1, "infra/gpu-server/openssh-server", "USN-1", "ubuntu-usn:USN-1", "urgent"), m(D1, "infra/gpu-server/openssh-client", "USN-1", "ubuntu-usn:USN-1", "urgent"),
                      m(D1, "demo/repo/lib", "CVE-2", "osv:X", "advisory", 5.0)])
        made = O.create_orders(self.vault, date(2026, 11, 3), self.store)
        self.assertEqual(len(made), 1)
        doc = yaml.safe_load(made[0].read_text(encoding="utf-8"))["order"]
        self.assertEqual(doc["attributed_to"], "infra")
        self.assertEqual(doc["host"], "infra/gpu-server")
        self.assertEqual(len(doc["targets"]), 2)
        self.assertEqual(doc["due"], "2026-11-06")                     # KEV → 3 days
        self.assertEqual(doc["evidence"]["source_url"], "https://usn/1")
        self.assertEqual(doc["priority"][2], 9.8)
        self.assertIn("projects/infra/tasks/2026.11.03/01-sec-usn-1/_order.yaml", str(made[0]))
        self.assertEqual(self.store.first_seen_all()["infra/gpu-server/openssh-server|USN-1"]["order_ref"], "projects/infra/tasks/2026.11.03/01-sec-usn-1/_order.yaml")
        self.assertFalse(list(self.vault.glob("projects/demo/**/_order.yaml")))   # the advisory got none
        # next day, same pair: no second order, last_seen moves
        self.day(D2, [m(D2, "infra/gpu-server/openssh-server", "USN-1", "ubuntu-usn:USN-1", "urgent")])
        made2 = O.create_orders(self.vault, date(2026, 11, 4), self.store)
        self.assertEqual(made2, [])
        doc = yaml.safe_load(made[0].read_text(encoding="utf-8"))["order"]
        self.assertEqual(doc["last_seen"], D2)
        # the note links the order
        self.store.save_run(D2, D2 + "T08:00:00", D2 + "T08:01:00", {"general-db": "ok"}, {}, None)
        text = N.build(self.vault, D2, self.store, [])
        self.assertIn("[오더](../../projects/infra/tasks/2026.11.03/01-sec-usn-1/_order.yaml)", text)

    def test_promote_and_assign(self):
        self.day(D1, [m(D1, "demo/repo/lib", "CVE-2", "osv:X", "advisory", 5.0)])
        made = O.create_orders(self.vault, date(2026, 11, 3), self.store, match_ids=[f"{D1}:demo/repo/lib|CVE-2"], by="reviewer", to_project="demo")
        self.assertEqual(len(made), 1)
        doc = yaml.safe_load(made[0].read_text(encoding="utf-8"))["order"]
        self.assertEqual((doc["promoted_by"], doc["attributed_to"], doc["due"]), ("reviewer", "demo", "2026-11-17"))
        p = O.assign(self.vault, str(made[0].relative_to(self.vault)), "web-app", by="reviewer")
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))["order"]
        self.assertEqual(doc["attributed_to"], "web-app")
        self.assertEqual(doc["history"][-1]["event"], "assigned")
        self.assertEqual((doc["history"][-1]["from"], doc["history"][-1]["to"]), ("demo", "web-app"))
        self.assertTrue(p.is_file())                                      # the file did not move


if __name__ == "__main__":
    unittest.main()
