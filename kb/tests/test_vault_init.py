"""kb vault-init (MB-strata-kit-2026-048): a starter vault from core/templates/vault that the engine can read at once —
the store builds and the hygiene report runs on it — and a second run overwrites nothing."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kb import vault_init

KIT = Path(__file__).resolve().parents[2]


class VaultInitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vault"

    def tearDown(self):
        self.tmp.cleanup()

    def test_layout_follows_the_onboarding_procedure(self):
        made, kept = vault_init.init(self.root, "demo", detached=True, today="2026-11-02")
        self.assertEqual(kept, [])
        for rel in ("_meta/taxonomy.yaml", "env-config.yaml", "_index/projects.md", ".gitignore",
                    "projects/demo/overview.md", "projects/demo/_meta/taxonomy.yaml", "projects/demo/_meta/toc.yaml",
                    "projects/demo/knowledge-base/domain/_index.md", "projects/demo/sessions", "projects/demo/tasks",
                    "projects/demo/strata/profile.yaml"):
            self.assertTrue((self.root / rel).exists(), rel)
        self.assertIn("type: overview", (self.root / "projects/demo/overview.md").read_text())
        import yaml
        env = yaml.safe_load((self.root / "env-config.yaml").read_text())          # placeholders filled: valid YAML
        (alias,) = env["environments"]
        self.assertNotIn("{{", (self.root / "env-config.yaml").read_text())
        self.assertEqual(env["environments"][alias]["last_active"].isoformat(), "2026-11-02")
        self.assertRegex(env["environments"][alias]["fingerprint"], r"^([0-9a-f]{12})?$")   # a hash, never the raw id

    def test_second_run_keeps_everything(self):
        vault_init.init(self.root, "demo")
        (self.root / "projects/demo/overview.md").write_text("mine\n")
        made, kept = vault_init.init(self.root, "demo")
        self.assertEqual(made, [])
        self.assertEqual((self.root / "projects/demo/overview.md").read_text(), "mine\n")

    def test_the_engine_reads_it(self):
        vault_init.init(self.root, "demo")
        env = {**os.environ, "STRATA_VAULT": str(self.root)}
        for args in (["build-store"], ["hygiene", "--project", "demo"]):
            r = subprocess.run([sys.executable, str(KIT / "kb"), *args], cwd=self.tmp.name, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{args}: {r.stdout[-400:]} {r.stderr[-400:]}")

    def test_bad_project_name_is_refused(self):
        with self.assertRaises(SystemExit):
            vault_init.main([str(self.root), "--project", "My Project"])


if __name__ == "__main__":
    unittest.main()
