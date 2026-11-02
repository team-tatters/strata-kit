import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import api, search  # noqa: E402
from kb.providers import DecisionRecords, VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        w(self.vault / "_meta" / "taxonomy.yaml", "version: '2'\ncategories:\n  domain:\n    order: 1\n    children:\n      orders: {order: 1}\n  guides:\n    order: 3\ndocument_types:\n  scratch:\n    indexed: false\n")
        kb = self.vault / "projects" / "p" / "knowledge-base"
        w(kb / "domain" / "orders" / "refunds.md", "---\ntitle: Refunds\nid: kb-p-refunds\ntype: specification\ntags: [domain/orders, 3.0]\ncreated: 2026-01-01\npage_order: 2\n---\n## 개요\n협업자 매직링크 초대 흐름\n\n## 정책\n매직링크 는 일회용\n")
        w(kb / "guides" / "howto.md", "---\ntitle: How to\nid: kb-p-howto\ntype: guide\ncreated: 2026-01-01\nstatus: draft\n---\n## 절차\n매직링크 로그인\n")
        w(kb / "guides" / "notes.md", "---\ntitle: Notes\nid: kb-p-notes\ntype: scratch\ncreated: 2026-01-01\n---\n## 메모\n매직링크 메모\n")
        w(self.vault / "projects" / "p" / "sessions" / "session-2026-01-02-x.md", "---\ntitle: s\nid: session-p-2026-01-02-x\ntype: session\ncreated: 2026-01-02\ntopic: 매직링크 작업\n---\n## 완료\n매직링크 세션 본문\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            search.get_store = lambda db=None: self.store
            search.main(list(argv))
        return buf.getvalue()

    def test_indexed_false_type_has_node_but_no_chunks_and_is_not_a_document(self):
        n = self.store.get("doc:projects/p/knowledge-base/guides/notes.md")
        self.assertFalse(n.payload["indexed"])
        self.assertEqual(self.store.chunks_of(n.id), [])
        self.assertEqual([d.path for d in api.documents(self.store)],
                         ["projects/p/sessions/session-2026-01-02-x.md", "projects/p/knowledge-base/domain/orders/refunds.md",
                          "projects/p/knowledge-base/guides/howto.md"])   # legacy discovery order: history before knowledge-base

    def test_search_excludes_history_by_default_and_prints_positions(self):
        out = self.run_cli("매직링크")
        self.assertIn('검색: "매직링크" → 3건', out)
        self.assertNotIn("sessions/", out)
        self.assertIn("위치: L", out)
        self.assertIn('검색: "매직링크" → 4건', self.run_cli("매직링크", "--include-history"))   # session counted once (record dedupe), docs per chunk
        self.assertIn("(draft)", self.run_cli("매직링크", "--category", "guides"))
        self.assertIn("검색 결과 없음", self.run_cli("없는말"))

    def test_toc_tags_doc_stats(self):
        toc = self.run_cli("--toc")
        self.assertIn("## domain", toc)
        self.assertIn("### orders", toc)
        self.assertIn("2. [specification] Refunds — domain/orders/refunds.md  [domain/orders, 3.0]", toc)   # float tag does not crash
        self.assertIn("## archive", toc)
        self.assertIn('태그: "domain/orders" → 1건', self.run_cli("--tags", "domain/orders"))
        doc = self.run_cli("--doc", "refunds")
        self.assertIn("분류: domain/orders", doc)
        self.assertIn("## 개요  (L1-3", doc)
        stats = self.run_cli("--stats")
        self.assertIn("문서: 3개", stats)
        self.assertIn("domain: 1개 문서, 2개 청크", stats)

    def test_any_term_fallback_when_no_chunk_has_every_word(self):
        out = self.run_cli("매직링크 외계어zzz 로그인")
        self.assertIn("일부 단어 일치로 순위", out)
        self.assertIn("→ 3건", out)
        self.assertIn("검색 결과 없음", self.run_cli("매직링크 AND 외계어zzz"))   # explicit operators: no fallback
        hits = api.search(self.store, "매직링크 외계어zzz", mode="fts")
        self.assertTrue(hits and hits[0]["mode"].startswith("fts-any"))
        self.assertEqual(api.search(self.store, "매직링크", mode="fts")[0].get("mode"), None)   # plain fts result shape unchanged

    def test_roles_and_session_leads_to_documents(self):
        from kb.providers import DecisionRecords
        repo = Path(self.tmp.name) / "p"
        w(repo / ".strata" / "profile.yaml", "profile: embedded\nproject: p\n")
        w(repo / ".strata" / "decisions" / "DEC-2026-01-02-01-x.yaml", "decision:\n  id: DEC-2026-01-02-01\n  date: '2026-01-02'\n  topic: 매직링크 일회용\n  summary: s\n  decision: 매직링크는 한 번만\n  nodes: [auth]\n")
        w(self.vault / "projects" / "p" / "_meta" / "toc.yaml", "version: '1.0'\nproject: p\nnodes:\n  auth:\n    label: 인증\n")
        w(self.vault / "projects" / "p" / "knowledge-base" / "domain" / "orders" / "refunds.md",
          "---\ntitle: Refunds\nid: kb-p-refunds\ntype: specification\ntags: [domain/orders, 3.0]\ncreated: 2026-01-01\npage_order: 2\nnodes: [auth]\n---\n## 개요\n협업자 초대 흐름\n\n## 정책\n일회용\n")
        w(self.vault / "projects" / "p" / "sessions" / "session-2026-01-02-x.md",
          "---\ntitle: s\nid: session-p-2026-01-02-x\ntype: session\ncreated: 2026-01-02\ntopic: 매직링크 작업\nnodes: [auth]\nkb_updates: [\"[[howto]]\"]\ndecisions_made: [DEC-2026-01-02-01]\n---\n## 완료\n매직링크 세션 본문\n")
        self.store.rebuild([VaultScanner(self.vault), DecisionRecords([repo], vault=self.vault)], kit_rev="t")
        # default scope: knowledge only — the term now lives only in the session and the decision
        self.assertEqual([h["role"] for h in api.search(self.store, "매직링크")], ["knowledge"])   # howto still has it
        hits = api.search(self.store, "매직링크", include_history=True)
        roles = {h["role"] for h in hits}
        self.assertEqual(roles, {"knowledge", "session", "decision"})
        sess = next(h for h in hits if h["role"] == "session")
        leads = {(lt["via"], lt["path"].split("/")[-1]) for lt in sess["leads_to"]}
        self.assertEqual(leads, {("kb_updates", "howto.md"), ("topic", "refunds.md"), ("decision", "DEC-2026-01-02-01.md")})
        self.assertEqual(len([h for h in hits if h["role"] == "decision"]), 1)   # one entry per record, not per chunk
        dec = next(h for h in hits if h["role"] == "decision")
        self.assertIn(("topic", "refunds.md"), {(lt["via"], lt["path"].split("/")[-1]) for lt in dec["leads_to"]})
        # a term that lives only in a session/decision: default search falls through to history with its leads
        (self.vault / "projects" / "p" / "knowledge-base" / "guides" / "howto.md").write_text("---\ntitle: How to\nid: kb-p-howto\ntype: guide\ncreated: 2026-01-01\n---\n## 절차\n로그인\n", encoding="utf-8")
        self.store.rebuild([VaultScanner(self.vault), DecisionRecords([repo], vault=self.vault)], kit_rev="t")
        only = api.search(self.store, "매직링크")
        self.assertEqual({h["role"] for h in only}, {"session", "decision"})
        self.assertTrue(all(h["mode"].startswith("fts+history") for h in only))
        self.assertIn("지식 문서에는 없음", self.run_cli("매직링크"))
        out = self.run_cli("매직링크", "--include-history")
        self.assertIn("〔세션〕", out)
        self.assertIn("〔결정〕", out)
        self.assertIn("→ 갱신한 문서: guides/howto.md", out)
        self.assertIn("→ 주제의 최종형상: domain/orders/refunds.md", out)

    def test_dense_and_hybrid_fall_back_to_fts_without_embeddings(self):
        for mode in ("dense", "hybrid"):
            hits = api.search(self.store, "매직링크", mode=mode)
            self.assertTrue(hits and hits[0]["mode"].startswith("fts (no embeddings yet"), mode)

    def test_api_shapes(self):
        hits = api.search_fts(self.store, "매직링크", include_content=True)
        self.assertEqual({h["file_path"] for h in hits}, {"projects/p/knowledge-base/domain/orders/refunds.md", "projects/p/knowledge-base/guides/howto.md"})
        self.assertEqual(set(hits[0]), {"file_path", "short_path", "title", "type", "tags", "heading", "rank", "content", "role"})
        d = api.get_document(self.store, "refunds")
        self.assertEqual((d["category"], d["topic"], d["topic_order"], d["page_order"], d["nodes"], d["covers"]), ("domain", "orders", 1, 2, "[]", ""))
        self.assertEqual([c["heading"] for c in d["chunks"]], ["개요", "정책"])
        self.assertEqual(api.get_stats(self.store)["documents"], 3)
        self.assertEqual([x["short_path"] for x in api.list_documents(self.store, category="guides")], ["guides/howto.md"])


if __name__ == "__main__":
    unittest.main()
