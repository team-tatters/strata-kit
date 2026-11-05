"""Sections over the encoder window are split; every other chunk is untouched (MB-strata-kit-2026-056)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import chunking  # noqa: E402
from kb.chunking import estimate_tokens, split_over_tokens  # noqa: E402
from kb.store import embed_text  # noqa: E402


def words(n: int, tag: str) -> str:
    return " ".join(f"{tag}{i}" for i in range(n))


def chunk(content: str, heading: str = "긴 절") -> dict:
    return {"heading": heading, "heading_level": 2, "content": content, "line_start": 1, "line_end": 9}


def embedded(c: dict) -> str:
    return embed_text("문서", c["heading"], c["content"])


class SplitOverTokensTest(unittest.TestCase):
    def test_sections_that_fit_are_returned_unchanged(self):
        chunks = [chunk("짧은 본문", "a"), chunk(words(300, "w"), "b")]
        out = split_over_tokens(chunks, embedded, count=estimate_tokens)
        self.assertEqual(out, chunks)
        self.assertNotIn("part", out[1])

    def test_over_limit_section_splits_at_paragraphs_under_the_limit(self):
        paras = [words(120, f"p{k}_") for k in range(30)]   # ~30 paragraphs of ~600 chars
        c = chunk("\n\n".join(paras))
        self.assertGreater(estimate_tokens(embedded(c)), chunking.TOKEN_LIMIT)
        out = split_over_tokens([c], embedded, count=estimate_tokens)
        self.assertGreater(len(out), 1)
        for k, d in enumerate(out):
            self.assertEqual(d["heading"], "긴 절")
            self.assertEqual(d["part"], [k + 1, len(out)])
            self.assertLessEqual(estimate_tokens(embedded(d)), chunking.TOKEN_LIMIT)
            self.assertLessEqual(estimate_tokens(embedded(d)), chunking.TARGET_TOKENS + 10)
        # cuts fall between paragraphs: every paragraph is whole in some piece
        for p in paras:
            self.assertTrue(any(p in d["content"] for d in out), p[:20])
        # later pieces lead with '…' + the end of the previous piece
        for prev, d in zip(out, out[1:]):
            self.assertTrue(d["content"].startswith("…"))
            lead = d["content"][1:d["content"].index("\n")]
            self.assertTrue(prev["content"].endswith(lead))
            self.assertLessEqual(len(lead), chunking.OVERLAP_CHARS)
        self.assertEqual(sum(d["own_chars"] for d in out) + 2 * (len(out) - 1), len(c["content"]))

    def test_single_huge_paragraph_falls_back_to_lines_then_characters(self):
        lines = "\n".join(words(40, f"l{k}_") for k in range(200))
        out = split_over_tokens([chunk(lines)], embedded, count=estimate_tokens)
        self.assertGreater(len(out), 1)
        self.assertTrue(all(estimate_tokens(embedded(d)) <= chunking.TOKEN_LIMIT for d in out))
        self.assertIn("\nl1_0 ", out[0]["content"])           # lines inside a piece keep their single newline
        blob = "가" * 20000                                    # no paragraph or line break at all
        out = split_over_tokens([chunk(blob)], embedded, count=estimate_tokens)
        self.assertGreater(len(out), 1)
        self.assertTrue(all(estimate_tokens(embedded(d)) <= chunking.TOKEN_LIMIT for d in out))
        self.assertEqual("".join(d["content"][len(d["content"]) - d["own_chars"]:] for d in out), blob)

    def test_output_is_deterministic(self):
        c = chunk("\n\n".join(words(150, f"d{k}_") for k in range(25)))
        a = split_over_tokens([c], embedded, count=estimate_tokens)
        b = split_over_tokens([dict(c)], embedded, count=estimate_tokens)
        self.assertEqual(a, b)

    def test_fallback_counter_when_tokenizer_unavailable(self):
        with mock.patch.object(chunking, "_COUNTER", None), mock.patch.dict(sys.modules, {"transformers": None}):
            count, source = chunking.token_counter()
            self.assertEqual(source, "chars")
            self.assertIs(count, estimate_tokens)


class ScannerSplitTest(unittest.TestCase):
    def test_scanner_splits_only_the_long_section(self):
        from kb.providers import VaultScanner
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            doc = vault / "projects" / "demo" / "knowledge-base" / "domain" / "long.md"
            doc.parent.mkdir(parents=True)
            long_body = "\n\n".join(words(120, f"p{k}_") for k in range(30)) + "\n\n뒤쪽의 사실"
            doc.write_text("---\ntitle: Long\ntype: concept\nproject: demo\ncreated: 2026-11-05\n---\n"
                           "## 짧은 절\n\n짧다.\n\n## 긴 절\n\n" + long_body + "\n\n## 끝 절\n\n끝.\n", encoding="utf-8")
            os.environ["STRATA_VAULT"] = str(vault)
            with mock.patch.object(chunking, "_COUNTER", (estimate_tokens, "chars")):
                out = VaultScanner(vault).collect()
            chunks = [c for c in out.chunks if c.node_id.endswith("long.md")]
            self.assertEqual([c.seq for c in chunks], list(range(len(chunks))))
            self.assertEqual(chunks[0].heading, "짧은 절")
            self.assertEqual(chunks[0].text, "짧다.")
            self.assertNotIn("part", chunks[0].meta)
            self.assertEqual(chunks[-1].text, "끝.")
            parts = [c for c in chunks if c.heading == "긴 절"]
            self.assertGreater(len(parts), 1)
            self.assertEqual([c.meta["part"] for c in parts], [[k + 1, len(parts)] for k in range(len(parts))])
            self.assertTrue(all(estimate_tokens(embed_text(c.title, c.heading, c.text)) <= chunking.TOKEN_LIMIT for c in parts))
            self.assertIn("뒤쪽의 사실", parts[-1].text)
            self.assertEqual(parts[1].meta["char_count"], len(parts[1].text))
            self.assertLess(parts[1].meta["own_chars"], parts[1].meta["char_count"])


if __name__ == "__main__":
    unittest.main()
