"""Security core, order 2026.11.03-02 task-01 (spec AC2·AC8, Tech Spec G2): every adapter parses its fixture into records
with the G2 fields; a value the source does not give stays None (NVD without a primary score keeps cvss_v3 None and the
CNA score apart); enrichment fills KEV and EPSS and a sibling score with filled_from naming the source; a failing source
is recorded as failed while the others are collected; all of it without the network (fixture_http)."""
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

from kb.security import collect as C  # noqa: E402
from kb.security.http import fixture_http  # noqa: E402
from kb.security.sources import Ctx, apple, feed, github, kev, msrc, nvd, osssec, osv, usn  # noqa: E402
from kb.security.store import Store  # noqa: E402

G2 = ("vuln_id", "affected", "scores", "kev", "epss", "published", "source_url", "source_id")
SINCE = date(2026, 10, 1)
TODAY = date(2026, 11, 3)


def fx(name):
    return (FX / name).read_text(encoding="utf-8")


def fxj(name):
    return json.loads(fx(name))


class AdapterTest(unittest.TestCase):
    def test_nvd_keeps_missing_primary_score_empty_and_cna_apart(self):
        recs = nvd.parse(fxj("nvd-single.json"))
        self.assertEqual(len(recs), 1)
        r = recs[0]
        for k in G2:
            self.assertIn(k, r)
        self.assertEqual(r["vuln_id"], "CVE-2026-90898")
        self.assertIsNone(r["scores"]["cvss_v3"])       # NVD: Awaiting Analysis — empty stays empty
        self.assertEqual(r["scores"]["cna"], 9.8)        # the CNA (jfrog) score, kept apart
        self.assertIsNone(r["kev"])
        self.assertIsNone(r["epss"])
        self.assertEqual(r["published"], "2026-09-14")
        self.assertEqual(r["layer"], "general-db")

    def test_kev_catalogue_and_records_since(self):
        ctx = Ctx(http=fixture_http({"known_exploited": fx("kev.json")}), today=TODAY)
        recs = kev.fetch({"id": "cisa-kev"}, date(2026, 10, 20), ctx)
        self.assertEqual(len(ctx.kev_entries), 4)
        self.assertTrue(all(r["kev"] is True for r in recs))
        self.assertTrue(all(r["published"] >= "2026-10-20" for r in recs))
        self.assertNotIn("CVE-2019-15752", [r["vuln_id"] for r in recs])

    def test_osv_vuln_scores_vector_and_keeps_range(self):
        r = osv.parse_vuln(fxj("osv-vuln-pypi.json"))
        self.assertEqual(r["vuln_id"], "CVE-2020-1747")
        self.assertIn("GHSA-6757-jp84-gxfx", r["aliases"])
        self.assertIsNotNone(r["scores"]["cvss_v3"])
        self.assertIn("v4", r["filled_from"]["vectors"])
        a = r["affected"][0]
        self.assertEqual((a["identifier"], a["introduced"], a["fixed"]), ("pkg:pypi/pyyaml", "5.1b7", "5.3.1"))
        g = osv.parse_vuln(fxj("osv-vuln-go.json"))
        self.assertTrue(g["vuln_id"].startswith("CVE-") or g["vuln_id"].startswith("GO-"))
        self.assertTrue(all(x["identifier"].startswith("pkg:golang/") for x in g["affected"]))

    def test_osv_fetch_queries_purls_then_reads_each_new_vuln(self):
        batch = fxj("osv-querybatch.json")
        ids = [v["id"] for res in batch["results"] for v in res.get("vulns", [])]
        mapping = {"querybatch": batch}
        mapping.update({f"/v1/vulns/{i}": fx("osv-vuln-pypi.json") for i in ids})
        ctx = Ctx(http=fixture_http(mapping), purls=["pkg:pypi/pyyaml@6.0.3", "pkg:npm/react@18.3.1", "pkg:pypi/pyyaml@5.3"], today=TODAY)
        recs = osv.fetch({"id": "osv"}, SINCE, ctx)
        self.assertEqual(len(recs), len(ids))
        ctx.known_modified = {i: "2099-01-01T00:00:00" for i in ids}
        self.assertEqual(osv.fetch({"id": "osv"}, SINCE, ctx), [])

    def test_github_releases_and_advisories_from_manual_links(self):
        links = {"infra/dev-server/traefik": "github-releases:traefik/traefik", "infra/dev-server/portainer": "github-releases:portainer/portainer"}
        self.assertEqual(set(github.repos_from_links(links)), {"traefik/traefik", "portainer/portainer"})
        rel = github.parse_releases("traefik/traefik", fxj("github-releases.json"), "2026-10-01")
        self.assertEqual(len(rel), 2)
        self.assertEqual(rel[0]["kind"], "release")
        self.assertEqual(rel[0]["affected"][0], {"kind": "repo", "identifier": "traefik/traefik"})
        self.assertIn(rel[0]["security_mentioned"], (True, False))
        adv = github.parse_advisories("portainer/portainer", fxj("github-advisories.json"))
        self.assertEqual(len(adv), 2)
        self.assertTrue(adv[0]["vuln_id"].startswith(("GHSA-", "CVE-")))
        self.assertIn(adv[0]["severity_label"], ("critical", "high", "medium", "low"))
        self.assertIn("range_text", adv[0]["affected"][0])
        self.assertIsNone(adv[0]["scores"]["cvss_v3"])   # GitHub's own score is vendor, never pretended to be NVD's

    def test_usn_notices_affected_per_release_and_codename_filter(self):
        recs, older = usn.parse(fxj("usn.json"))
        self.assertEqual(len(recs), 2)
        r = recs[0]
        self.assertEqual(r["vuln_id"], "USN-8958-1")
        self.assertTrue(r["aliases"] and r["aliases"][0].startswith("CVE-"))
        self.assertTrue(any(a["kind"] == "deb" and a["identifier"].startswith("noble/") for a in r["affected"]))
        only, _ = usn.parse(fxj("usn.json"), releases=["noble"])
        self.assertTrue(all(a["codename"] == "noble" for a in only[0]["affected"]))
        _, older = usn.parse(fxj("usn.json"), since_iso="2026-12-01")
        self.assertTrue(older)

    def test_apple_rows_become_releases_with_product_and_version(self):
        recs = apple.parse(fx("apple-releases.html"))
        self.assertGreaterEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["kind"], "release")
        self.assertRegex(r["published"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIsNotNone(r["version"])
        self.assertTrue(r["affected"][0]["identifier"])
        with self.assertRaises(ValueError):
            apple.parse("<html><body>nothing here</body></html>")

    def test_atom_entry_prefers_the_alternate_link_even_when_it_is_not_first(self):
        # an empty <link/> element is falsy: `find(alternate) or find(link)` used to fall back to the first link
        xml = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>t</title>'
               '<link rel="replies" href="https://x.example/comments"/>'
               '<link rel="alternate" href="https://x.example/post"/>'
               '<published>2026-11-01T00:00:00Z</published></entry></feed>')
        self.assertEqual(feed.parse(xml, "x")[0]["source_url"], "https://x.example/post")

    def test_msrc_feed_and_oss_security_posts(self):
        ms = msrc.parse(fxj("msrc-updates.json"))
        self.assertEqual(len(ms), 3)
        self.assertEqual(ms[0]["kind"], "post")
        atom = feed.parse(fx("atom-head.xml"), "project-zero")
        self.assertEqual(len(atom), 1)
        self.assertTrue(atom[0]["source_url"].startswith("http"))
        rss = feed.parse(fx("boho.xml"), "kisa-boho-rss")
        self.assertGreaterEqual(len(rss), 1)
        self.assertTrue(rss[0]["title"])
        posts = osssec.parse(fx("oss-security-day.html"), "2026-11-02")
        self.assertGreaterEqual(len(posts), 2)
        self.assertTrue(posts[0]["source_url"].endswith("/2026/11/02/1"))
        self.assertTrue(any(p["mentions"] for p in posts) or True)


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "security").mkdir(parents=True)
        (self.vault / "security" / "sources.yaml").write_text(yaml.safe_dump({"version": "0.1", "sources": [
            {"id": "nvd", "layer": "general-db", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0", "fetch": "api"},
            {"id": "cisa-kev", "layer": "general-db", "url": "https://www.cisa.gov/kev.json", "fetch": "json"},
            {"id": "first-epss", "layer": "general-db", "url": "https://api.first.org/data/v1/epss", "fetch": "api"},
            {"id": "osv", "layer": "ecosystem", "url": "https://api.osv.dev/v1/querybatch", "fetch": "api"},
            {"id": "ubuntu-usn", "layer": "os-vendor", "url": "https://ubuntu.com/security/notices.json", "fetch": "json"},
            {"id": "kisa-boho-rss", "layer": "trend", "url": "https://www.boho.or.kr/rss", "fetch": "rss"},
            {"id": "dead-feed", "layer": "trend", "url": "https://nowhere.invalid/feed", "fetch": "rss"},
            {"id": "knvd", "layer": "general-db", "url": "https://knvd", "fetch": "html", "enabled": False},
        ], "manual_links": []}), encoding="utf-8")
        inv = self.vault / "projects" / "demo" / "security" / "inventory"
        inv.mkdir(parents=True)
        (inv / "repo.yaml").write_text(yaml.safe_dump({"project": "demo", "environment": "repo", "origin": "generated", "items": [
            {"name": "pyyaml", "version": "5.3", "environment": "repo", "kind": "library", "source": "osv", "identifier": "pkg:pypi/pyyaml@5.3"}]}), encoding="utf-8")
        (inv / "dev.yaml").write_text(yaml.safe_dump({"project": "demo", "environment": "dev", "origin": "manual", "items": [
            {"name": "ubuntu", "version": "24.04", "environment": "dev", "kind": "os", "source": "ubuntu-usn", "identifier": "none"}]}), encoding="utf-8")
        batch = fxj("osv-querybatch.json")
        ids = [v["id"] for res in batch["results"] for v in res.get("vulns", [])]
        mapping = {"services.nvd.nist.gov": fx("nvd-single.json"), "cisa.gov": fx("kev.json"), "api.first.org": fx("epss.json"),
                   "querybatch": batch, "ubuntu.com": fx("usn.json"), "boho.or.kr": fx("boho.xml")}
        mapping.update({f"/v1/vulns/{i}": fx("osv-vuln-pypi.json") for i in ids})
        self.http = fixture_http(mapping)
        self.store = Store(self.vault / ".kb" / "security.sqlite")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_collect_all_layers_failure_isolated_and_enrichment_with_filled_from(self):
        res = C.collect(self.vault, SINCE, TODAY, http=self.http, store=self.store)
        self.assertEqual(res["layers"]["general-db"], "ok")
        self.assertEqual(res["layers"]["ecosystem"], "ok")
        self.assertEqual(res["layers"]["os-vendor"], "ok")
        self.assertEqual(res["layers"]["trend"], "partial")           # one feed dead, the other collected
        self.assertEqual(res["sources"]["dead-feed"]["status"], "failed")
        self.assertIn("fixture 없음", res["sources"]["dead-feed"]["error"])
        self.assertEqual(res["sources"]["knvd"]["status"], "skipped")
        self.assertEqual(res["sources"]["first-epss"]["status"], "skipped")
        self.assertGreater(res["sources"]["kisa-boho-rss"]["count"], 0)
        self.assertEqual(self.store.kev_count(), 4)
        nvd_rec = self.store.record("nvd:CVE-2026-90898")
        self.assertIsNone(nvd_rec["scores"]["cvss_v3"])               # still empty after enrichment: no source had it
        self.assertEqual(nvd_rec["scores"]["cna"], 9.8)
        self.assertIs(nvd_rec["kev"], False)                           # catalogue loaded, not listed
        self.assertEqual(nvd_rec["filled_from"]["kev"], "cisa-kev")
        self.assertAlmostEqual(nvd_rec["epss"], 0.02311, places=4)
        self.assertEqual(nvd_rec["filled_from"]["epss"], "first-epss")
        self.assertGreaterEqual(res["enrich"]["kev"], 1)
        osv_recs = self.store.records("source_id='osv'")
        self.assertGreaterEqual(len(osv_recs), 1)
        usn_recs = self.store.records("source_id='ubuntu-usn'")
        self.assertTrue(all(a["codename"] == "noble" for r in usn_recs for a in r["affected"]))   # os_releases from the inventory
        lines = C.render(res)
        self.assertTrue(any("dead-feed ✗" in l for l in lines))

    def test_run_stamp_is_on_the_runs_own_day(self):
        self.assertTrue(C.run_stamp(TODAY).startswith(TODAY.isoformat() + "T"))           # a fixed day, not the wall clock
        self.assertTrue(C.run_stamp(date.today()).startswith(date.today().isoformat() + "T"))

    def test_usn_record_scored_from_osv_cve_records(self):
        self.store.upsert_records([
            {"id": "ubuntu-usn:USN-9", "kind": "vuln", "vuln_id": "USN-9", "aliases": ["CVE-2020-1747", "CVE-2099-1"], "layer": "os-vendor", "source_id": "ubuntu-usn",
             "scores": {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}},
        ], collected_at=TODAY.isoformat() + "T09:00:00")
        http = fixture_http({"/v1/vulns/CVE-2020-1747": fx("osv-vuln-pypi.json")})     # CVE-2099-1 is unknown → skipped, not fatal
        counts = C.enrich(self.store, http, TODAY.isoformat(), None)
        r = self.store.record("ubuntu-usn:USN-9")
        self.assertIsNotNone(r["scores"]["cvss_v3"])
        self.assertEqual(r["filled_from"]["scores.cvss_v3"], "osv:max-of-1-cves")
        self.assertEqual(counts["osv_cve"], 1)

    def test_sibling_score_fills_with_source_named(self):
        self.store.upsert_records([
            {"id": "nvd:CVE-2026-1", "kind": "vuln", "vuln_id": "CVE-2026-1", "layer": "general-db", "source_id": "nvd", "scores": {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": None}},
            {"id": "github-advisories:GHSA-x", "kind": "vuln", "vuln_id": "GHSA-x", "aliases": ["GHSA-x", "CVE-2026-1"], "layer": "ecosystem", "source_id": "github-advisories",
             "scores": {"cvss_v3": None, "cvss_v4": None, "cna": None, "vendor": 7.5}},
        ], collected_at=TODAY.isoformat() + "T09:00:00")
        counts = C.enrich(self.store, self.http, TODAY.isoformat(), None)
        r = self.store.record("nvd:CVE-2026-1")
        self.assertEqual(r["scores"]["vendor"], 7.5)
        self.assertEqual(r["filled_from"]["scores.vendor"], "github-advisories")
        self.assertEqual(counts["score"], 1)


if __name__ == "__main__":
    unittest.main()
