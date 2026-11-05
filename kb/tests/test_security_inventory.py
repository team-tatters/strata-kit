"""Security core, order 2026.11.03-01 task-02 (spec AC1, DEC-2026-11-03-05): the inventory generator — every item carries
the six G1 values (name, version, environment, kind, source, identifier-or-none); lockfile generators for pnpm, npm, uv
and go.sum emit purls; the compose generator takes image tags or digests and binds a manual link as the source, leaving
unlinked images as blind candidates; the manual generator only validates a hand-written file (nested devices or flat
items) and reports placeholders; two runs give an empty diff and a version change gives one changed line; the CLI
writes only with --write and exits 1 when the inventory differs from the file."""
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))
FIX = KIT / "kb" / "tests" / "fixtures" / "security"

from kb.security import inventory as I  # noqa: E402
from kb.security.generators import compose as C, lockfile as L, manual as M  # noqa: E402

SIX = ("name", "version", "environment", "kind", "source", "identifier")


def by_name(items):
    return {i["name"]: i for i in items}


class GeneratorsTest(unittest.TestCase):
    def test_pnpm_lock_items_have_six_values_and_npm_purls(self):
        items = L.generate([FIX / "pnpm-lock.yaml"], "npm", "repo")
        self.assertEqual({i["name"] for i in items}, {"react", "@tanstack/react-query", "@tanstack/query-core", "loose-envify"})
        for i in items:
            for k in SIX:
                self.assertIn(k, i, i)
        n = by_name(items)
        self.assertEqual(n["react"]["identifier"], "pkg:npm/react@18.3.1")
        self.assertEqual(n["@tanstack/react-query"]["identifier"], "pkg:npm/%40tanstack/react-query@5.59.0")
        self.assertEqual(n["react"]["depth"], "direct")
        self.assertEqual(n["loose-envify"]["depth"], "transitive")
        self.assertEqual(n["react"]["kind"], "library")
        self.assertEqual(n["react"]["source"], "osv")

    def test_package_lock_nested_names_and_direct_marking(self):
        items = L.generate([FIX / "package-lock.json"], "npm", "repo")
        n = by_name(items)
        self.assertEqual(set(n), {"vue", "vite", "esbuild"})
        self.assertEqual(n["esbuild"]["version"], "0.21.5")
        self.assertEqual(n["vite"]["depth"], "direct")
        self.assertEqual(n["esbuild"]["depth"], "transitive")

    def test_uv_lock_skips_root_and_emits_pypi_purls(self):
        items = L.generate([FIX / "uv.lock"], "pypi", "repo")
        n = by_name(items)
        self.assertEqual(set(n), {"pyyaml", "markdown-it-py"})
        self.assertEqual(n["pyyaml"]["identifier"], "pkg:pypi/pyyaml@6.0.2")
        self.assertEqual(n["pyyaml"]["depth"], "direct")
        self.assertEqual(n["markdown-it-py"]["depth"], "transitive")

    def test_go_sum_dedupes_go_mod_lines(self):
        items = L.generate([FIX / "go.sum"], "golang", "repo")
        n = by_name(items)
        self.assertEqual(set(n), {"github.com/gorilla/websocket", "golang.org/x/crypto"})
        self.assertEqual(n["golang.org/x/crypto"]["identifier"], "pkg:golang/golang.org/x/crypto@v0.28.0")
        self.assertEqual(n["golang.org/x/crypto"]["depth"], "unknown")

    def test_sbom_reader_takes_purl_or_builds_maven_purl(self):
        items = L.generate([FIX / "sbom.cdx.json"], "maven", "repo")
        n = by_name(items)
        self.assertEqual(n["spring-core"]["identifier"], "pkg:maven/org.springframework/spring-core@6.1.14")
        self.assertEqual(n["jackson-databind"]["identifier"], "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.17.2")

    def test_compose_images_tags_digests_links_and_blind_candidates(self):
        links = {"infra/dev-server/traefik": "github-releases:traefik/traefik", "infra/dev-server/portainer": "github-releases:portainer/portainer"}
        items = C.generate([FIX / "compose.yml"], "dev-server", "infra", os_spec={"name": "ubuntu", "version": "24.04"}, manual_links=links)
        n = by_name(items)
        self.assertEqual(n["traefik"]["version"], "v3.7.17")
        self.assertEqual(n["traefik"]["source"], "github-releases:traefik/traefik")
        self.assertFalse(n["traefik"]["blind_candidate"])
        self.assertEqual(n["portainer"]["image"], "portainer/portainer-ce")
        self.assertEqual(n["onyx"]["source"], "none")
        self.assertTrue(n["onyx"]["blind_candidate"])
        self.assertTrue(n["redis"]["version"].startswith("sha256:"))
        self.assertEqual(n["dashboard"]["version"], "latest")
        self.assertTrue(n["dashboard"]["floating_tag"])
        self.assertEqual(n["ubuntu"]["kind"], "os")
        self.assertEqual(n["ubuntu"]["source"], "ubuntu-usn")
        for i in items:
            self.assertEqual(i["environment"], "dev-server")
            for k in SIX:
                self.assertIn(k, i, i)

    def test_compose_internal_prefix_packages_and_reboot_pending(self):
        pk = FIX / "dpkg.txt"
        pk.write_text("# dpkg\ncurl 8.5.0-2ubuntu10.16\nlinux-image-generic 6.8.0-147.147\n", encoding="utf-8")
        try:
            items = C.generate([FIX / "compose.yml"], "dev-server", "infra", os_spec={"name": "ubuntu", "version": "24.04", "codename": "noble", "kernel": "6.8.0-137-generic", "installed_kernel": "6.8.0-147-generic"},
                               manual_links={}, internal_prefixes=["ghcr.io/acme/"], packages=pk)
        finally:
            pk.unlink()
        n = by_name(items)
        self.assertTrue(n["ubuntu"]["reboot_pending"])
        self.assertEqual(n["ubuntu"]["codename"], "noble")
        self.assertEqual(n["curl"]["kind"], "package")
        self.assertEqual(n["curl"]["identifier"], "pkg:deb/ubuntu/curl@8.5.0-2ubuntu10.16?distro=noble")
        self.assertEqual(n["curl"]["source"], "ubuntu-usn")
        self.assertTrue(n["onyx"]["blind_candidate"])
        items2 = C.generate([FIX / "compose.yml"], "dev-server", "infra", internal_prefixes=["onyxdotapp/"])
        self.assertEqual(by_name(items2)["onyx"]["source"], "internal-build")
        self.assertFalse(by_name(items2)["onyx"]["blind_candidate"])

    def test_manual_validates_nested_devices_and_reports_placeholders(self):
        items, problems = M.load(FIX / "desktop.yaml", "desktop")
        n = by_name(items)
        self.assertEqual(n["macOS"]["kind"], "os")
        self.assertEqual(n["macOS"]["device"], "desk-mac")
        self.assertEqual(n["Docker Desktop"]["source"], "docker-release-notes")
        self.assertEqual(len(problems), 1)
        self.assertIn("node", problems[0])
        self.assertIn("version", problems[0])


class DiffAndCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "security").mkdir(parents=True)
        ws = self.vault.parent
        (ws / "repo").mkdir()
        self.lock = ws / "repo" / "uv.lock"
        self.lock.write_text((FIX / "uv.lock").read_text(encoding="utf-8"), encoding="utf-8")
        (self.vault / "security" / "registry.yaml").write_text(yaml.safe_dump({
            "version": "0.1", "environments": ["repo", "desktop"],
            "targets": [{"project": "demo", "environment": "repo", "kind": "lockfile", "sources": ["{workspace}/repo/uv.lock"], "ecosystem": "pypi"},
                        {"project": "infra", "environment": "desktop", "kind": "manual", "sources": ["projects/infra/security/inventory/desktop.yaml"]}]}), encoding="utf-8")
        (self.vault / "security" / "sources.yaml").write_text("version: '0.1'\nsources: []\nmanual_links: []\n", encoding="utf-8")
        d = self.vault / "projects" / "infra" / "security" / "inventory"
        d.mkdir(parents=True)
        (d / "desktop.yaml").write_text((FIX / "desktop.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        out = StringIO()
        with redirect_stdout(out):
            rc = I.main(list(args) + ["--today", "2026-11-03"])
        return rc, out.getvalue()

    def test_diff_empty_then_version_change(self):
        a = [{"name": "x", "version": "1", "identifier": "pkg:pypi/x@1"}, {"name": "y", "version": "2", "identifier": "pkg:pypi/y@2"}]
        b = [{"name": "x", "version": "1.1", "identifier": "pkg:pypi/x@1.1"}, {"name": "z", "version": "3", "identifier": "pkg:pypi/z@3"}]
        self.assertEqual(I.diff(a, a), {"added": [], "removed": [], "changed": []})
        d = I.diff(a, b)
        self.assertEqual([i["name"] for i in d["added"]], ["z"])
        self.assertEqual([i["name"] for i in d["removed"]], ["y"])
        self.assertEqual(d["changed"], [("x", "1", "1.1")])

    def test_diff_same_package_at_two_versions_is_not_a_false_change(self):
        a = [{"name": "numpy", "version": "1.26", "identifier": "pkg:pypi/numpy@1.26"}, {"name": "numpy", "version": "2.1", "identifier": "pkg:pypi/numpy@2.1"}]
        self.assertEqual(I.diff(a, a), {"added": [], "removed": [], "changed": []})
        b = a[:1] + [{"name": "numpy", "version": "2.2", "identifier": "pkg:pypi/numpy@2.2"}]
        d = I.diff(a, b)
        self.assertEqual(d["changed"], [])
        self.assertEqual([i["version"] for i in d["added"]], ["2.2"])
        self.assertEqual([i["version"] for i in d["removed"]], ["2.1"])

    def test_cli_write_twice_then_change_exits_one_and_file_has_header(self):
        rc, out = self.run_cli("inventory", "--project", "demo", "--env", "repo", "--write")
        self.assertEqual(rc, 1, out)           # first run: the file did not exist, everything is added
        f = self.vault / "projects" / "demo" / "security" / "inventory" / "repo.yaml"
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        self.assertEqual(doc["origin"], "generated")
        self.assertEqual(doc["project"], "demo")
        self.assertEqual(doc["environment"], "repo")
        self.assertEqual(doc["generated_at"], "2026-11-03")
        self.assertTrue(doc["source_ref"][0].endswith("repo/uv.lock"))
        self.assertEqual(len(doc["items"]), 2)
        rc, out = self.run_cli("inventory", "--project", "demo", "--env", "repo")
        self.assertEqual(rc, 0, out)           # second run: no difference
        self.assertIn("차이 없음", out)
        self.lock.write_text(self.lock.read_text(encoding="utf-8").replace('version = "6.0.2"', 'version = "6.0.3"'), encoding="utf-8")
        rc, out = self.run_cli("inventory", "--project", "demo", "--env", "repo")
        self.assertEqual(rc, 1, out)
        self.assertIn("~ pyyaml 6.0.2 → 6.0.3", out)
        self.assertEqual(yaml.safe_load(f.read_text(encoding="utf-8"))["items"][1 if doc["items"][1]["name"] == "pyyaml" else 0]["version"], "6.0.2")  # not written without --write

    def test_cli_manual_target_reports_placeholder_and_exits_one(self):
        rc, out = self.run_cli("inventory", "--project", "infra", "--env", "desktop")
        self.assertEqual(rc, 1, out)
        self.assertIn("node", out)
        rc, out = self.run_cli("inventory", "--all")
        self.assertIn("demo/repo", out)
        self.assertIn("infra/desktop", out)


if __name__ == "__main__":
    unittest.main()
