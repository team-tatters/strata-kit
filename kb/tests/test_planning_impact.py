"""Planning impact assessment (DEC-2026-11-01-16): from the planning's topic nodes (and their child nodes) to the
specifications, the code they cover, the code one hop away and its tests, the decisions on those nodes (superseded
apart) and other planning on the same nodes; a bundle gets audit/impact.md, a single document is printed only."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import planning_impact as PI  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.providers.code_graph import CodeGraph  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PlanningImpactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        p = self.vault / "projects" / "demo"
        w(p / "_meta" / "toc.yaml", "nodes:\n  billing:\n    label: 청구\n    children:\n      refund:\n        label: 환불\n  other:\n    label: 기타\n")
        w(p / "knowledge-base" / "billing" / "refund.md",
          "---\ntitle: 환불\nid: kb-demo-refund\ntype: specification\nproject: demo\ncreated: 2026-10-01\nstatus: active\n"
          "nodes: [billing.refund]\ncovers:\n  paths: [\"tools/refund/\"]\n---\n## 본문\nx\n")
        w(p / "knowledge-base" / "other" / "x.md",
          "---\ntitle: 기타\nid: kb-demo-x\ntype: specification\nproject: demo\ncreated: 2026-10-01\nnodes: [other]\ncovers:\n  paths: [\"tools/other/\"]\n---\n## 본문\ny\n")
        for n, title, nodes, sup in (("DEC-2026-10-01-01", "환불 창구", "[billing.refund]", "[]"),
                                     ("DEC-2026-10-02-01", "환불 창구 바꿈", "[billing]", "[\"[[DEC-2026-10-01-01]]\"]"),
                                     ("DEC-2026-10-03-01", "기타", "[other]", "[]")):
            w(p / "decisions" / f"{n}.md", f"---\ntitle: \"{n} — {title}\"\naliases: [{n}]\nstatus: active\ncreated: 2026-10-0{n[-4]}\n"
              f"nodes: {nodes}\nsupersedes: {sup}\n---\n")
        self.bundle = p / "planning" / "partial-refund"
        w(self.bundle / "audit" / "facts.md", "| # | 위치 | 유형 | 내용 | 역할 | 축 | 하위 |\n|---|---|---|---|---|---|---|\n")
        w(self.bundle / "prd.md", "---\ntitle: 부분 환불 PRD\ntype: planning\nplanning_doc: prd\nnodes: [billing]\n---\n# PRD\n")
        w(p / "planning" / "older" / "refund-window.md", "---\ntitle: 환불 기한\ntype: planning\nstatus: planned\nnodes: [billing.refund]\n---\n# x\n")
        w(p / "planning" / "older" / "unrelated.md", "---\ntitle: 무관\ntype: planning\nnodes: [other]\n---\n# y\n")
        repo = root / "demo"
        w(repo / "tools" / "refund" / "calc.py", "def calc():\n    pass\n")
        w(repo / "tools" / "api" / "handler.py", "from tools.refund.calc import calc\n")
        w(repo / "tools" / "api" / "far.py", "from tools.api.handler import x\n")
        w(repo / "tools" / "refund" / "test_calc.py", "from tools.refund.calc import calc\n")
        w(repo / "tools" / "other" / "o.py", "X = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        self.old = os.environ.get("STRATA_VAULT")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore(":memory:")
        self.store.rebuild([VaultScanner(self.vault), CodeGraph([repo])], kit_rev="t")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STRATA_VAULT", None)
        else:
            os.environ["STRATA_VAULT"] = self.old
        self.tmp.cleanup()

    def test_bundle_gathers_from_nodes_and_children(self):
        r = PI.assess(self.vault, self.store, self.bundle)
        self.assertTrue(r["bundle"])
        self.assertEqual(r["scope"], ["billing", "billing.refund"])
        self.assertEqual([s["doc"].split("/")[-1] for s in r["specs"]], ["refund.md"])
        self.assertIn("tools/refund/calc.py", r["files"])
        self.assertNotIn("tools/other/o.py", r["files"])
        deps = [d["file"] for d in r["dependents"]]
        self.assertIn("tools/api/handler.py", deps)
        self.assertNotIn("tools/api/far.py", deps)            # depth 1
        self.assertIn("tools/refund/test_calc.py", r["tests"])
        decs = {d["rec"]: d["superseded"] for d in r["decisions"]}
        self.assertEqual(decs, {"DEC-2026-10-02-01": False, "DEC-2026-10-01-01": True})
        self.assertEqual([o["path"].split("/")[-1] for o in r["others"]], ["refund-window.md"])
        deeper = PI.assess(self.vault, self.store, self.bundle, depth=2)
        self.assertIn("tools/api/far.py", [d["file"] for d in deeper["dependents"]])

    def test_render_and_write_to_bundle_audit(self):
        r = PI.assess(self.vault, self.store, self.bundle)
        text = PI.render(r, date(2026, 11, 1))
        self.assertIn("GENERATED", text)
        self.assertIn("명세 1 · 맡은 코드", text)
        self.assertIn("[[refund]]", text)
        self.assertIn("대체된 결정 1: [[DEC-2026-10-01-01]]", text)
        from kb.planning import layer_of, split_frontmatter
        out = self.bundle / "audit" / "impact.md"
        out.write_text(text, encoding="utf-8")
        fm, _, _ = split_frontmatter(text)
        self.assertEqual(layer_of(str(out.relative_to(self.vault)), fm, self.vault), "audit")   # never injected

    def test_single_document_and_missing_nodes(self):
        doc = self.vault / "projects" / "demo" / "planning" / "older" / "refund-window.md"
        r = PI.assess(self.vault, self.store, doc)
        self.assertFalse(r["bundle"])
        self.assertEqual(r["scope"], ["billing.refund"])
        w(self.bundle / "prd.md", "---\ntitle: 부분 환불 PRD\ntype: planning\nnodes: [billing, nowhere]\n---\n# PRD\n")
        r = PI.assess(self.vault, self.store, self.bundle)
        self.assertEqual(r["unknown_nodes"], ["nowhere"])
        self.assertIn("toc.yaml 에 없는 노드", PI.render(r, date(2026, 11, 1)))
        w(self.bundle / "prd.md", "---\ntitle: 부분 환불 PRD\ntype: planning\n---\n# PRD\n")
        r = PI.assess(self.vault, self.store, self.bundle)
        self.assertIn("평가할 출발점이 없다", PI.render(r, date(2026, 11, 1)))
        with self.assertRaises(ValueError):
            PI.assess(self.vault, self.store, self.vault / "projects" / "demo" / "knowledge-base" / "billing" / "refund.md")


if __name__ == "__main__":
    unittest.main()
