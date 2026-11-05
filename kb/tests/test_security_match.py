"""Security core, order 2026.11.03-02 task-02 (spec AC3, Tech Spec G3): a library at a vulnerable version matches by purl
and range (and stays as out-of-range when fixed), a Debian package matches a notice by codename/package and installed
version, a target without an identifier matches its manual link's advisories by range text and its newer releases as
new posts, macOS matches the newest security release of its major line, a target with neither identifier nor link is
a blind target, an unparsable version is kept as unknown, and the version comparator orders deb and dotted versions."""
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.security import match as M  # noqa: E402
from kb.security.sources import record  # noqa: E402
from kb.security.versions import deb_cmp, dotted_cmp, in_range  # noqa: E402

DAY = "2026-11-03"


def item(name, version, kind, identifier="none", source="none", env="dev", project="demo", **extra):
    return {"name": name, "version": version, "kind": kind, "identifier": identifier, "source": source, "environment": env, "project": project,
            "target_ref": f"{project}/{env}/{name}", **extra}


RECORDS = [
    record("osv:GHSA-1", "vuln", "ecosystem", "osv", vuln_id="CVE-2020-1747", affected=[{"kind": "purl", "identifier": "pkg:pypi/pyyaml", "ecosystem": "PyPI", "introduced": "5.1b7", "fixed": "5.3.1"}]),
    record("ubuntu-usn:USN-1", "vuln", "os-vendor", "ubuntu-usn", vuln_id="USN-1", affected=[{"kind": "deb", "identifier": "noble/curl", "fixed": "8.5.0-2ubuntu10.17", "codename": "noble"}]),
    record("github-advisories:GHSA-t", "vuln", "ecosystem", "github-advisories", vuln_id="GHSA-t", affected=[{"kind": "repo", "identifier": "traefik/traefik", "range_text": ">= 3.0.0, < 3.7.17", "fixed": "v3.7.17"}]),
    record("github-releases:traefik/traefik:v3.7.17", "release", "os-vendor", "github-releases", version="v3.7.17", published="2026-10-30", security_mentioned=True, affected=[{"kind": "repo", "identifier": "traefik/traefik"}]),
    record("apple:macOS-Tahoe-26.7.2", "release", "os-vendor", "apple-security-releases", version="26.7.2", published="2026-10-26", affected=[{"kind": "product", "identifier": "macOS Tahoe"}]),
    record("apple:macOS-Golden-Gate-27.2", "release", "os-vendor", "apple-security-releases", version="27.2", published="2026-10-26", affected=[{"kind": "product", "identifier": "macOS Golden Gate"}]),
    record("msrc:2026-Oct", "post", "os-vendor", "msrc", version="2026-Oct", published="2026-10-14", affected=[{"kind": "product", "identifier": "Windows"}]),
]
LINKS = {"demo/dev/traefik": "github-releases:traefik/traefik"}


class VersionsTest(unittest.TestCase):
    def test_deb_and_dotted_and_range(self):
        self.assertLess(deb_cmp("1:1.3.dfsg-3.1ubuntu2.3", "1:1.3.dfsg-3.1ubuntu2.4"), 0)
        self.assertLess(deb_cmp("1.0~rc1", "1.0"), 0)
        self.assertEqual(deb_cmp("2.8.3", "2.8.3"), 0)
        self.assertGreater(dotted_cmp("v3.7.17", "3.7.16"), 0)
        self.assertLess(dotted_cmp("5.1b7", "5.1"), 0)
        self.assertIsNone(dotted_cmp("sha256:abc", "1.0"))
        self.assertTrue(in_range("5.3", "5.1b7", "5.3.1"))
        self.assertFalse(in_range("6.0.3", "5.1b7", "5.3.1"))
        self.assertTrue(in_range("8.5.0-2ubuntu10.16", None, "8.5.0-2ubuntu10.17", scheme="deb"))
        self.assertTrue(M.range_text_holds("3.7.16", ">= 3.0.0, < 3.7.17"))
        self.assertFalse(M.range_text_holds("v3.7.17", ">= 3.0.0, < 3.7.17"))
        self.assertIsNone(M.range_text_holds("3.7.17", "all versions"))


class MatchTest(unittest.TestCase):
    def run_items(self, items):
        return M.match_items(items, RECORDS, LINKS, DAY, since="2026-10-01")

    def find(self, res, target, vuln=None):
        return [m for m in res["matches"] if m["target_ref"].endswith(target) and (vuln is None or m["vuln_id"] == vuln)]

    def test_library_vulnerable_version_matches_and_fixed_version_is_out_of_range(self):
        res = self.run_items([item("pyyaml", "5.3", "library", "pkg:pypi/pyyaml@5.3", "osv"), item("pyyaml2", "6.0.3", "library", "pkg:pypi/pyyaml@6.0.3", "osv")])
        a = self.find(res, "/pyyaml", "CVE-2020-1747")
        self.assertEqual((len(a), a[0]["matched_by"], a[0]["version_in_range"]), (1, "identifier", True))
        b = self.find(res, "/pyyaml2", "CVE-2020-1747")
        self.assertEqual((len(b), b[0]["version_in_range"]), (1, False))
        self.assertEqual(res["blind_targets"], [])

    def test_two_versions_of_one_target_keep_both_versions_on_the_single_match(self):
        # lockfile with next 15.2.6 (apps) and 15.2.4 (packages): one id per target, both versions shown (2026-11-04 note said only 15.2.4)
        res = self.run_items([item("pyyaml", "5.2", "library", "pkg:pypi/pyyaml@5.2", "osv"), item("pyyaml", "5.3", "library", "pkg:pypi/pyyaml@5.3", "osv"),
                              item("pyyaml", "6.0", "library", "pkg:pypi/pyyaml@6.0", "osv")])
        a = self.find(res, "/pyyaml", "CVE-2020-1747")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["detail"]["target_versions"], {"5.2": True, "5.3": True, "6.0": False})
        self.assertTrue(a[0]["version_in_range"])

    def test_debian_package_behind_notice(self):
        res = self.run_items([item("curl", "8.5.0-2ubuntu10.16", "package", "pkg:deb/ubuntu/curl@8.5.0-2ubuntu10.16?distro=noble", "ubuntu-usn", codename="noble"),
                              item("wget", "1.21.4-1ubuntu4.5", "package", "pkg:deb/ubuntu/wget@1.21.4-1ubuntu4.5?distro=noble", "ubuntu-usn", codename="noble")])
        a = self.find(res, "/curl", "USN-1")
        self.assertEqual((len(a), a[0]["version_in_range"], a[0]["detail"]["fixed"]), (1, True, "8.5.0-2ubuntu10.17"))
        self.assertEqual(self.find(res, "/wget"), [])

    def test_manual_link_advisory_range_and_newer_release_as_new_post(self):
        res = self.run_items([item("traefik", "v3.7.16", "image", source="github-releases:traefik/traefik")])
        adv = self.find(res, "/traefik", "GHSA-t")
        self.assertEqual((adv[0]["matched_by"], adv[0]["version_in_range"]), ("manual-link", True))
        rel = self.find(res, "/traefik", "github-releases:traefik/traefik:v3.7.17")
        self.assertTrue(rel and rel[0]["detail"]["new_post"] and rel[0]["version_in_range"] is True)
        res2 = self.run_items([item("traefik", "v3.7.17", "image", source="github-releases:traefik/traefik")])
        self.assertFalse(self.find(res2, "/traefik", "GHSA-t")[0]["version_in_range"])
        self.assertFalse(self.find(res2, "/traefik", "github-releases:traefik/traefik:v3.7.17")[0]["version_in_range"])

    def test_macos_version_line_windows_notice_and_blind_target(self):
        res = self.run_items([item("macOS", "26.6.2 (25G83)", "os", source="apple-security-releases", device="a"),
                              item("macOS", "27.2 (26B123)", "os", source="apple-security-releases", device="b", env="desk2"),
                              item("Windows", "11 25H2", "os", source="msrc", device="c"),
                              item("redis", "7-alpine", "image"),
                              item("api", "dev", "image", source="internal-build")])
        mac = [m for m in res["matches"] if m["matched_by"] == "version-line"]
        self.assertEqual(len(mac), 2)
        by = {m["target_ref"]: m for m in mac}
        self.assertTrue(by["demo/dev/macOS"]["version_in_range"])
        self.assertEqual(by["demo/dev/macOS"]["detail"]["latest"], "26.7.2")
        self.assertFalse(by["demo/desk2/macOS"]["version_in_range"])
        win = [m for m in res["matches"] if m["matched_by"] == "vendor-notice"]
        self.assertEqual((len(win), win[0]["version_in_range"]), (1, None))
        self.assertEqual([b["target_ref"] for b in res["blind_targets"]], ["demo/dev/redis"])

    def test_old_installed_kernel_package_is_marked_not_running(self):
        recs = RECORDS + [record("ubuntu-usn:USN-K", "vuln", "os-vendor", "ubuntu-usn", vuln_id="USN-K",
                                 affected=[{"kind": "deb", "identifier": "noble/linux-image-6.8.0-100-generic", "fixed": "6.8.0-100.101", "codename": "noble"},
                                           {"kind": "deb", "identifier": "noble/linux-image-6.8.0-137-generic", "fixed": "6.8.0-137.138", "codename": "noble"}])]
        items = [item("ubuntu", "24.04", "os", source="ubuntu-usn", kernel="6.8.0-137-generic"),
                 item("linux-image-6.8.0-100-generic", "6.8.0-100.100", "package", "pkg:deb/ubuntu/linux-image-6.8.0-100-generic@6.8.0-100.100?distro=noble", "ubuntu-usn", codename="noble"),
                 item("linux-image-6.8.0-137-generic", "6.8.0-137.137", "package", "pkg:deb/ubuntu/linux-image-6.8.0-137-generic@6.8.0-137.137?distro=noble", "ubuntu-usn", codename="noble")]
        res = M.match_items(items, recs, {}, DAY)
        by = {x["target_ref"].split("/")[-1]: x for x in res["matches"]}
        self.assertTrue(by["linux-image-6.8.0-100-generic"]["detail"].get("not_running"))
        self.assertNotIn("not_running", by["linux-image-6.8.0-137-generic"]["detail"])

    def test_unparsable_version_is_kept_as_unknown(self):
        recs = RECORDS + [record("osv:X", "vuln", "ecosystem", "osv", vuln_id="CVE-X", affected=[{"kind": "purl", "identifier": "pkg:npm/left-pad", "ecosystem": "npm", "introduced": "0", "fixed": "1.3.0"}])]
        res = M.match_items([item("left-pad", "git+https://x", "library", "pkg:npm/left-pad@git+https://x", "osv")], recs, {}, DAY)
        self.assertIsNone(res["matches"][0]["version_in_range"])


if __name__ == "__main__":
    unittest.main()


class MultiRangeTest(unittest.TestCase):
    """2026-11-04: an advisory with several affected ranges (next 10.0.0–15.5.24 and 16.0.0–16.3.3) must stay in range for a
    15.x target — the later out-of-range block must not overwrite the earlier in-range one; two versions of one package
    under the same target keep the in-range result."""

    REC = record("osv:GHSA-next", "vuln", "ecosystem", "osv", vuln_id="GHSA-next", affected=[
        {"kind": "purl", "identifier": "pkg:npm/next", "ecosystem": "npm", "introduced": "10.0.0", "fixed": "15.5.24"},
        {"kind": "purl", "identifier": "pkg:npm/next", "ecosystem": "npm", "introduced": "16.0.0", "fixed": "16.3.3"}])

    def test_earlier_range_wins(self):
        out = M.match_items([item("next", "15.2.6", "library", identifier="pkg:npm/next@15.2.6", source="osv")], [self.REC], {}, DAY)["matches"]
        self.assertEqual([m["version_in_range"] for m in out], [True])

    def test_two_versions_same_target(self):
        its = [item("next", "15.2.6", "library", identifier="pkg:npm/next@15.2.6", source="osv"),
               item("next", "16.4.0", "library", identifier="pkg:npm/next@16.4.0", source="osv")]
        out = M.match_items(its, [self.REC], {}, DAY)["matches"]
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["version_in_range"])

    def test_fixed_version_stays_out(self):
        out = M.match_items([item("next", "15.5.28", "library", identifier="pkg:npm/next@15.5.28", source="osv")], [self.REC], {}, DAY)["matches"]
        self.assertEqual([m["version_in_range"] for m in out], [False])
