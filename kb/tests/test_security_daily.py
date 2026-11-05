"""Security core, order 2026.11.03-02 task-05 (spec AC8): the daily run writes a run record with the layer status and
counts and a note; a step that fails is recorded and the later steps still run; days without a run since the last one get
the one-line "오늘은 보지 못했다" note; nothing is committed without --commit."""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))
FX = KIT / "kb" / "tests" / "fixtures" / "security" / "sources"

from kb.security import daily as D  # noqa: E402
from kb.security.http import fixture_http  # noqa: E402
from kb.security.store import Store  # noqa: E402


class DailyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "security").mkdir(parents=True)
        (self.vault / "security" / "registry.yaml").write_text(yaml.safe_dump({"version": "0.1", "targets": [
            {"project": "demo", "environment": "repo", "kind": "lockfile", "sources": ["{workspace}/repo/uv.lock"], "ecosystem": "pypi"}]}), encoding="utf-8")
        (self.vault.parent / "repo").mkdir()
        (self.vault.parent / "repo" / "uv.lock").write_text((FX.parent / "uv.lock").read_text(encoding="utf-8").replace('version = "6.0.2"', 'version = "5.3"'), encoding="utf-8")
        (self.vault / "security" / "sources.yaml").write_text(yaml.safe_dump({"version": "0.1", "sources": [
            {"id": "cisa-kev", "layer": "general-db", "url": "https://www.cisa.gov/kev.json", "fetch": "json"},
            {"id": "osv", "layer": "ecosystem", "url": "https://api.osv.dev/v1/querybatch", "fetch": "api"},
            {"id": "ubuntu-usn", "layer": "os-vendor", "url": "https://ubuntu.com/security/notices.json", "fetch": "json"},
            {"id": "dead-feed", "layer": "trend", "url": "https://nowhere.invalid/feed", "fetch": "rss"}], "manual_links": []}), encoding="utf-8")
        batch = json.loads((FX / "osv-querybatch.json").read_text(encoding="utf-8"))
        ids = [v["id"] for res in batch["results"] for v in res.get("vulns", [])]
        mapping = {"cisa.gov": (FX / "kev.json").read_text(encoding="utf-8"), "querybatch": batch, "ubuntu.com": (FX / "usn.json").read_text(encoding="utf-8")}
        mapping.update({f"/v1/vulns/{i}": (FX / "osv-vuln-pypi.json").read_text(encoding="utf-8") for i in ids})
        self.http = fixture_http(mapping)
        self.store = Store(self.vault / ".kb" / "security.sqlite")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_run_record_note_gap_and_failure_isolation(self):
        # a run three days ago, then nothing: today's run must leave gap notes for the two days between
        (self.vault / "security" / "runs").mkdir()
        (self.vault / "security" / "runs" / "2026-10-31.yaml").write_text("day: 2026-10-31\n", encoding="utf-8")
        rec = D.run(self.vault, date(2026, 11, 3), since=date(2026, 10, 1), http=self.http, store=self.store, log=lambda m: None)
        self.assertEqual(rec["missed_days"], ["2026-11-01", "2026-11-02"])
        for d in rec["missed_days"]:
            self.assertIn("오늘은 보지 못했다", (self.vault / "security" / "notes" / f"{d}.md").read_text(encoding="utf-8"))
        self.assertEqual(rec["steps"]["inventory"]["status"], "ok")
        self.assertEqual(rec["steps"]["collect"]["status"], "ok")
        self.assertEqual(rec["layers"]["trend"], "failed")                 # the dead feed, recorded, not fatal
        self.assertEqual(rec["layers"]["ecosystem"], "ok")
        self.assertGreaterEqual(rec["counts"]["candidates"], 1)            # pyyaml 5.3 → CVE-2020-1747
        self.assertGreaterEqual(rec["counts"]["urgent"] + rec["counts"]["advisory"], 1)
        run_file = yaml.safe_load((self.vault / "security" / "runs" / "2026-11-03.yaml").read_text(encoding="utf-8"))
        self.assertEqual(run_file["layers"]["trend"], "failed")
        self.assertIn("dead-feed", run_file["sources"])
        note = (self.vault / rec["note_path"]).read_text(encoding="utf-8")
        self.assertIn("오늘 보지 못한 층: trend", note)
        self.assertIn("CVE-2020-1747", note)
        self.assertTrue((self.vault / "projects" / "demo" / "security" / "inventory" / "repo.yaml").is_file())
        self.assertNotIn("commit", rec["steps"])

    def test_first_run_ever_writes_no_gap_notes(self):
        rec = D.run(self.vault, date(2026, 11, 3), since=date(2026, 10, 1), http=self.http, store=self.store, log=lambda m: None)
        self.assertEqual(rec["missed_days"], [])
        self.assertEqual(sorted(p.name for p in (self.vault / "security" / "notes").glob("*.md")), ["2026-11-03.md"])

    def test_failed_step_does_not_stop_the_note(self):
        (self.vault / "security" / "sources.yaml").unlink()                # collect cannot even start
        rec = D.run(self.vault, date(2026, 11, 3), http=self.http, store=self.store, log=lambda m: None)
        self.assertEqual(rec["steps"]["collect"]["status"], "failed")
        self.assertIn("원천 등록 없음", rec["steps"]["collect"]["error"])
        self.assertEqual(rec["steps"]["match"]["status"], "ok")
        self.assertEqual(rec["steps"]["note"]["status"], "ok")
        self.assertTrue((self.vault / "security" / "notes" / "2026-11-03.md").is_file())


if __name__ == "__main__":
    unittest.main()
