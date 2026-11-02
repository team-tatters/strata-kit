"""Vault templates live in the kit (order 2026.10.29-11, DEC-2026-10-29-11): the body-section fallbacks read
core/templates/vault/_meta/taxonomy.yaml, not $STRATA_ROOT."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.legacy import kb_sections  # noqa: E402
from kb.views import node_pages  # noqa: E402


class KitTemplateFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "_meta").mkdir()
        (self.vault / "_meta" / "taxonomy.yaml").write_text("version: '1'\ndocument_types: {}\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_sections_fall_back_to_kit_template(self):
        self.assertIn("완료", kb_sections.body_sections("session", vault=str(self.vault)))

    def test_node_sections_fall_back_to_kit_template(self):
        self.assertEqual(len(node_pages.body_sections(self.vault)), 6)

    def test_no_strata_root_parameter(self):
        import inspect
        self.assertNotIn("strata_root", inspect.signature(kb_sections.body_sections).parameters)
        self.assertNotIn("strata_root", inspect.signature(node_pages.body_sections).parameters)


if __name__ == "__main__":
    unittest.main()
