"""Store-backed node pages: six faces, decision chain, debts, idempotence (the legacy kb_node_model_test [6] cases)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402
from kb.views import node_pages  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class NodePagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        p = self.vault / "projects" / "demo"
        w(self.vault / "_meta" / "taxonomy.yaml",
          "version: '1.0'\ncategories:\n  domain: {order: 1}\ndocument_types:\n  node:\n    body_sections: [최종형상, 정책, 결정, 기획, 작업이력, 부채]\n")
        w(p / "_meta" / "toc.yaml", "version: '1.0'\nproject: demo\nnodes:\n  orders:\n    label: 주문\n    order: 1\n"
                                     "    children:\n      refunds:\n        label: Refunds\n        order: 1\n        aliases: [refund-alias]\n")
        w(p / "knowledge-base" / "domain" / "orders" / "refunds.md",
          "---\ntitle: \"Refunds\"\nid: kb-demo-refunds\ntype: specification\nproject: demo\nstatus: active\ncreated: 2026-04-01\n"
          "updated: 2026-08-20\nnodes: [orders.refunds, orders.missing]\n---\n## 본문\n")
        w(p / "knowledge-base" / "domain" / "orders" / "old.md",
          "---\ntitle: old\nid: kb-demo-old\ntype: concept\nproject: demo\ncreated: 2026-01-01\nnodes: [orders.refunds]\n---\n## 개념\n")
        w(p / "sessions" / "session-2026-09-05-refunds-refactor.md",
          "---\ntitle: s3\nid: session-demo-2026-09-05-refunds-refactor\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-09-05\n"
          "nodes: [refund-alias]\ndoc_change: none\ndoc_change_reason: \"리팩터링만\"\n---\n## 완료\n")
        w(p / "sessions" / "session-2026-09-06-undeclared.md",
          "---\ntitle: s4\nid: session-demo-2026-09-06-undeclared\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-09-06\n"
          "nodes: [orders.refunds]\n---\n## 완료\n")
        w(p / "decisions" / "DEC-2026-08-01-01.md",
          "---\ntitle: \"DEC-2026-08-01-01 — 산정식 v1\"\nid: dec-demo-2026-08-01-01\ntype: decision\nproject: demo\nstatus: superseded\n"
          "created: 2026-08-01\naliases: [DEC-2026-08-01-01]\nnodes: [orders.refunds]\nsuperseded_by: \"[[DEC-2026-09-01-01]]\"\n---\n# x\n")
        w(p / "decisions" / "DEC-2026-09-01-01.md",
          "---\ntitle: \"DEC-2026-09-01-01 — 산정식 v2\"\nid: dec-demo-2026-09-01-01\ntype: decision\nproject: demo\nstatus: active\n"
          "created: 2026-09-01\naliases: [DEC-2026-09-01-01]\nnodes: [orders.refunds]\nsupersedes: [\"[[DEC-2026-08-01-01]]\"]\n---\n# y\n")
        w(p / "planning" / "notion-x" / "기획-a--abcd1234.md",
          "---\ntitle: \"기획 A\"\nid: plan-demo-abcd\ntype: planning\nproject: demo\nstatus: realized\nnodes: [orders.refunds]\n"
          "implementation:\n  status: diverged\n  reviewed: 2026-09-09\n  spec: \"[[kb-demo-refunds]]\"\ncreated: 2026-09-09\n---\n# 기획 A\n")
        w(p / "planning" / "notion-x" / "기획-b--efgh5678.md",
          "---\ntitle: \"기획 B\"\nid: plan-demo-efgh\ntype: planning\nproject: demo\nstatus: requested\nnodes: [orders.refunds]\n"
          "implementation:\n  status: unreviewed\ncreated: 2026-09-09\n---\n# 기획 B\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore(":memory:")
        self.store.rebuild([VaultScanner(self.vault)])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_project_docs_follow_legacy_order_and_fields(self):
        docs = node_pages.project_docs(self.store, "demo")
        self.assertEqual([d["created"] for d in docs], sorted([d["created"] for d in docs], reverse=True))
        spec = next(d for d in docs if d["stem"] == "refunds")
        self.assertEqual((spec["type"], spec["status"], spec["updated"], spec["category"]), ("specification", "active", "2026-08-20", "domain"))
        self.assertEqual(spec["nodes"], ["orders.refunds", "orders.missing"])
        sess = next(d for d in docs if d["stem"].startswith("session-2026-09-05"))
        self.assertEqual((sess["category"], sess["doc_change"], sess["updated"]), ("archive", "none", ""))

    def test_pages_join_six_faces_and_are_idempotent(self):
        w1, u1, r1, n = node_pages.generate_all(self.vault, self.store, quiet=True)
        self.assertEqual((n, r1), (1, 0))
        page = (self.vault / "projects" / "demo" / "nodes" / "orders.refunds.md").read_text(encoding="utf-8")
        for needle in ("**[[DEC-2026-09-01-01]] (현행)** 2026-09-01 — 산정식 v2 ← supersedes [[DEC-2026-08-01-01]]",
                       "[[DEC-2026-08-01-01]] (대체됨)",
                       "형상 미갱신 선언(사유 있음)",
                       "[[session-2026-09-06-undeclared]] (2026-09-06) 이 노드를 다뤘으나 최종형상(updated 2026-08-20) 미갱신, doc_change 선언 없음.",
                       "[[refunds]] covers 없음 — 커버리지 게이트",
                       "## 기획",
                       "**기획과 다름** [[기획-a--abcd1234]] — 기획 A (기획 realized, reviewed 2026-09-09, spec [[kb-demo-refunds]])",
                       "**미검토** [[기획-b--efgh5678]]",
                       "기획 문서 1건 구현 검토 전",
                       "기획과 구현이 다름(기획과 다름)"):
            self.assertIn(needle, page)
        index = (self.vault / "projects" / "demo" / "nodes" / "_index.md").read_text(encoding="utf-8")
        self.assertIn("| 노드 | 형상 | 정책 | 결정 | 기획 | 이력 | 부채 |", index)
        self.assertIn("| 　[[orders.refunds\\|Refunds]] | 2 | 0 | 2 | 2 | 2 | 5 |", index)   # 형상 2(spec+concept) · 결정 2 · 기획 2 · 이력 2 · 부채 5
        w2, u2, r2, _ = node_pages.generate_all(self.vault, self.store, quiet=True)
        self.assertEqual((w2, r2), (0, 0))
        self.assertEqual(u2, w1 - 1)   # pages written once are unchanged on the second run; the index is not counted (legacy)

    def test_pages_removed_when_toc_disappears(self):
        node_pages.generate_all(self.vault, self.store, quiet=True)
        (self.vault / "projects" / "demo" / "_meta" / "toc.yaml").unlink()
        self.store.rebuild([VaultScanner(self.vault)])
        node_pages.generate_all(self.vault, self.store, quiet=True)   # legacy quirk kept: the removal count is reported, not returned
        self.assertFalse(list((self.vault / "projects" / "demo" / "nodes").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
