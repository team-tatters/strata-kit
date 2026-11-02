"""Document parity in tools/i18n_check.py (order 2026.10.29-09): subfolders and profile docs are checked, pending
entries may be relative paths, and a Korean-only document with no canonical en is reported."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import i18n_check  # noqa: E402


def w(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class DocParityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def all_locales(self, rel: str):
        for loc in i18n_check.LOCALES:
            w(self.root / rel.replace("/en/", f"/{loc}/"))

    def test_subfolder_and_profile_docs_need_siblings(self):
        self.all_locales("core/docs/en/kb.md")
        w(self.root / "core/docs/en/architecture/a.md")
        w(self.root / "core/docs/ko/architecture/a.md")
        w(self.root / "profiles/p.x/docs/en/b.md")
        errors, warnings = i18n_check.doc_parity(self.root, {})
        self.assertIn("profiles/p.x/docs/ko/b.md: missing (mark in i18n/pending.yaml or translate)", errors)
        self.assertIn("core/docs/ja/architecture/a.md: missing (mark in i18n/pending.yaml or translate)", warnings)
        self.assertFalse([m for m in errors + warnings if "kb.md" in m])

    def test_pending_accepts_relative_paths_and_bare_names(self):
        w(self.root / "core/docs/en/architecture/a.md")
        w(self.root / "core/docs/ko/architecture/a.md")
        w(self.root / "core/docs/en/kb.md")
        w(self.root / "core/docs/ko/kb.md")
        pending = {loc: ["architecture/a.md", "kb.md"] for loc in ("ja", "zh", "es", "fr")}
        self.assertEqual(i18n_check.doc_parity(self.root, pending), ([], []))

    def test_korean_only_document_is_reported(self):
        w(self.root / "profiles/p.x/docs/ko/c.md")
        errors, warnings = i18n_check.doc_parity(self.root, {})
        self.assertEqual(errors, [])
        self.assertIn("profiles/p.x/docs/ko/c.md: no canonical en (profiles/p.x/docs/en/c.md)", warnings)


if __name__ == "__main__":
    unittest.main()
