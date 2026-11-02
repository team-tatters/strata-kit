"""vault_git.sh commit-push commits only the listed paths (DEC-2026-10-29-04): files another session staged stay
staged and uncommitted, and an exclude pathspec keeps generated node pages out of a session's commit."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "legacy" / "vault_git.sh"


def git(cwd: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, check=True).stdout


class CommitPushTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        origin, self.vault = root / "origin.git", root / "vault"
        subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "clone", "--quiet", str(origin), str(self.vault)], check=True, capture_output=True)
        git(self.vault, "config", "user.email", "t@t"); git(self.vault, "config", "user.name", "t")
        for rel in ("projects/p/sessions/s.md", "projects/p/nodes/n.md", "other/x.md", "_index/review-needed.md"):
            (self.vault / rel).parent.mkdir(parents=True, exist_ok=True); (self.vault / rel).write_text("0\n")
        git(self.vault, "add", "."); git(self.vault, "commit", "--quiet", "-m", "init"); git(self.vault, "push", "--quiet", "origin", "HEAD:main")
        git(self.vault, "branch", "--set-upstream-to=origin/main")

    def tearDown(self):
        self.tmp.cleanup()

    def run_push(self, *paths: str) -> None:
        env = {**os.environ, "STRATA_VAULT": str(self.vault)}
        subprocess.run(["sh", str(SCRIPT), "commit-push", "msg", *paths], env=env, capture_output=True, check=True)

    def test_only_listed_paths_and_excludes(self):
        for rel in ("projects/p/sessions/s.md", "projects/p/nodes/n.md", "other/x.md"):
            (self.vault / rel).write_text("1\n")
        git(self.vault, "add", "other/x.md")                                   # another session staged this
        self.run_push("projects/p", ":(exclude)projects/p/nodes")
        committed = git(self.vault, "show", "--name-only", "--format=", "HEAD").split()
        self.assertEqual(committed, ["projects/p/sessions/s.md"])
        status = git(self.vault, "status", "--porcelain")
        self.assertIn("M  other/x.md", status)                                 # still staged, not committed
        self.assertIn(" M projects/p/nodes/n.md", status)                      # generated page left for librarian

    def test_views_publish_paths_take_only_node_pages(self):
        for rel in ("projects/p/sessions/s.md", "projects/p/nodes/n.md"):
            (self.vault / rel).write_text("2\n")
        self.run_push(":(glob)projects/*/nodes/**", "_index/review-needed.md")  # the paths kb views-publish passes
        self.assertEqual(git(self.vault, "show", "--name-only", "--format=", "HEAD").split(), ["projects/p/nodes/n.md"])


if __name__ == "__main__":
    unittest.main()
