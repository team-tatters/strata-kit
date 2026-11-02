"""Public projection (DEC-2026-11-02-07): only included, non-excluded tracked files at a revision are projected, map
places public-only files, a deny pattern anywhere (text or path) fails the build, allow lists exempt named files,
the output keeps its .git and nothing else, and the working tree can be scanned but never built."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import project_public as pp  # noqa: E402

MANIFEST = """include: ["core/**", "LOCALES.md"]
exclude: ["core/private/**"]
map: {public/README.md: README.md}
deny:
  - {pattern: 'acme[-_]internal', why: "client"}
  - {pattern: '\\bbob\\b', why: "author", allow: ["README.md"]}
"""


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)


class ProjectPublicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name).resolve()
        self.repo, self.out = r / "dev", r / "pub"
        files = {"public/projection.yaml": MANIFEST, "public/README.md": "by bob\n", "LOCALES.md": "en\n",
                 "core/a.md": "clean\n", "core/private/secret.md": "acme-internal plan\n", "notes.md": "acme_internal\n"}
        for rel, text in files.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True); (self.repo / rel).write_text(text)
        git(self.repo, "init", "-q"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-q", "-m", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        return pp.main(["--repo", str(self.repo), *args])

    def test_plan_includes_maps_and_excludes(self):
        _, pairs = pp.plan(self.repo)
        self.assertEqual(sorted(d for _, d in pairs), ["LOCALES.md", "README.md", "core/a.md"])   # private, notes.md, public/ out

    def test_clean_build_writes_only_the_projection_and_keeps_git(self):
        (self.out / ".git").mkdir(parents=True); (self.out / ".git" / "HEAD").write_text("x")
        (self.out / "stale.md").write_text("old")
        self.assertEqual(self.run_main("build", "--out", str(self.out)), 0)
        got = sorted(str(p.relative_to(self.out)) for p in self.out.rglob("*") if p.is_file())
        self.assertEqual(got, [".git/HEAD", ".strata-projection.yaml", "LOCALES.md", "README.md", "core/a.md"])
        self.assertIn("source_revision:", (self.out / ".strata-projection.yaml").read_text())

    def test_a_deny_hit_refuses_the_build(self):
        (self.repo / "core" / "b.md").write_text("ask acme-internal\n")
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-q", "-m", "leak")
        self.assertEqual(self.run_main("build", "--out", str(self.out)), 1)
        self.assertFalse(self.out.exists())
        m, pairs = pp.plan(self.repo)
        hits = pp.scan(self.repo, "HEAD", m, pairs)
        self.assertEqual([(h["file"], h["line"]) for h in hits], [("core/b.md", 1)])   # README's "bob" is allowed
        self.assertEqual(pp.load_manifest(self.repo, "HEAD")["deny"][1]["pattern"], r"\bbob\b")   # a word boundary, not a backslash

    def test_a_denied_word_in_a_path_is_a_hit(self):
        (self.repo / "core" / "acme_internal.md").write_text("ok\n")
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-q", "-m", "path")
        m, pairs = pp.plan(self.repo)
        self.assertEqual([(h["file"], h["line"]) for h in pp.scan(self.repo, "HEAD", m, pairs)], [("core/acme_internal.md", 0)])

    def test_worktree_is_scanned_but_not_built(self):
        (self.repo / "core" / "draft.md").write_text("bob wrote this\n")       # untracked, in the working tree only
        self.assertEqual(self.run_main("scan", "--rev", "WORKTREE"), 1)
        self.assertEqual(self.run_main("scan"), 0)                              # HEAD does not have it
        with self.assertRaises(SystemExit):
            self.run_main("build", "--rev", "WORKTREE", "--out", str(self.out))

    def test_output_inside_the_repository_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_main("build", "--out", str(self.repo / "dist" / "pub"))


if __name__ == "__main__":
    unittest.main()
