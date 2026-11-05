"""Security core, order 2026.11.03-03 tasks 02·03 (spec AC7·AC11·AC12, DEC-2026-11-03-02): the plan names the executor and
the condition from the target's kind (library → code level, image → minutes swap, package → none with a pre-deploy
skeleton); run refuses with exit 3 when no condition holds and with exit 4 when a user-accepted run has no recorded
acceptance; a lockfile bump runs through the injected runner on a branch and leaves an execution record and a closed
order; close marks the pairs closed so the note shows them once; accept refuses without a term, filters inside the term
and marks the pair expired after it."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.security import close as CL, grade as G, note as N, orders as O, patch as P  # noqa: E402
from kb.security.sources import record  # noqa: E402
from kb.security.store import Store  # noqa: E402

D1, D2, D3 = "2026-11-03", "2026-11-04", "2026-11-05"


def m(day, target, vuln, rid, grade="urgent", sev=9.8, version="5.3", fixed="5.3.1"):
    return {"id": f"{day}:{target}|{vuln}", "target_ref": target, "record_id": rid, "vuln_id": vuln, "matched_by": "identifier", "version_in_range": True,
            "grade": grade, "reason": f"cvss_v3 {sev} ≥ 9.0 (default)", "severity": sev, "severity_from": "cvss_v3", "threshold": 9.0,
            "sort_key": [0, 0.1, sev, 0], "detail": {"target_version": version, "fixed": fixed}}


class PatchCloseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "security").mkdir(parents=True)
        self.repo = self.vault.parent / "repo"
        self.repo.mkdir()
        (self.repo / "uv.lock").write_text('[[package]]\nname = "pyyaml"\nversion = "5.3"\nsource = { registry = "x" }\n', encoding="utf-8")
        (self.vault / "security" / "registry.yaml").write_text(yaml.safe_dump({"version": "0.1", "targets": [
            {"project": "demo", "environment": "repo", "kind": "lockfile", "sources": ["{workspace}/repo/uv.lock"], "ecosystem": "pypi"}]}), encoding="utf-8")
        (self.vault / "security" / "sources.yaml").write_text(yaml.safe_dump({"version": "0.1", "sources": [], "manual_links": [{"target_ref": "infra/dev/traefik", "notice": "github-releases:traefik/traefik"}]}), encoding="utf-8")
        inv = self.vault / "projects" / "demo" / "security" / "inventory"; inv.mkdir(parents=True)
        (inv / "repo.yaml").write_text(yaml.safe_dump({"project": "demo", "environment": "repo", "origin": "generated", "items": [
            {"name": "pyyaml", "version": "5.3", "environment": "repo", "kind": "library", "source": "osv", "identifier": "pkg:pypi/pyyaml@5.3"}]}), encoding="utf-8")
        inv2 = self.vault / "projects" / "infra" / "security" / "inventory"; inv2.mkdir(parents=True)
        (inv2 / "dev.yaml").write_text(yaml.safe_dump({"project": "infra", "environment": "dev", "origin": "generated", "items": [
            {"name": "traefik", "version": "v3.7.16", "environment": "dev", "kind": "image", "image": "traefik", "source": "github-releases:traefik/traefik", "identifier": "none"},
            {"name": "curl", "version": "8.5.0-2ubuntu10.11", "environment": "dev", "kind": "package", "source": "ubuntu-usn", "identifier": "pkg:deb/ubuntu/curl@8.5.0-2ubuntu10.11?distro=noble", "codename": "noble"}]}), encoding="utf-8")
        self.store = Store(self.vault / ".kb" / "security.sqlite")
        self.store.upsert_records([
            record("osv:X", "vuln", "ecosystem", "osv", vuln_id="CVE-2020-1747", title="pyyaml", source_url="https://osv/X", scores={"cvss_v3": 9.8, "cvss_v4": None, "cna": None, "vendor": None}),
            record("github-advisories:GHSA-t", "vuln", "ecosystem", "github-advisories", vuln_id="GHSA-t", title="traefik thing", scores={"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": 9.3}),
            record("github-releases:traefik/traefik:v3.7.17", "release", "os-vendor", "github-releases", version="v3.7.17", published="2026-10-30"),
            record("ubuntu-usn:USN-1", "vuln", "os-vendor", "ubuntu-usn", vuln_id="USN-1", title="curl", scores={"cvss_v3": 9.8, "cvss_v4": None, "cna": None, "vendor": None}),
        ], collected_at=D1 + "T08:00:00")
        rows = [m(D1, "demo/repo/pyyaml", "CVE-2020-1747", "osv:X"), m(D1, "infra/dev/traefik", "GHSA-t", "github-advisories:GHSA-t", version="v3.7.16", fixed=None),
                m(D1, "infra/dev/curl", "USN-1", "ubuntu-usn:USN-1", version="8.5.0-2ubuntu10.11", fixed="8.5.0-2ubuntu10.16")]
        for r in rows:
            r["first_seen"] = self.store.touch_first_seen(r["target_ref"], r["vuln_id"], D1)
        self.store.replace_matches(D1, rows)
        self.orders = {p.parent.name.split("-sec-")[1]: str(p.relative_to(self.vault)) for p in O.create_orders(self.vault, date(2026, 11, 3), self.store)}

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def order(self, key):
        return yaml.safe_load((self.vault / self.orders[key]).read_text(encoding="utf-8").split("\n", 1)[1])["order"]

    def test_plan_conditions_by_kind(self):
        lib = P.cmd_plan(self.vault, self.orders["cve-2020-1747"], self.store)
        self.assertEqual((lib["executor"], lib["condition"], lib["to_version"], lib["downtime_expected"]), ("lockfile_bump", "code-level", "5.3.1", "none"))
        img = P.cmd_plan(self.vault, self.orders["ghsa-t"], self.store)
        self.assertEqual((img["executor"], img["condition"], img["to_version"]), ("compose_tag", "minutes-swap", "v3.7.17"))
        self.assertTrue(any("docker compose" in c for c in img["server_commands"]))
        pkg = P.cmd_plan(self.vault, self.orders["usn-1"], self.store)
        self.assertEqual((pkg["executor"], pkg["condition"]), ("none", "none"))
        self.assertIn("되돌림", pkg["pre_deploy_note"])

    def test_run_refusals_then_accepted(self):
        rc, info = P.cmd_run(self.vault, self.orders["usn-1"], self.store)
        self.assertEqual(rc, 3)
        self.assertIn("조건 없음", info["refused"])
        o = self.order("usn-1")
        self.assertEqual(o["history"][-1]["event"], "run-refused")
        o["patch_plan"]["condition"] = "user-accepted"          # a run that needs the person's acceptance …
        p = self.vault / self.orders["usn-1"]
        head, body = p.read_text(encoding="utf-8").split("\n", 1)
        p.write_text(head + "\n" + yaml.safe_dump({"order": o}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        rc, info = P.cmd_run(self.vault, self.orders["usn-1"], self.store)
        self.assertEqual(rc, 4)                                  # … and has none recorded → refused
        self.assertIn("수락", info["refused"])
        rc, info = P.cmd_run(self.vault, self.orders["usn-1"], self.store, accepted_by="reviewer", accepted_text="dev 서버 수 분 다운타임 수락", dry_run=True)
        self.assertEqual((rc, info["condition"]), (0, "user-accepted"))
        self.assertEqual(self.order("usn-1")["acceptance_record"]["by"], "reviewer")

    def test_lockfile_bump_runs_through_runner_and_closes(self):
        calls = []
        def runner(cmd, cwd):
            calls.append(cmd)
            if cmd[0] == "uv":
                (self.repo / "uv.lock").write_text((self.repo / "uv.lock").read_text(encoding="utf-8").replace('"5.3"', '"5.3.1"'), encoding="utf-8")
            return 0, "ok"
        P.cmd_plan(self.vault, self.orders["cve-2020-1747"], self.store)
        rc, entry = P.cmd_run(self.vault, self.orders["cve-2020-1747"], self.store, runner=runner, day=date(2026, 11, 4))
        self.assertEqual((rc, entry["result"], entry["from"], entry["to"], entry["downtime"]), (0, "committed-on-branch", "5.3", "5.3.1", "none"))
        self.assertEqual(calls[0][:3], ["git", "checkout", "-b"])
        self.assertTrue(any(c[0] == "uv" for c in calls))
        self.assertTrue(all(c[:2] != ["git", "push"] for c in calls))
        o = self.order("cve-2020-1747")
        self.assertEqual((o["status"], o["closed"]["reason"], len(o["execution"])), ("closed", "patched", 1))
        self.assertEqual(self.store.first_seen_all()["demo/repo/pyyaml|CVE-2020-1747"]["closed"], D2)
        self.store.save_run(D2, D2 + "T08:00:00", D2 + "T08:01:00", {"general-db": "ok"}, {}, None)
        text = N.build(self.vault, D2, self.store, [])
        self.assertIn("CVE-2020-1747", text.split("## 닫힌 항목")[1].split("## 눈이 없는 대상")[0])

    def test_close_and_accept_rules(self):
        p = CL.close_order(self.vault, self.orders["ghsa-t"], "reviewer", "not-affected", self.store, date(2026, 11, 4))
        o = yaml.safe_load(p.read_text(encoding="utf-8").split("\n", 1)[1])["order"]
        self.assertEqual((o["status"], o["closed"]["by"]), ("closed", "reviewer"))
        with self.assertRaises(ValueError):
            CL.accept(self.vault, "infra", "infra/dev/curl", "USN-1", "낮은 노출", "", "reviewer")
        CL.accept(self.vault, "infra", "infra/dev/curl", "USN-1", "내부망만, 다음 유지보수 창에", "2026-11-10", "reviewer")
        rows = yaml.safe_load(G.accepted_path(self.vault, "infra").read_text(encoding="utf-8"))["accepted"]
        self.assertEqual((rows[0]["until"], rows[0]["by"], rows[0]["status"]), ("2026-11-10", "reviewer", "active"))
        g = G.load_grading(self.vault, "infra")
        inside = G.grade_match(m(D2, "infra/dev/curl", "USN-1", "ubuntu-usn:USN-1"), self.store.record("ubuntu-usn:USN-1"), g, rows, "2026-11-05")
        self.assertEqual((inside["grade"], inside["reason"]), ("filtered", "accepted-risk until 2026-11-10"))
        after = G.grade_match(m("2026-11-12", "infra/dev/curl", "USN-1", "ubuntu-usn:USN-1"), self.store.record("ubuntu-usn:USN-1"), g, rows, "2026-11-12")
        self.assertEqual(after["grade"], "urgent")
        self.assertIn("수용 기한 만료 2026-11-10", after["reason"])


if __name__ == "__main__":
    unittest.main()
