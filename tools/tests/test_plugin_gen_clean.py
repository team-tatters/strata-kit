"""Adapters are generated from a clean tree (audit 2026-11-05): the Claude plugin and the Codex bundle refuse a dirty
working tree unless --allow-dirty, so the stamped core_revision names a commit; doctor says when the installed
Claude plugin's core revision lags the kit HEAD."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(KIT))

import doctor  # noqa: E402
import gen_claude_plugin  # noqa: E402
import gen_codex_bundle  # noqa: E402


def git(repo: Path, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


class CleanTreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "kit"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_tree_stamps_the_commit(self):
        for gen in (gen_claude_plugin, gen_codex_bundle):
            self.assertEqual(gen.stamp_revision(False, kit=self.repo), git(self.repo, "rev-parse", "--short=12", "HEAD"))

    def test_dirty_tree_is_refused_unless_allowed(self):
        (self.repo / "a.txt").write_text("b\n")
        for gen in (gen_claude_plugin, gen_codex_bundle):
            with self.assertRaises(SystemExit) as cm:
                gen.stamp_revision(False, kit=self.repo)
            self.assertIn("a.txt", str(cm.exception.code))
            self.assertIn("--allow-dirty", str(cm.exception.code))
            self.assertTrue(gen.stamp_revision(True, kit=self.repo).endswith("+dirty"))

    def test_cli_has_allow_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            for script in ("gen_claude_plugin.py", "gen_codex_bundle.py"):
                r = subprocess.run([sys.executable, str(KIT / "tools" / script), "--allow-dirty", "--out", str(Path(d) / script / "strata-kit")],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


class InstalledPluginLagTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.install = root / "cache" / "strata-kit" / "0.1.9"
        self.install.mkdir(parents=True)
        self.registry = root / "installed_plugins.json"
        self.registry.write_text(json.dumps({"plugins": {"strata-kit@strata-kit": [{"installPath": str(self.install), "version": "0.1.9"}]}}))

    def tearDown(self):
        self.tmp.cleanup()

    def stamp(self, rev: str):
        (self.install / "README.md").write_text(f"<!-- strata-kit adapter | core_revision: {rev} | locale: ko | 2026-11-05 -->\n# x\n")

    def test_lagging_install_is_reported(self):
        old = subprocess.run(["git", "-C", str(KIT), "rev-list", "-n1", "HEAD~3"], capture_output=True, text=True).stdout.strip()[:12]
        if not old:
            self.skipTest("kit checkout has fewer than four commits")
        self.stamp(old)
        (i,) = doctor.check_plugin_lag(self.registry)
        self.assertTrue(i.machine)
        self.assertIn(old, i.evidence)
        self.assertIn("커밋 뒤", i.message)
        self.assertIn("gen_claude_plugin.py", i.fix)

    def test_dirty_stamp_is_reported_and_head_is_quiet(self):
        head = subprocess.run(["git", "-C", str(KIT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.stamp(head)
        self.assertEqual(doctor.check_plugin_lag(self.registry), [])
        self.stamp(head + "+dirty")
        (i,) = doctor.check_plugin_lag(self.registry)
        self.assertIn("더러운 작업 트리", i.message)

    def test_no_install_is_quiet(self):
        self.assertEqual(doctor.check_plugin_lag(Path(self.tmp.name) / "none.json"), [])


if __name__ == "__main__":
    unittest.main()
