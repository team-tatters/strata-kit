"""Session-start header shows when the vault is out of step (MB-strata-kit-2026-008): unpushed or unpulled commits,
uncommitted files the remote also changed, and uncommitted files left for hours."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402


def git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, check=True).stdout


class VaultSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(self.origin)], check=True)
        self.a, self.b = root / "a", root / "b"
        for c in (self.a, self.b):
            subprocess.run(["git", "clone", "--quiet", str(self.origin), str(c)], check=True, capture_output=True)
            git(c, "config", "user.email", "t@t"); git(c, "config", "user.name", "t")
        (self.a / "index.json").write_text("{}\n"); (self.a / "note.md").write_text("n\n")
        git(self.a, "add", "."); git(self.a, "commit", "--quiet", "-m", "init"); git(self.a, "push", "--quiet", "origin", "HEAD:main")
        git(self.a, "branch", "--set-upstream-to=origin/main")
        git(self.b, "pull", "--quiet", "origin", "main"); git(self.b, "branch", "--set-upstream-to=origin/main")

    def tearDown(self):
        self.tmp.cleanup()

    def test_in_step_vault_says_nothing(self):
        self.assertIsNone(wizard.vault_sync(self.a))

    def test_diverged_with_overlapping_and_stale_uncommitted(self):
        (self.b / "index.json").write_text('{"b": 1}\n'); git(self.b, "commit", "--quiet", "-am", "b"); git(self.b, "push", "--quiet")
        (self.a / "mine.md").write_text("m\n"); git(self.a, "add", "mine.md"); git(self.a, "commit", "--quiet", "-m", "a")
        (self.a / "index.json").write_text('{"a": 1}\n')                      # uncommitted, remote changed it too
        (self.a / "note.md").write_text("old edit\n")
        old = time.time() - 7 * 3600; os.utime(self.a / "note.md", (old, old))  # uncommitted for 7 hours
        git(self.a, "fetch", "--quiet")
        line = wizard.vault_sync(self.a)
        self.assertIn("ahead 1 · behind 1", line)
        self.assertIn("uncommitted the remote also changed 1 (index.json)", line)
        self.assertIn("uncommitted for over 6h 1 (note.md)", line)

    def test_not_a_repo_or_no_upstream(self):
        self.assertIsNone(wizard.vault_sync(Path(self.tmp.name)))
        self.assertIsNone(wizard.vault_sync(None))


if __name__ == "__main__":
    unittest.main()
