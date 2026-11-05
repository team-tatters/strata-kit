"""Korean particles in FTS (MB-strata-kit-2026-056 step 1): the unicode61 tokenizer keeps '결정을' and '결정' apart,
so the index and the query both drop a trailing particle before tokenizing. Identifiers stay exact."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api  # noqa: E402
from kb.store import SCHEMA_VERSION, Chunk, Node, ProviderOutput, SqliteStore, fts_normalize, fts_query, text_hash  # noqa: E402


class NormalizeTest(unittest.TestCase):
    def test_trailing_particles_are_dropped(self):
        self.assertEqual(fts_normalize("결정을 결정은 결정의"), "결정 결정 결정")
        self.assertEqual(fts_normalize("알고리즘으로 서버에서 사용자의"), "알고리즘 서버 사용자")
        self.assertEqual(fts_normalize("확정하고 잠그는 정책"), "확정 잠그 정책")

    def test_identifiers_and_short_words_are_kept(self):
        self.assertEqual(fts_normalize("JwtResult config.key_name scope_key"), "JwtResult config.key_name scope_key")
        self.assertEqual(fts_normalize("JWT로 S3에"), "JWT S3")            # a particle glued to a latin token
        self.assertEqual(fts_normalize("회의 정의 경로 평가"), "회의 정의 경로 평가")   # one-syllable stems are not cut
        self.assertEqual(fts_normalize("1만"), "1만")

    def test_query_uses_the_same_normalization(self):
        self.assertEqual(fts_query("결정을 내리는 JwtResult"), '"결정" "내리" "JwtResult"')
        self.assertEqual(fts_query("결정을*", any_terms=True), '"결정"*')


class KoreanSearchTest(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore()
        self.s.put_nodes([Node("doc:a", "doc", title="A", payload={"indexed": True}), Node("doc:b", "doc", title="B", payload={"indexed": True})])
        self.s.put_chunks([Chunk("doc:a", 0, "이 문서는 결정을 기록한다. JwtResult 를 돌려준다", heading="결정의 배경"),
                           Chunk("doc:b", 0, "JWT로 인증하고 S3에 쌓는다")])

    def test_particle_variants_find_each_other(self):
        self.assertEqual([h.node.id for h in self.s.search_text("결정")], ["doc:a"])
        self.assertEqual([h.node.id for h in self.s.search_text("결정은")], ["doc:a"])
        self.assertEqual([h.node.id for h in self.s.search_text("JWT")], ["doc:b"])
        self.assertEqual([r["node"].id for r in api.fts_rows(self.s, "배경이")], ["doc:a"])

    def test_exact_identifiers_still_match(self):
        self.assertEqual([h.node.id for h in self.s.search_text("JwtResult")], ["doc:a"])
        self.assertEqual(self.s.search_text("JwtRes"), [])

    def test_chunk_text_is_returned_unnormalized(self):
        self.assertEqual(self.s.chunk("doc:a", 0).text, "이 문서는 결정을 기록한다. JwtResult 를 돌려준다")

    def test_replaced_duplicate_chunks_leave_no_stale_index_rows(self):
        # two providers emitting the same (node_id, seq): INSERT OR REPLACE deletes the first row; its index row must go too
        class P:
            def __init__(self, name, text):
                self.name, self.text = name, text

            def collect(self):
                return ProviderOutput([Node("order:x", "order")], [], [Chunk("order:x", 0, self.text)])
        for _ in range(2):
            self.s.rebuild([P("a", "첫번째 오더 본문"), P("b", "두번째 오더 본문")])
        self.assertEqual(self.s.search_text("첫번째"), [])
        self.assertEqual(self.s.conn.execute("SELECT COUNT(*) FROM chunks_fts_docsize").fetchone()[0],
                         self.s.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        self.s.conn.execute("INSERT INTO chunks_fts(chunks_fts, rank) VALUES ('integrity-check', 1)")


class SchemaUpgradeTest(unittest.TestCase):
    def test_upgrade_keeps_the_embedding_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "store.sqlite"
            s = SqliteStore(path)
            c = Chunk("doc:a", 0, "alpha")
            s.put_nodes([Node("doc:a", "doc")])
            s.put_chunks([c])
            s.put_embeddings("m", [(text_hash(c), [1.0, 0.0])])
            s.conn.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
            s.conn.commit()
            s.close()
            s2 = SqliteStore(path)
            self.assertEqual(s2.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], SCHEMA_VERSION)
            self.assertEqual(s2.counts()["chunks"], 0)                       # generated rows are rebuilt, not migrated
            self.assertEqual(s2.embedding_model(), "m")
            self.assertEqual(s2.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0], 1)
            s2.put_nodes([Node("doc:a", "doc")])
            s2.put_chunks([c])
            self.assertEqual(s2.missing_embeddings("m"), [])
            s2.close()

    def test_unreadable_old_file_is_simply_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "store.sqlite"
            conn = sqlite3.connect(path)
            conn.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT); INSERT INTO meta VALUES ('schema_version','1');")
            conn.close()
            s = SqliteStore(path)
            self.assertIsNone(s.embedding_model())
            s.close()


if __name__ == "__main__":
    unittest.main()
