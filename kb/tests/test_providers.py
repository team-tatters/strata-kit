import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.providers import DecisionRecords, Orders, VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        self.repo = root / "demo"
        p = self.vault / "projects" / "demo"
        w(p / "_meta" / "toc.yaml", "version: '1.0'\nproject: demo\nnodes:\n  orders:\n    label: 주문\n    order: 1\n"
                                     "    children:\n      refunds:\n        label: Refunds\n        aliases: [refund-alias]\n")
        w(p / "knowledge-base" / "domain" / "orders" / "refunds.md",
          "---\ntitle: Refunds\nid: kb-demo-refunds\ntype: specification\nproject: demo\nstatus: active\ncreated: 2026-04-01\n"
          "updated: 2026-08-20\nnodes: [refund-alias]\nsupersedes: [\"[[old]]\"]\ndecisions: [DEC-2026-08-01-01]\n"
          "covers:\n  paths: [\"service/order-api/refunds/\"]\n  symbols: [RefundService]\n---\n## 본문\n\nscope_key 는 고정폭 색인이다.\n\n## 정책\n\n협업자 매직링크.\n")
        w(p / "knowledge-base" / "domain" / "orders" / "old.md",
          "---\ntitle: old\nid: kb-demo-old\ntype: concept\nproject: demo\ncreated: 2026-01-01\nsuperseded_by: \"[[refunds]]\"\n---\n## 개념\n옛 글\n")
        w(p / "sessions" / "session-2026-09-05-refunds.md",
          "---\ntitle: s3\nid: session-demo-2026-09-05-refunds\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-09-05\n"
          "nodes: [orders.refunds]\norders: [\"[[tasks/2026.09.05/01-refunds/_order|2026.09.05-01]] refunds (note)\"]\nkb_updates: [\"[[refunds]]\", \"[[nowhere]]\", \"[[old]] (annotated link)\", \"knowledge-base/domain/orders/old.md §2 (path with remark)\", \"TRACK_BOARD\"]\ndecisions_made: [DEC-2026-08-02-01, \"other DEC-2026-08-03-01\"]\n---\n## 완료\n끝\n")
        w(self.vault / "patterns" / "p.md", "---\ntitle: p\nid: kb-vault-p\ntype: pattern\ncreated: 2026-01-01\n---\n## 문제\n패턴 본문\n")
        w(self.vault / "TRACK_BOARD.md", "# board\n")
        w(self.repo / ".strata" / "profile.yaml", "profile: embedded\nproject: demo\n")
        w(self.repo / ".strata" / "decisions" / "DEC-2026-08-01-01-first.yaml",
          "decision:\n  id: DEC-2026-08-01-01\n  date: '2026-08-01'\n  session: session-2026-09-05-refunds\n  topic: first\n  summary: s1\n  decision: d1\n  reason: r1\n  nodes: [orders.refunds]\n")
        w(self.repo / ".strata" / "decisions" / "DEC-2026-08-02-01-second.yaml",
          "decision:\n  id: DEC-2026-08-02-01\n  date: '2026-08-02'\n  topic: second\n  summary: s2\n  decision: d2\n  supersedes: [DEC-2026-08-01-01]\n  nodes: [refund-alias]\n")
        w(p / "tasks" / "2026.09.05" / "01-refunds" / "_order.yaml",
          "order:\n  id: \"2026.09.05-01\"\n  title: refunds order\n  date: \"2026-09-05\"\n  status: completed\n  decisions: [\"DEC-2026-08-02-01 (demo)\"]\n"
          "  goal: |\n    do refunds\n  tasks:\n    - {id: task-01, title: t1}\n")
        w(p / "tasks" / "2026.08.19" / "02-old-style" / "_order.md",
          "---\ntitle: \"order 2026.08.19-02\"\naliases: [\"2026.08.19-02\"]\norder:\n  id: \"2026.08.19-02\"\n  title: old style order\n  date: \"2026-08-19\"\n  status: completed\n---\n# body\n")
        w(p / "tasks" / "2026.09.05" / "01-refunds" / "task-01.yaml",
          "task: {id: \"2026.09.05-01/task-01\", title: first task}\nscope: {repo: /r, module: L2}\ninputs:\n  requirements: |\n    build it\nstatus: completed\n")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        self.tmp.cleanup()

    def test_vault_scanner_nodes_edges_chunks(self):
        out = VaultScanner(self.vault).collect()
        ids = {n.id: n for n in out.nodes}
        self.assertEqual(ids["doc:projects/demo/knowledge-base/domain/orders/refunds.md"].kind, "doc")
        self.assertEqual(ids["doc:projects/demo/sessions/session-2026-09-05-refunds.md"].kind, "session")
        self.assertEqual(ids["doc:patterns/p.md"].project, "vault")
        self.assertEqual(ids["node:demo:orders.refunds"].title, "Refunds")
        self.assertEqual(ids["node:demo:orders.refunds"].payload["aliases"], ["refund-alias"])
        spec = ids["doc:projects/demo/knowledge-base/domain/orders/refunds.md"]
        self.assertEqual(spec.payload["stable_id"], "kb-demo-refunds")
        self.assertEqual(spec.updated, "2026-08-20")
        self.assertEqual(len(spec.revision), 64)
        edges = {(e.src, e.dst, e.kind, e.source_ref) for e in out.edges}
        spec_id, sess_id = spec.id, "doc:projects/demo/sessions/session-2026-09-05-refunds.md"
        old_id = "doc:projects/demo/knowledge-base/domain/orders/old.md"
        self.assertIn((spec_id, "node:demo:orders.refunds", "member_of", "nodes"), edges)          # alias resolved
        self.assertIn(("node:demo:orders.refunds", "node:demo:orders", "member_of", "toc"), edges)
        self.assertIn((spec_id, old_id, "supersedes", "supersedes"), edges)                    # [[old]] → stem
        self.assertIn((spec_id, old_id, "supersedes", "superseded_by"), edges)                 # reverse of superseded_by
        self.assertIn((spec_id, "decision:demo:DEC-2026-08-01-01", "decisions_made", "decisions"), edges)
        self.assertIn((spec_id, "code:demo:paths:service/order-api/refunds/", "covers", "covers.paths"), edges)
        self.assertIn((spec_id, "code:demo:symbols:RefundService", "covers", "covers.symbols"), edges)
        self.assertIn((sess_id, spec_id, "kb_updates", "kb_updates"), edges)
        self.assertIn((sess_id, "ref:nowhere", "kb_updates", "kb_updates"), edges)            # unresolved kept visible
        self.assertIn((sess_id, old_id, "kb_updates", "kb_updates"), edges)                   # "[[old]] (note)" still resolves
        self.assertIn((sess_id, "doc:TRACK_BOARD.md", "kb_updates", "kb_updates"), edges)       # an undiscovered markdown file is a node too
        self.assertEqual(sum(1 for e in out.edges if e.src == sess_id and e.dst == old_id and e.kind == "kb_updates"), 2)   # "[[old]] (note)" and "…/old.md §2 (remark)" both resolve; the store keeps one edge
        self.assertIn((sess_id, "order:demo:2026.09.05-01", "orders", "orders"), edges)
        self.assertIn((sess_id, "decision:demo:DEC-2026-08-02-01", "decisions_made", "decisions_made"), edges)
        self.assertIn((sess_id, "decision:other:DEC-2026-08-03-01", "decisions_made", "decisions_made"), edges)   # "<project> DEC-…" names another project's record
        self.assertTrue(all(e.confidence == "declared" for e in out.edges))
        chunks = [c for c in out.chunks if c.node_id == spec_id]
        self.assertEqual([(c.heading, c.title, c.meta["heading_level"]) for c in chunks], [("본문", "Refunds", 2), ("정책", "Refunds", 2)])
        self.assertTrue(chunks[0].text.startswith("scope_key"))
        self.assertEqual(chunks[0].meta["char_count"], len(chunks[0].text))
        self.assertEqual((spec.payload["category"], spec.payload["section_name"]), ("", "domain"))   # no taxonomy → legacy section mode
        self.assertEqual(spec.payload["links_raw"], ["DEC-2026-08-01-01", "old"])   # typed links in legacy field order (decisions before supersedes)
        sess = ids["doc:projects/demo/sessions/session-2026-09-05-refunds.md"]
        self.assertEqual((sess.payload["category"], sess.payload["topic"]), ("archive", "sessions"))

    def test_frontmatter_paths_and_prose_links_are_not_broken_references(self):
        p = self.vault / "projects" / "demo"
        w(p / "tasks" / "2026.09.05" / "01-refunds" / "reconcile.sql", "select 1;\n")
        w(p / "planning" / "tree" / "03-fact-lists" / "a.md", "# a\n")
        w(p / "sessions" / "session-2026-09-06-links.md",
          "---\ntitle: s6\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-09-06\n"
          "kb_updates: [\"tasks/2026.09.05/01-refunds/reconcile.sql (dump)\", \"TRACK_BOARD.md B8·B9\", \"신규 KB 11건 + 패턴 3건\", \"[[refunds]]\"]\n---\n"
          "## 본문\n[목록](../planning/tree/03-fact-lists/) 과 reviewers[{id}](순서대로), [없음](../planning/missing.md)\n")
        out = VaultScanner(self.vault).collect()
        sess = "doc:projects/demo/sessions/session-2026-09-06-links.md"
        edges = {(e.dst, e.kind, e.source_ref) for e in out.edges if e.src == sess}
        self.assertIn(("file:projects/demo/tasks/2026.09.05/01-refunds/reconcile.sql", "kb_updates", "kb_updates"), edges)   # a produced file, not a broken ref
        self.assertIn(("doc:TRACK_BOARD.md", "kb_updates", "kb_updates"), edges)                                          # row id after the path is a remark
        self.assertFalse(any(d.startswith("ref:신규") for d, _, _ in edges))                                               # free text makes no edge
        self.assertIn(("doc:projects/demo/knowledge-base/domain/orders/refunds.md", "kb_updates", "kb_updates"), edges)
        self.assertIn(("file:projects/demo/planning/tree/03-fact-lists", "links", "md:dir:../planning/tree/03-fact-lists/"), edges)   # a directory link resolves
        self.assertFalse(any("순서대로" in r for _, _, r in edges))                                                        # a bare word in prose is not a link
        self.assertIn(("doc:projects/demo/planning/missing.md", "links", "md:none:../planning/missing.md"), edges)

    def test_origin_immutable_marks_notion_exports(self):
        from kb.providers.vault_scanner import is_origin_immutable
        p = self.vault / "projects" / "demo"
        w(p / "planning" / "intake" / "story.md", "---\ntitle: story\ntype: planning\nproject: demo\nstatus: requested\ncreated: 2026-09-01\nsource: \"notion:abc123\"\n---\n[[주문 정책 페이지]] 와 [첨부](files/a.xlsx)\n")
        out = VaultScanner(self.vault).collect()
        node = next(n for n in out.nodes if n.id == "doc:projects/demo/planning/intake/story.md")
        self.assertTrue(is_origin_immutable(node.payload))
        self.assertFalse(is_origin_immutable(next(n for n in out.nodes if n.id.endswith("refunds.md")).payload))

    def test_reviews_are_indexed_in_full_and_validated(self):
        """DEC-2026-10-30-03: a review record under reviews/ is a history document indexed in full, checked as type review."""
        p = self.vault / "projects" / "demo"
        kit = Path(__file__).resolve().parents[2]
        w(self.vault / "_meta" / "taxonomy.yaml", (kit / "core/templates/vault/_meta/taxonomy.yaml").read_text(encoding="utf-8"))
        filler = "\n".join(f"줄 {i}" for i in range(60))
        w(p / "reviews" / "2026-10-29-cross-review.md",
          "---\ntitle: r1\ntype: review\nproject: demo\nreview_of: abc123\nreceived: 2026-10-29\nsource: 외부 모델\n"
          "created: 2026-10-29\n---\n## 대응 요약\n수용\n\n## 원문\n" + filler + "\n깊은 곳의 지적\n")
        w(p / "reviews" / "no-fields.md", "---\ntitle: r2\ntype: review\nproject: demo\ncreated: 2026-10-29\n---\n## 원문\nx\n")
        out = VaultScanner(self.vault).collect()
        nodes = {n.id: n for n in out.nodes}
        node = nodes["doc:projects/demo/reviews/2026-10-29-cross-review.md"]
        self.assertEqual(node.payload["category"], "review")
        self.assertTrue(node.payload["history"])
        self.assertTrue(any("깊은 곳의 지적" in c.text for c in out.chunks if c.node_id == node.id))
        missing = " ".join(str(d) for d in nodes["doc:projects/demo/reviews/no-fields.md"].payload["diagnostics"])
        self.assertIn("review_of", missing)

    def test_decision_records_status_and_edges(self):
        out = DecisionRecords([self.repo], vault=self.vault).collect()
        nodes = {n.id: n for n in out.nodes}
        first, second = nodes["decision:demo:DEC-2026-08-01-01"], nodes["decision:demo:DEC-2026-08-02-01"]
        self.assertEqual(first.status, "superseded")
        self.assertEqual(first.payload["superseded_by"], ["DEC-2026-08-02-01"])
        self.assertEqual(second.status, "active")
        self.assertEqual(first.path, ".strata/decisions/DEC-2026-08-01-01-first.yaml")
        self.assertEqual(first.payload["mirror"], "projects/demo/decisions/DEC-2026-08-01-01.md")
        edges = {(e.src, e.dst, e.kind) for e in out.edges}
        self.assertIn(("decision:demo:DEC-2026-08-02-01", "decision:demo:DEC-2026-08-01-01", "supersedes"), edges)
        self.assertIn(("decision:demo:DEC-2026-08-01-01", "node:demo:orders.refunds", "member_of"), edges)
        self.assertIn(("doc:projects/demo/sessions/session-2026-09-05-refunds.md", "decision:demo:DEC-2026-08-01-01", "decisions_made"), edges)
        self.assertEqual([(c.heading, c.text) for c in out.chunks if c.node_id == first.id],
                         [("first", "s1"), ("decision", "d1"), ("reason", "r1")])

    def test_order_id_forms(self):
        from kb.providers.vault_scanner import order_id
        self.assertEqual(order_id("2026.09.30-04"), "2026.09.30-04")
        self.assertEqual(order_id("[[2026.08.28-04]] c1-authz (task-02 완결)"), "2026.08.28-04")
        self.assertEqual(order_id("[[04-billing/_order|2026.09.30-04]]"), "2026.09.30-04")
        self.assertEqual(order_id("tasks/2026.09.15/01-billing-workspace-isolation-api"), "2026.09.15-01")
        self.assertEqual(order_id("free text"), "free text")

    def test_decision_record_string_supersedes_names_ids_not_characters(self):
        w(self.repo / ".strata" / "decisions" / "DEC-2026-08-03-01-legacy.yaml",
          "decision:\n  id: DEC-2026-08-03-01\n  date: '2026-08-03'\n  topic: legacy\n  summary: s\n  decision: d\n"
          "  supersedes: DEC-2026-08-01-01 (Applier 부분)\n")
        out = DecisionRecords([self.repo]).collect()
        edges = {(e.src, e.dst) for e in out.edges if e.kind == "supersedes" and e.src.endswith("DEC-2026-08-03-01")}
        self.assertEqual(edges, {("decision:demo:DEC-2026-08-03-01", "decision:demo:DEC-2026-08-01-01")})

    def test_orders_provider(self):
        out = Orders(self.vault).collect()
        ids = {n.id: n for n in out.nodes}
        o = ids["order:demo:2026.09.05-01"]
        self.assertEqual((o.kind, o.title, o.status, o.updated), ("order", "refunds order", "completed", "2026-09-05"))
        self.assertEqual(o.payload["decisions"], ["DEC-2026-08-02-01"])
        t = ids["task:demo:2026.09.05-01/task-01"]
        self.assertEqual((t.kind, t.title, t.payload["layer"], t.payload["repo"]), ("task", "first task", "L2", "/r"))
        edges = {(e.src, e.dst, e.kind) for e in out.edges}
        self.assertIn((t.id, o.id, "member_of"), edges)
        self.assertIn((o.id, "decision:demo:DEC-2026-08-02-01", "decisions_made"), edges)
        self.assertEqual([c.text for c in out.chunks], ["old style order", "refunds order\ndo refunds", "first task\nbuild it"])

    def test_decision_record_nodes_follow_toc_aliases(self):
        out = DecisionRecords([self.repo], self.vault).collect()
        edges = {(e.src, e.dst) for e in out.edges if e.kind == "member_of"}
        self.assertIn(("decision:demo:DEC-2026-08-02-01", "node:demo:orders.refunds"), edges)   # alias refund-alias → orders.refunds

    def test_retrospectives_indexed_outputs_not(self):
        # DEC-2026-10-30-06: retrospectives/ is cross-project knowledge (project vault); outputs/ holds regenerable bundles
        from kb.docrules import discover_kb_files
        w(self.vault / "retrospectives" / "r.md", "---\ntitle: r\nid: doc-vault-r\ntype: reference\ncreated: 2026-10-30\n---\n## 요약\n회고\n")
        w(self.vault / "outputs" / "retro" / "2026-10-30-x" / "decisions.md", "# 복사본\n")
        found = {rel: proj for _, rel, proj in discover_kb_files(self.vault)}
        self.assertEqual(found.get("retrospectives/r.md"), "vault")
        self.assertFalse(any(rel.startswith("outputs/") for rel in found))
        self.assertNotIn("retrospectives/r.md", {rel for _, rel, _ in discover_kb_files(self.vault, project="demo")})

    def test_orders_read_markdown_orders_too(self):
        out = Orders(self.vault).collect()
        ids = {n.id: n for n in out.nodes}
        self.assertIn("order:demo:2026.08.19-02", ids)
        self.assertEqual(ids["order:demo:2026.08.19-02"].title, "old style order")
        self.assertIn("order:demo:2026.09.05-01", ids)

    def test_rebuild_joins_both_providers(self):
        s = SqliteStore()
        s.rebuild([VaultScanner(self.vault), Orders(self.vault), DecisionRecords([self.repo], vault=self.vault)], kit_rev="t")
        self.assertEqual(len(s.query(kind="doc")), 4)   # refunds · old · patterns/p · TRACK_BOARD (undiscovered, no chunks)
        self.assertEqual(len(s.query(kind="session")), 1)
        self.assertEqual(len(s.query(kind="node")), 2)
        self.assertEqual(len(s.query(kind="decision")), 2)
        # join: which decisions does the spec reference, and does the referenced one still stand?
        spec = "doc:projects/demo/knowledge-base/domain/orders/refunds.md"
        decs = [s.get(e.dst) for e in s.neighbors(spec, kind="decisions_made")]
        self.assertEqual([(d.id, d.status) for d in decs], [("decision:demo:DEC-2026-08-01-01", "superseded")])
        # join: sessions that touched the topic node, via member_of
        touched = [e.src for e in s.neighbors("node:demo:orders.refunds", kind="member_of", direction="in")]
        self.assertIn("doc:projects/demo/sessions/session-2026-09-05-refunds.md", touched)
        self.assertIn("decision:demo:DEC-2026-08-01-01", touched)
        # text search spans docs and decisions in one ranking
        self.assertEqual({h.node.kind for h in s.search_text("d1")}, {"decision"})
        self.assertEqual([h.node.id for h in s.search_text("scope_key")], [spec])
        dangling = {e.dst for e in s.dangling_edges()}
        self.assertEqual(dangling, {"code:demo:paths:service/order-api/refunds/", "code:demo:symbols:RefundService", "ref:nowhere",
                                    "decision:other:DEC-2026-08-03-01"})   # another project's record is not in this fixture
        # session → order → task chain
        self.assertEqual([e.dst for e in s.neighbors("doc:projects/demo/sessions/session-2026-09-05-refunds.md", kind="orders")],
                         ["order:demo:2026.09.05-01"])
        self.assertEqual(len(s.query(kind="order")), 2)   # _order.yaml + the older _order.md
        self.assertEqual(len(s.query(kind="task")), 2)   # task-01.yaml node + the _order.md markdown under tasks/ (a task-kind document)


if __name__ == "__main__":
    unittest.main()
