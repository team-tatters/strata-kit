"""Opt-in cross-encoder rerank (kb/rerank.py): off by default, reorders the first candidates by score, falls back to
the original order with a note when the model cannot load. No test downloads a model: a fake scorer stands in."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api, rerank, search  # noqa: E402
from kb.evals import search_eval  # noqa: E402
from kb.store import Chunk, Node, SqliteStore  # noqa: E402


def fake_scorer(query, texts):
    """Scores a text by how often it says 'best' — enough to tell a reorder from bm25 order."""
    return [t.count("best") for t in texts]


def unavailable(query, texts):
    raise rerank.RerankUnavailable("rerank model unavailable: sentence_transformers")


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore()
        nodes, chunks = [], []
        # bm25 favours the short, needle-dense chunks; the fake scorer favours 'best'
        for i, text in enumerate(["needle needle", "needle needle needle", "needle and some best best best words here"]):
            nid = f"doc:{i}"
            nodes.append(Node(nid, "doc", path=f"projects/p/knowledge-base/d{i}.md", title=f"D{i}", payload={"indexed": True}))
            chunks.append(Chunk(nid, 0, text, heading=f"h{i}", meta={"heading_level": 2}))
        self.s.put_nodes(nodes)
        self.s.put_chunks(chunks)


class ApiRerankTest(StoreCase):
    def test_off_by_default_and_never_loads_a_model(self):
        with mock.patch.object(rerank, "get_reranker", side_effect=AssertionError("loaded")):
            out = api.search(self.s, "needle", mode="fts")
        self.assertNotIn("rerank_score", out[0])
        self.assertNotEqual(out[0]["title"], "D2")

    def test_rerank_reorders_and_marks_the_mode(self):
        out = api.search(self.s, "needle", mode="fts", limit=2, rerank=True, _scorer=fake_scorer)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "D2")          # pulled up from below the cut
        self.assertEqual(out[0]["rerank_score"], 3)
        self.assertTrue(all(e["mode"] == "fts+rerank" for e in out))
        self.assertNotIn("content", out[0])               # content was only fetched for scoring

    def test_context_follows_the_reranked_hit(self):
        out = api.search(self.s, "needle", mode="fts", limit=1, rerank=True, include_content=True, _scorer=fake_scorer)
        self.assertEqual(out[0]["title"], "D2")
        self.assertIn("best", out[0]["content"])
        self.assertIn("context", out[0])

    def test_unavailable_model_keeps_order_with_a_note(self):
        plain = api.search(self.s, "needle", mode="fts", limit=2)
        out = api.search(self.s, "needle", mode="fts", limit=2, rerank=True, _scorer=unavailable)
        self.assertEqual([e["title"] for e in out], [e["title"] for e in plain])
        self.assertIn("rerank skipped", out[0]["mode"])
        self.assertNotIn("rerank_score", out[0])

    def test_import_error_in_the_real_loader_becomes_unavailable(self):
        r = rerank.Reranker("x")
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with self.assertRaises(rerank.RerankUnavailable):
                r("q", ["t"])


class RerankFunctionTest(unittest.TestCase):
    def test_only_the_head_is_rescored_and_the_tail_keeps_its_order(self):
        seen = []

        def scorer(q, texts):
            seen.extend(texts)
            return [0, 5]
        items, scores = rerank.rerank("q", ["a", "b", "c", "d"], str, top_n=2, scorer=scorer)
        self.assertEqual(items, ["b", "a", "c", "d"])
        self.assertEqual(scores, [5, 0])
        self.assertEqual(seen, ["a", "b"])

    def test_defaults_match_the_measured_trade_off(self):
        self.assertEqual((rerank.DEFAULT_MODEL, rerank.TOP_N, rerank.MAX_LENGTH), ("BAAI/bge-reranker-v2-m3", 30, 384))

    def test_reranker_is_cached_per_process(self):
        self.assertIs(rerank.get_reranker("m-test"), rerank.get_reranker("m-test"))


class CliRerankTest(StoreCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(search, "get_store", return_value=self.s), redirect_stdout(buf):
            search.main(list(argv))
        return buf.getvalue()

    def test_flag_reranks_and_labels(self):
        with mock.patch.object(rerank, "get_reranker", return_value=fake_scorer):
            out = self.run_cli("needle", "--rerank", "--limit", "1")
        self.assertIn("[fts+rerank]", out)
        self.assertIn("d2.md", out)

    def test_flag_without_model_falls_back_with_a_note(self):
        with mock.patch.object(rerank, "get_reranker", return_value=unavailable):
            out = self.run_cli("needle", "--rerank", "--limit", "1")
        self.assertIn("재순위 생략", out)
        self.assertNotIn("d2.md", out)


class EvalRerankTest(StoreCase):
    def test_rerank_mode_counts_documents_after_reordering(self):
        q = [{"q": "needle", "expect": ["d2.md"]}]
        res = search_eval.run(self.s, q, ks=(1,), modes=("fts", "fts+rerank"), scorer=fake_scorer)
        self.assertEqual(res["summary"]["fts"][1], 0.0)
        self.assertEqual(res["summary"]["fts+rerank"][1], 1.0)
        self.assertIn("fts+rerank", search_eval.format_report(res, ks=(1,)))


if __name__ == "__main__":
    unittest.main()
