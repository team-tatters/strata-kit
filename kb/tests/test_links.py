import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import links  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        kb = self.vault / "projects" / "p" / "knowledge-base"
        w(kb / "new.md", "---\nid: kb-p-new\nstatus: active\n---\n# new\n")
        w(kb / "old.md", "---\nid: kb-p-old\nstatus: superseded\nsuperseded_by: \"[[new]]\"\n---\n# old\n")
        w(self.vault / "projects" / "p" / "tasks" / "2026.01.01" / "01-x" / "_order.md", "---\nid: order-p-2026.01.01-01\naliases: [\"2026.01.01-01\"]\n---\n")
        w(kb / "guide.md", "---\nid: kb-p-guide\nstatus: active\n---\n"
          "정상 [[new]] · 표 이스케이프 [[new\\|새 문서]] · 상대 [[../knowledge-base/new]] · 문서 내부 [[#제목]]\n"
          "깨짐 [[없는 문서]] · id 전용 [[kb-p-new]] · 태스크 id [[2026.01.01-01]] · 대체된 문서 [[old]]\n"
          "`[[코드 안은 무시]]`\n```\n[[펜스 안도 무시]]\n```\n마크다운 [있음](new.md) · [없음](gone.md) · [외부](https://x.y/z) · [그림](../img.png)\n")
        w(self.vault / "projects" / "p" / "img.png", "x")
        w(self.vault / "TRACK_BOARD.md", "# board\n[[없는 보드 링크]] [[guide]]\n")
        w(self.vault / "projects" / "p" / "decisions" / "DEC-2026-01-01-01.md", "---\ntype: decision\n---\n[[없는 결정 링크]]\n")
        w(self.vault / "projects" / "q" / "knowledge-base" / "guide.md", "---\nid: kb-q-guide\n---\n[[guide]] 는 같은 프로젝트의 나를 가리킨다\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scanner_emits_doc_nodes_for_every_markdown_and_link_edges(self):
        board = self.store.get("doc:TRACK_BOARD.md")
        self.assertEqual((board.kind, board.project, board.payload["indexed"]), ("doc", "vault", False))
        dec = self.store.get("doc:projects/p/decisions/DEC-2026-01-01-01.md")
        self.assertTrue(dec.payload["generated"])
        self.assertEqual(self.store.chunks_of("doc:TRACK_BOARD.md"), [])     # no chunks for non-indexed docs
        refs = {(e.dst, e.source_ref) for e in self.store.neighbors("doc:projects/p/knowledge-base/guide.md", kind="links")}
        self.assertIn(("doc:projects/p/knowledge-base/new.md", "wiki:file:new"), refs)
        self.assertIn(("doc:projects/p/knowledge-base/new.md", "wiki:file:../knowledge-base/new"), refs)
        self.assertIn(("ref:없는 문서", "wiki:none:없는 문서"), refs)
        self.assertIn(("doc:projects/p/knowledge-base/new.md", "wiki:id:kb-p-new"), refs)
        self.assertIn(("doc:projects/p/tasks/2026.01.01/01-x/_order.md", "wiki:alias:2026.01.01-01"), refs)
        self.assertIn(("doc:projects/p/knowledge-base/gone.md", "md:none:gone.md"), refs)
        self.assertIn(("file:projects/p/img.png", "md:file:../img.png"), refs)
        self.assertFalse(any("코드" in r[1] or "펜스" in r[1] or "#제목" in r[1] or "x.y" in r[1] for r in refs))
        # same-project preference: q's [[guide]] resolves to q's guide, not p's
        q = {e.dst for e in self.store.neighbors("doc:projects/q/knowledge-base/guide.md", kind="links")}
        self.assertEqual(q, {"doc:projects/q/knowledge-base/guide.md"})

    def test_check_classifies_like_legacy(self):
        v = links.check(self.store)
        got = {(x["file"], x["type"], x["target"], x["hint"]) for x in v}
        g = "projects/p/knowledge-base/guide.md"
        self.assertEqual(got, {
            (g, "broken", "없는 문서", ""),
            (g, "id-only", "kb-p-new", "파일명 new 로 바꿀 것"),
            (g, "alias-only", "2026.01.01-01", "파일명 _order 로 바꿀 것"),
            (g, "superseded-target", "old", "현행 문서: [[new]]"),
            (g, "md-link", "gone.md", ""),
            ("TRACK_BOARD.md", "broken", "없는 보드 링크", ""),
            ("projects/p/decisions/DEC-2026-01-01-01.md", "broken", "없는 결정 링크", ""),
        })
        self.assertEqual({x["type"] for x in v if not links.blocking(x)}, {"superseded-target", "broken"})
        self.assertEqual(sorted(x["file"] for x in v if not links.blocking(x)), sorted([g, "projects/p/decisions/DEC-2026-01-01-01.md"]))
        self.assertEqual([x["target"] for x in links.check(self.store, project="q")], [])

    def test_main_baseline_flow_and_store_mirror(self):
        store_path = Path(self.tmp.name) / "store.sqlite"
        SqliteStore(store_path).rebuild([VaultScanner(self.vault)], kit_rev="t")
        base = Path(self.tmp.name) / "baseline.json"
        os.environ["KB_NO_REFRESH"] = "1"
        try:
            self.assertEqual(links.main(["--db", str(store_path), "--baseline", str(base)]), 1)      # new violations
            self.assertEqual(links.main(["--db", str(store_path), "--baseline", str(base), "--write-baseline"]), 0)
            keys = set(json.loads(base.read_text())["violations"])
            self.assertEqual(len(keys), 5)                                                            # blocking only
            self.assertEqual(SqliteStore(store_path).baselines("link"), keys)
            self.assertEqual(links.main(["--db", str(store_path), "--baseline", str(base)]), 0)
            # fix one → shrink removes it from the file and the mirror
            (self.vault / "projects" / "p" / "knowledge-base" / "gone.md").write_text("# here\n")
            SqliteStore(store_path).rebuild([VaultScanner(self.vault)], kit_rev="t")
            self.assertEqual(links.main(["--db", str(store_path), "--baseline", str(base), "--shrink-baseline"]), 0)
            self.assertEqual(len(json.loads(base.read_text())["violations"]), 4)
            self.assertEqual(len(SqliteStore(store_path).baselines("link")), 4)
            self.assertEqual(links.main(["--db", str(store_path), "--baseline", str(base), "--project", "p", "--write-baseline"]), 2)
        finally:
            del os.environ["KB_NO_REFRESH"]


if __name__ == "__main__":
    unittest.main()
