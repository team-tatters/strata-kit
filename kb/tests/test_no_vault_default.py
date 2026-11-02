"""No guessed vault (MB-strata-kit-2026-048): without STRATA_VAULT the link check, the order claim and the decision-note
generator stop with a message, and the vault sync does nothing — none of them falls back to ~/workspace/vault."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]


class NoVaultDefaultTest(unittest.TestCase):
    def setUp(self):
        self.env = {k: v for k, v in os.environ.items() if k != "STRATA_VAULT"}

    def run_kb(self, *args):
        return subprocess.run([sys.executable, str(KIT / "kb"), *args], cwd=KIT, env=self.env, capture_output=True, text=True)

    def test_link_check_refuses(self):
        r = self.run_kb("link-check", "--project", "demo")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STRATA_VAULT", r.stderr)

    def test_order_claim_refuses(self):
        r = self.run_kb("order", "show", "2026.01.01-01", "--no-sync")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("STRATA_VAULT", r.stdout + r.stderr)

    def test_decision_notes_refuse(self):
        r = self.run_kb("gen-decision-notes", "--project-dir", str(KIT))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STRATA_VAULT", r.stderr)

    def test_vault_sync_does_nothing(self):
        r = subprocess.run(["sh", str(KIT / "kb" / "legacy" / "vault_git.sh"), "pull"], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("STRATA_VAULT", r.stderr)


if __name__ == "__main__":
    unittest.main()
