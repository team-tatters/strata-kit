"""Security core, order 2026.11.03-02 task-03 (spec AC4, DEC-2026-11-03-02): the default threshold 9.0 makes 9.1 urgent and
8.9 advisory; setting the repository threshold to 8.0 makes 8.9 urgent and leaves one history row with value and date;
a KEV entry scoring 7.5 stays advisory (KEV orders, never grades); a prod override applies by environment; a candidate
without any score is advisory with reason no-score; out-of-range matches and accepted risks inside their term are
filtered with their reason; the vendor score is used when no CVSS is present."""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.security import grade as G  # noqa: E402

DAY = "2026-11-03"


def rec(cvss3=None, cna=None, vendor=None, kev=None, epss=None, kind="vuln", **extra):
    return {"id": "r", "kind": kind, "scores": {"cvss_v4": None, "cvss_v3": cvss3, "cna": cna, "vendor": vendor}, "kev": kev, "epss": epss, **extra}


def m(target="demo/dev/x", vuln="CVE-1", in_range=True):
    return {"id": f"{DAY}:{target}|{vuln}", "target_ref": target, "record_id": "r", "vuln_id": vuln, "matched_by": "identifier", "version_in_range": in_range, "detail": {}}


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.g = G.load_grading(self.vault, "demo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_threshold_splits_at_nine(self):
        self.assertEqual(G.grade_match(m(), rec(cvss3=9.1), self.g, [], DAY)["grade"], "urgent")
        self.assertEqual(G.grade_match(m(), rec(cvss3=8.9), self.g, [], DAY)["grade"], "advisory")
        self.assertEqual(G.grade_match(m(), rec(cvss3=9.0), self.g, [], DAY)["grade"], "urgent")

    def test_repository_threshold_change_is_applied_and_recorded(self):
        doc = G.set_threshold(self.vault, "demo", 8.0, by="tester", at="2026-11-03T10:00:00")
        self.assertEqual(G.grade_match(m(), rec(cvss3=8.9), doc, [], DAY)["grade"], "urgent")
        self.assertEqual(len(doc["history"]), 1)
        self.assertEqual((doc["history"][0]["from"], doc["history"][0]["to"], doc["history"][0]["by"], doc["history"][0]["at"]), (9.0, 8.0, "tester", "2026-11-03T10:00:00"))
        on_disk = yaml.safe_load(G.grading_path(self.vault, "demo").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["default"]["threshold"], 8.0)
        self.assertEqual(len(on_disk["history"]), 1)

    def test_kev_below_threshold_stays_advisory_but_sorts_first(self):
        g = G.grade_match(m(), rec(cvss3=7.5, kev=True, epss=0.9), self.g, [], DAY)
        self.assertEqual(g["grade"], "advisory")
        self.assertIn("kev", g["reason"])
        self.assertEqual(g["sort_key"][:2], [1, 0.9])

    def test_environment_override_and_cna_or_vendor_fallback(self):
        doc = G.set_threshold(self.vault, "demo", 8.5, by="tester", environment="prod")
        self.assertEqual(G.grade_match(m("demo/prod/x"), rec(cvss3=8.7), doc, [], DAY)["grade"], "urgent")
        self.assertEqual(G.grade_match(m("demo/dev/x"), rec(cvss3=8.7), doc, [], DAY)["grade"], "advisory")
        g = G.grade_match(m(), rec(cna=9.8), self.g, [], DAY)          # NVD empty, CNA 9.8 — the bifrost case
        self.assertEqual((g["grade"], g["severity_from"]), ("urgent", "cna"))
        g = G.grade_match(m(), rec(vendor=7.5), self.g, [], DAY)
        self.assertEqual((g["grade"], g["severity_from"]), ("advisory", "vendor"))

    def test_no_score_out_of_range_accepted_and_new_post(self):
        g = G.grade_match(m(), rec(), self.g, [], DAY)
        self.assertEqual((g["grade"], g["reason"]), ("advisory", "no-score"))
        g = G.grade_match(m(in_range=False), rec(cvss3=9.9), self.g, [], DAY)
        self.assertEqual((g["grade"], g["reason"]), ("filtered", "out-of-range"))
        acc = [{"target_ref": "demo/dev/x", "vuln_id": "CVE-1", "until": "2026-12-31", "status": "active"}]
        self.assertEqual(G.grade_match(m(), rec(cvss3=9.9), self.g, acc, DAY)["grade"], "filtered")
        acc[0]["until"] = "2026-11-02"
        self.assertEqual(G.grade_match(m(), rec(cvss3=9.9), self.g, acc, DAY)["grade"], "urgent")   # expired → shows again
        g = G.grade_match(m(), rec(kind="release", security_mentioned=True), self.g, [], DAY)
        self.assertEqual((g["grade"], g["reason"]), ("advisory", "new-post security-mentioned"))
        nr = m(); nr["detail"] = {"not_running": True, "running_kernel": "6.8.0-137-generic"}
        g = G.grade_match(nr, rec(cvss3=9.8), self.g, [], DAY)
        self.assertEqual(g["grade"], "advisory")
        self.assertIn("installed-not-running", g["reason"])
        g = G.grade_match(m(in_range=None), rec(cvss3=9.5), self.g, [], DAY)
        self.assertEqual(g["grade"], "urgent")
        self.assertIn("version-unknown", g["reason"])


if __name__ == "__main__":
    unittest.main()
