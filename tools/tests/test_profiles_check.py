"""Profile manifests against core/schemas/profile.schema.yaml (order 2026.10.29-11): tools/cards_check.py reports a
profile whose id differs from its folder, an unknown detect key, an unknown default card or a missing source path."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]


class ProfilesCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "core" / "cards").mkdir(parents=True)
        (self.root / "core" / "constitution").mkdir(parents=True)
        (self.root / "core" / "constitution" / "constitution.yaml").write_text("constitution:\n  version: '1'\n  ratified: 2026-10-29\n  last_amended: 2026-10-29\n  articles: []\n", encoding="utf-8")
        (self.root / "docs.md").write_text("x\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def profile(self, folder: str, body: str):
        p = self.root / "profiles" / folder / "profile.yaml"
        p.parent.mkdir(parents=True)
        p.write_text(body, encoding="utf-8")

    def check(self):
        return subprocess.run([sys.executable, str(KIT / "tools" / "cards_check.py"), "--root", str(self.root)], capture_output=True, text=True)

    GOOD = ("profile:\n  id: {id}\n  title: {{en: T, ko: T}}\n  status: draft\n  detect: {{any_files: [x.toml]}}\n  layers: a → b\n"
            "  enforcement: []\n  cards_default: []\n  cards_excluded: []\n  source: docs.md\n  note: {{en: n, ko: n}}\n")

    def test_good_profile_passes(self):
        self.profile("lang.good", self.GOOD.format(id="lang.good"))
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("1 profiles", r.stdout)

    def test_errors_are_reported(self):
        bad = self.GOOD.format(id="lang.other").replace("any_files", "any_file").replace("cards_default: []", "cards_default: [rec.none.here]").replace("source: docs.md", "source: missing.md")
        self.profile("lang.bad", bad)
        r = self.check()
        self.assertEqual(r.returncode, 2)
        for needle in ("folder", "any_file", "rec.none.here", "missing.md"):
            self.assertIn(needle, r.stdout)


if __name__ == "__main__":
    unittest.main()
