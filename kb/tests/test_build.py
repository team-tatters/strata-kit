"""build-index on the store: warnings · block exit · review inbox and transition · sortspec · manifest (legacy kb_node_model_test [1][7])."""
import io
import contextlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import build  # noqa: E402

TAXONOMY = """version: '1.0'
categories:
  domain: {order: 1, depth_limit: 2, defaults: {allowed_types: [specification, concept, guide, secret]}}
document_types:
  specification: {required_fields: [title, type, created, nodes]}
  concept: {}
  guide: {}
  session: {}
  secret: {indexed: false}
  node: {body_sections: [최종형상, 정책, 결정, 기획, 작업이력, 부채]}
lifecycle:
  statuses:
    active: {}
    review-needed: {}
    superseded: {required_fields: [superseded_by]}
  review_policy: {default_review_days: 90, exempt_types: [moc], auto_flag: true, fallback_to_created: true}
validation:
  category_type_check: {enabled: true, severity: warning, action: warn}
  required_fields_check: {enabled: true}
  depth_limit_check: {enabled: true, severity: error, action: block}
  lifecycle_transition_check: {enabled: true, severity: error, action: warn}
  node_id_check: {enabled: true}
  supersedes_symmetry_check: {enabled: true}
"""


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        p = self.vault / "projects" / "demo"
        self.p = p
        w(self.vault / "_meta" / "taxonomy.yaml", TAXONOMY)
        w(p / "_meta" / "toc.yaml", "version: '1.0'\nproject: demo\nnodes:\n  orders:\n    label: 주문\n    children:\n      refunds: {label: Refunds}\n")
        w(p / "knowledge-base" / "domain" / "orders" / "refunds.md",
          "---\ntitle: \"Refunds\"\nid: kb-demo-refunds\ntype: specification\nproject: demo\nstatus: active\ncreated: 2026-04-01\n"
          "updated: 2026-10-01\nnodes: [orders.refunds, orders.missing]\nsupersedes: [\"[[old]]\"]\npage_order: 2\n---\n## 본문\n")
        w(p / "knowledge-base" / "domain" / "orders" / "old.md",
          "---\ntitle: old\nid: kb-demo-old\ntype: concept\nproject: demo\nstatus: active\ncreated: 2026-01-01\npage_order: 1\n---\n## 개념\n")
        w(p / "knowledge-base" / "domain" / "orders" / "secret.md",
          "---\ntitle: secret\nid: kb-demo-secret\ntype: secret\nproject: demo\ncreated: 2026-01-01\n---\n숨김\n")
        w(p / "sessions" / "session-2026-09-05-x.md",
          "---\ntitle: s\nid: session-demo-2026-09-05-x\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-09-05\nnodes: [Bad Id]\n---\n## 완료\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = self.vault / ".kb" / "store.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, **kw):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = build.build(self.vault, self.store, project_dirs=[], **kw)
        return rc, buf.getvalue()

    def test_views_and_warnings(self):
        rc, out = self.run_build()
        self.assertEqual(rc, 0)
        self.assertIn("W projects/demo/knowledge-base/domain/orders/refunds.md: toc.yaml 에 없는 노드: 'orders.missing'", out)
        self.assertIn("W projects/demo/sessions/session-2026-09-05-x.md: 노드 id 형식 위반: 'Bad Id'", out)
        self.assertIn("'kb-demo-refunds' 가 이 문서를 supersedes 하지만 status 가 superseded 가 아님 (active)", out)
        self.assertIn("superseded_by 가 'kb-demo-refunds' 를 가리키지 않음 (대칭 깨짐)", out)
        self.assertIn("문서: 3개", out)            # secret.md is indexed: false
        self.assertIn("제외: 1", out)
        cand = json.loads((self.vault / ".kb" / "review-candidates.json").read_text(encoding="utf-8"))
        self.assertEqual([(c["file_path"], c["basis"]) for c in cand["candidates"]],
                         [("projects/demo/knowledge-base/domain/orders/old.md", "created")])
        inbox = (self.vault / "_index" / "review-needed.md").read_text(encoding="utf-8")
        self.assertIn("- [[old]] — ", inbox)
        sortspec = (self.p / "knowledge-base" / "sortspec.md").read_text(encoding="utf-8")
        self.assertIn("  target-folder: projects/demo/knowledge-base/domain/orders\n  old\n  refunds\n", sortspec)
        self.assertTrue((self.p / "nodes" / "orders.refunds.md").is_file())
        manifest = json.loads((self.vault / ".kb" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["files"]["projects/demo/knowledge-base/domain/orders/secret.md"]["title"], "(skipped)")
        self.assertEqual(manifest["files"]["projects/demo/knowledge-base/domain/orders/refunds.md"]["updated"], "2026-10-01")
        self.assertEqual(manifest["stats"]["documents"], 3)
        self.assertEqual(len(manifest["files"]), 4)
        rc2, out2 = self.run_build()
        self.assertIn("변경없음: 3", out2)       # the manifest now knows every file

    def test_apply_review_transitions_and_rebuilds(self):
        self.run_build()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            n = build.apply_review(self.vault)
        self.assertEqual(n, 1)
        self.assertIn("status: review-needed", (self.p / "knowledge-base" / "domain" / "orders" / "old.md").read_text(encoding="utf-8"))
        rc, out = self.run_build()
        self.assertNotIn("리뷰 필요 후보", out)

    def test_block_violation_exits_2(self):
        w(self.p / "knowledge-base" / "domain" / "orders" / "deep" / "x.md",
          "---\ntitle: deep\nid: kb-demo-deep\ntype: guide\nproject: demo\ncreated: 2026-10-01\n---\n## x\n")
        rc, out = self.run_build()
        self.assertEqual(rc, 2)
        self.assertIn("BLOCK 위반: 1건", out)
        self.assertIn("E projects/demo/knowledge-base/domain/orders/deep/x.md: 'domain' 최대 depth 2, 현재 3", out)


if __name__ == "__main__":
    unittest.main()
