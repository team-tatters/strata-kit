"""Context around a search hit (MB-strata-kit-2026-056 step 3): a section hit alone is often a fragment; the MCP
search attaches the neighbouring chunks or the enclosing H2 section, within a character budget."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api  # noqa: E402
from kb.store import Chunk, Node, SqliteStore  # noqa: E402


def ch(seq, level, heading, text):
    return Chunk("doc:a", seq, text, heading=heading, meta={"heading_level": level})


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore()
        self.s.put_nodes([Node("doc:a", "doc", path="projects/p/knowledge-base/a.md", title="A", payload={"indexed": True})])
        self.s.put_chunks([ch(0, 0, "(intro)", "머리말"),
                           ch(1, 2, "정책", "정책 개요"),
                           ch(2, 3, "잠금", "확정 후 잠금 needle"),
                           ch(3, 3, "해제", "해제는 주사용자만"),
                           ch(4, 2, "부록", "부록 본문")])

    def hit(self, **kw):
        out = api.search(self.s, "needle", include_content=True, **kw)
        self.assertEqual(len(out), 1)
        return out[0]

    def test_default_attaches_the_neighbouring_chunks(self):
        e = self.hit()
        self.assertEqual(e["context"]["mode"], "neighbors")
        self.assertEqual([c["seq"] for c in e["context"]["chunks"]], [1, 3])
        self.assertEqual(e["context"]["chunks"][0], {"seq": 1, "heading": "정책", "text": "정책 개요"})
        self.assertFalse(e["context"]["truncated"])

    def test_section_mode_returns_the_enclosing_h2_section(self):
        e = self.hit(context="section")
        self.assertEqual(e["context"]["mode"], "section")
        self.assertEqual(e["context"]["section"], "정책")
        self.assertEqual([c["seq"] for c in e["context"]["chunks"]], [1, 3])   # the H2 and its other subsections, not 부록

    def test_budget_bounds_the_attached_text(self):
        self.s.put_chunks([ch(1, 2, "정책", "가" * 500), ch(3, 3, "해제", "나" * 500)])
        e = self.hit(context_chars=300)
        self.assertLessEqual(e["context"]["chars"], 300)
        self.assertTrue(e["context"]["truncated"])
        before, after = e["context"]["chunks"]
        self.assertTrue(before["text"].startswith("…") and after["text"].endswith("…"))   # cut on the side away from the hit

    def test_no_context_without_content_or_when_asked_for_none(self):
        self.assertNotIn("context", api.search(self.s, "needle")[0])
        self.assertNotIn("context", self.hit(context="none"))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            api.search(self.s, "needle", include_content=True, context="page")

    def test_first_and_last_chunks_have_one_sided_context(self):
        self.s.put_chunks([ch(4, 2, "부록", "부록 needle")])
        self.s.put_chunks([ch(2, 3, "잠금", "확정 후 잠금")])
        e = self.hit()
        self.assertEqual([c["seq"] for c in e["context"]["chunks"]], [3])


if __name__ == "__main__":
    unittest.main()
