import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.store import (Chunk, Edge, Node, ProviderOutput, SqliteStore, StoreError,  # noqa: E402
                      VectorsUnavailable, fts_query)


class FakeProvider:
    def __init__(self, name, nodes=(), edges=(), chunks=()):
        self.name = name
        self.out = ProviderOutput(list(nodes), list(edges), list(chunks))

    def collect(self):
        return self.out


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.s = SqliteStore()

    def test_put_and_get_node_roundtrip_with_payload(self):
        n = Node("doc:a", "doc", project="p", path="projects/p/a.md", title="A", updated="2026-10-28",
                 revision="abc", payload={"tags": ["x"], "nodes": ["t.a"]})
        self.assertEqual(self.s.put_nodes([n]), 1)
        self.assertEqual(self.s.get("doc:a"), n)
        self.assertIsNone(self.s.get("doc:missing"))

    def test_unknown_kinds_are_rejected(self):
        with self.assertRaises(StoreError):
            self.s.put_nodes([Node("x", "blog")])
        with self.assertRaises(StoreError):
            self.s.put_edges([Edge("a", "b", "likes")])
        with self.assertRaises(StoreError):
            self.s.put_edges([Edge("a", "b", "covers", confidence="guessed")])
        with self.assertRaises(StoreError):
            self.s.put_nodes([Node("", "doc")])

    def test_query_filters_and_orders_by_id(self):
        self.s.put_nodes([Node("doc:b", "doc", project="p", path="projects/p/kb/b.md"),
                          Node("doc:a", "doc", project="p", path="projects/p/kb/a.md", status="draft"),
                          Node("dec:1", "decision", project="q", path="x")])
        self.assertEqual([n.id for n in self.s.query(kind="doc")], ["doc:a", "doc:b"])
        self.assertEqual([n.id for n in self.s.query(project="q")], ["dec:1"])
        self.assertEqual([n.id for n in self.s.query(status="draft")], ["doc:a"])
        self.assertEqual([n.id for n in self.s.query(path_prefix="projects/p/kb/")], ["doc:a", "doc:b"])
        self.assertEqual(self.s.query(path_prefix="projects/p_kb"), [])  # underscore is literal

    def test_neighbors_by_direction_and_kind(self):
        self.s.put_edges([Edge("s1", "d1", "kb_updates"), Edge("s1", "d2", "decisions_made"), Edge("d1", "s1", "covers")])
        self.assertEqual([e.dst for e in self.s.neighbors("s1")], ["d1", "d2"])
        self.assertEqual([e.src for e in self.s.neighbors("s1", direction="in")], ["d1"])
        self.assertEqual(len(self.s.neighbors("s1", direction="both")), 3)
        self.assertEqual([e.dst for e in self.s.neighbors("s1", kind="kb_updates")], ["d1"])
        with self.assertRaises(StoreError):
            self.s.neighbors("s1", direction="sideways")

    def test_edge_upsert_is_keyed_by_src_dst_kind_source_ref(self):
        self.s.put_edges([Edge("a", "b", "covers", source_ref="fm"), Edge("a", "b", "covers", source_ref="fm", created="later")])
        edges = self.s.neighbors("a")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].created, "later")

    def test_chunks_feed_fts_and_search_filters_by_kind(self):
        self.s.put_nodes([Node("doc:a", "doc", project="p", title="A"), Node("dec:1", "decision", project="p")])
        self.s.put_chunks([Chunk("doc:a", 0, "scope_key is a materialized path index"),
                           Chunk("doc:a", 1, "collaborators get magic links"),
                           Chunk("dec:1", 0, "we decided scope_key stays immutable")])
        hits = self.s.search_text("scope_key")
        self.assertEqual({(h.node.id, h.seq) for h in hits}, {("doc:a", 0), ("dec:1", 0)})
        self.assertEqual([h.node.id for h in self.s.search_text("scope_key", kind="decision")], ["dec:1"])
        self.assertEqual(self.s.search_text("   "), [])
        # replacing a chunk re-indexes it
        self.s.put_chunks([Chunk("doc:a", 1, "nothing here")])
        self.assertEqual(self.s.search_text("magic"), [])
        self.assertEqual(len(self.s.chunks_of("doc:a")), 2)

    def test_fts_query_quotes_tokens_keeps_operators_and_prefix(self):
        self.assertEqual(fts_query('a "b" c'), '"a" "b" "c"')
        self.assertEqual(fts_query('jwt AND relay* NOT x'), '"jwt" AND "relay"* NOT "x"')
        self.assertEqual(fts_query('   '), '')
        self.assertEqual(fts_query('협업자 초대 메일', any_terms=True), '"협업자" OR "초대" OR "메일"')
        self.assertEqual(fts_query('a AND b', any_terms=True), '"a" AND "b"')   # explicit operators win

    def test_chunk_fields_roundtrip_and_title_tags_are_searchable(self):
        self.s.put_nodes([Node("doc:a", "doc", title="Auth")])
        self.s.put_chunks([Chunk("doc:a", 0, "body words", heading="Intro", title="Authentication guide", tags="project/x domain/auth",
                                 meta={"heading_level": 2, "line_start": 3, "line_end": 9, "char_count": 10})])
        c = self.s.chunks_of("doc:a")[0]
        self.assertEqual((c.heading, c.title, c.tags, c.meta["line_end"]), ("Intro", "Authentication guide", "project/x domain/auth", 9))
        self.assertEqual([h.node.id for h in self.s.search_text("Authentication")], ["doc:a"])   # title column indexed
        self.assertEqual([h.node.id for h in self.s.search_text("auth")], ["doc:a"])             # tags column indexed
        self.assertEqual([h.node.id for h in self.s.search_text("Intro")], ["doc:a"])            # heading column indexed

    def test_embeddings_cache_vector_and_hybrid_search(self):
        import numpy as np
        from kb.store import text_hash
        self.s.put_nodes([Node("doc:a", "doc", project="p"), Node("doc:b", "doc", project="p"), Node("doc:c", "doc", project="q")])
        ca, cb, cc = Chunk("doc:a", 0, "alpha beta"), Chunk("doc:b", 0, "gamma delta"), Chunk("doc:c", 0, "alpha epsilon")
        self.s.put_chunks([ca, cb, cc])
        with self.assertRaises(VectorsUnavailable):
            self.s.search_vector(np.ones(4, dtype=np.float32))
        missing = self.s.missing_embeddings("m")
        self.assertEqual([m[3] for m in missing], ["alpha beta", "gamma delta", "alpha epsilon"])
        self.s.put_embeddings("m", [(text_hash(ca), [1, 0, 0, 0]), (text_hash(cb), [0, 1, 0, 0]), (text_hash(cc), [0.9, 0.1, 0, 0])])
        self.assertEqual(self.s.embedding_coverage(), (3, 3))
        self.assertEqual(self.s.embedding_model(), "m")
        self.assertEqual(self.s.missing_embeddings("m"), [])
        hits = self.s.search_vector([1, 0, 0, 0], limit=2)
        self.assertEqual([h.node.id for h in hits], ["doc:a", "doc:c"])
        self.assertAlmostEqual(hits[0].rank, -1.0, places=5)
        self.assertEqual([h.node.id for h in self.s.search_vector([1, 0, 0, 0], project="q")], ["doc:c"])
        with self.assertRaises(StoreError):
            self.s.search_vector([1, 0])
        # hybrid: 'alpha' is in a and c (fts); the vector prefers b → b surfaces through fusion
        hyb = self.s.search_hybrid("alpha", [0, 1, 0, 0], limit=3)
        self.assertEqual({h.node.id for h in hyb}, {"doc:a", "doc:b", "doc:c"})   # fusion surfaces b (vector only) with a·c (fts)
        self.assertIn(hyb[0].node.id, {"doc:a", "doc:c"})                         # a chunk present in both rankings leads
        # knowledge_only keeps records out of the candidate pool before the cut
        self.s.put_nodes([Node("decision:p:DEC-1", "decision", project="p")])
        from kb.store import text_hash as th
        cd = Chunk("decision:p:DEC-1", 0, "alpha alpha alpha")
        self.s.put_chunks([cd]); self.s.put_embeddings("m", [(th(cd), [1, 0, 0, 0])])
        self.assertIn("decision:p:DEC-1", [h.node.id for h in self.s.search_vector([1, 0, 0, 0], limit=2)])   # ties with doc:a
        self.assertEqual(self.s.search_vector([1, 0, 0, 0], limit=1, knowledge_only=True)[0].node.id, "doc:a")
        self.assertTrue(all(h.node.kind != "decision" for h in self.s.search_hybrid("alpha", [1, 0, 0, 0], limit=5, knowledge_only=True)))
        # rebuild keeps the cache and reattaches vectors without recomputation
        class P:
            name = "p"
            def collect(self_inner):
                return ProviderOutput([Node("doc:a", "doc", project="p"), Node("doc:d", "doc")], [], [ca, Chunk("doc:d", 0, "zeta")])
        self.s.rebuild([P()])
        self.assertEqual(self.s.embedding_coverage(), (1, 2))
        self.assertEqual([m[3] for m in self.s.missing_embeddings("m")], ["zeta"])
        self.assertEqual([h.node.id for h in self.s.search_vector([1, 0, 0, 0])], ["doc:a"])

    def test_old_schema_file_is_recreated(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "store.sqlite"
            c = sqlite3.connect(path); c.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT); INSERT INTO meta VALUES ('schema_version','1'); CREATE TABLE nodes(x);"); c.close()
            s = SqliteStore(path)
            self.assertEqual(s.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0], "3")
            self.assertIn("payload_json", {r[1] for r in s.conn.execute("PRAGMA table_info(nodes)")})
            s.close()

    def test_search_vector_is_explicitly_unavailable(self):
        with self.assertRaises(VectorsUnavailable):
            self.s.search_vector(b"\x00" * 4)
        self.assertFalse(self.s.supports_vectors)

    def test_rebuild_replaces_generated_rows_keeps_baselines_and_records_revision(self):
        self.s.put_nodes([Node("old", "doc")])
        self.s.put_edges([Edge("old", "x", "covers")])
        self.s.put_chunks([Chunk("old", 0, "stale text")])
        self.s.put_baseline("link", "p", "projects/p/a.md#[[gone]]", recorded="2026-09-30")
        p1 = FakeProvider("vault", nodes=[Node("doc:a", "doc", revision="r1")], chunks=[Chunk("doc:a", 0, "fresh text")])
        p2 = FakeProvider("decisions", nodes=[Node("dec:1", "decision")], edges=[Edge("dec:1", "dec:0", "supersedes", source_ref="rec")])
        rev = self.s.rebuild([p1, p2], kit_rev="36bc3bf")
        self.assertIsNone(self.s.get("old"))
        self.assertEqual(self.s.search_text("stale"), [])
        self.assertEqual(len(self.s.search_text("fresh")), 1)
        self.assertEqual(self.s.counts(), {"nodes": 2, "edges": 1, "chunks": 1, "baselines": 1})
        self.assertEqual(self.s.baselines("link", "p"), {"projects/p/a.md#[[gone]]"})
        self.assertEqual(self.s.revision(), rev)
        self.assertEqual(rev.kit_rev, "36bc3bf")
        # dangling edge target dec:0 is reported, not rejected
        self.assertEqual([e.dst for e in self.s.dangling_edges()], ["dec:0"])
        # same sources → same hashes; changed revision → different hash
        self.assertEqual(self.s.rebuild([p1, p2], kit_rev="36bc3bf").sources_hash, rev.sources_hash)
        p1.out.nodes = [Node("doc:a", "doc", revision="r2")]
        self.assertNotEqual(self.s.rebuild([p1, p2], kit_rev="36bc3bf").sources_hash, rev.sources_hash)

    def test_rebuild_is_atomic_on_invalid_provider_output(self):
        self.s.put_nodes([Node("keep", "doc")])
        bad = FakeProvider("bad", nodes=[Node("n", "nope")])
        with self.assertRaises(StoreError):
            self.s.rebuild([bad])
        self.assertIsNotNone(self.s.get("keep"))

    def test_file_backed_store_persists(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "store.sqlite"
            s = SqliteStore(path)
            s.put_nodes([Node("doc:a", "doc")])
            s.close()
            s2 = SqliteStore(path)
            self.assertIsNotNone(s2.get("doc:a"))
            s2.close()


if __name__ == "__main__":
    unittest.main()
