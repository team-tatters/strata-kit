import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.retro import build_bundle, write_bundle  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dec(repo: Path, rid: str, slug: str, extra: str = "") -> None:
    w(repo / ".strata" / "decisions" / f"{rid}-{slug}.yaml",
      f"decision:\n  id: {rid}\n  date: '{rid[4:14]}'\n  topic: {slug} topic\n  decision: {slug} 결론\n  reason: {slug} 이유\n{extra}")


class RetroBundleTest(unittest.TestCase):
    """Order 2026.10.30-03 task-02 — acceptance 1~5 of planning/retro-flow."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault, self.repo = root / "vault", root / "demo"
        p = self.vault / "projects" / "demo"
        w(self.repo / ".strata" / "profile.yaml", "profile: embedded\nproject: demo\n")
        dec(self.repo, "DEC-2026-09-01-01", "old", "  nodes: [kb]\n")
        dec(self.repo, "DEC-2026-10-10-01", "new",
            "  supersedes: [DEC-2026-09-01-01]\n  nodes: [kb.search]\n  alternatives:\n    - \"색인 밖: 찾지 못해 짐\"\n"
            "  background:\n    - \"NotebookLM 학습 방식\"\n")
        dec(self.repo, "DEC-2026-10-12-01", "plain", "  nodes: [skills]\n  affects: [\"[[reviews/r1]] 대응\"]\n")
        dec(self.repo, "DEC-2026-11-02-01", "later")
        w(p / "sessions" / "session-2026-10-11-a.md",
          "---\ntitle: session a\ntype: session\nproject: demo\ncreated: 2026-10-11\nnodes: [kb]\n---\n# a\n\n## 판단 과정\n\n"
          "[[DEC-2026-10-10-01]] 을 두고 [[reviews/r1|1차 리뷰]] 와 [[nowhere]] 를 봤다. 그래프 탐색.\n\n```yaml\n# 주석\nk: v\n```\n")
        w(p / "sessions" / "session-2026-08-01-old.md",
          "---\ntitle: session old\ntype: session\ncreated: 2026-08-01\n---\n# old\n")
        w(p / "reviews" / "r1.md",
          "---\ntitle: 교차 검증 1차\ntype: review\nreceived: 2026-10-12\nreview_of: demo abc\nsource: 외부\nnodes: [skills]\n---\n"
          "# r1\n\n## 대응 요약\n\n받아들임\n")
        w(p / "decisions" / "DEC-2026-10-10-01.md", "---\ntitle: 'DEC-2026-10-10-01 — new topic'\ntype: decision\n---\n")
        w(p / "measurements" / "strata-metrics.yaml",
          "project: demo\ncollected: '2026-10-20T00:00:00+00:00'\nrevisions:\n  aaa: {date: '2026-10-11', verify: [ok]}\n"
          "  bbb: {date: '2026-07-01', verify: [ok]}\n")

    def tearDown(self):
        self.tmp.cleanup()

    def bundle(self, **kw):
        return build_bundle(self.vault, "demo", date(2026, 10, 1), date(2026, 10, 31), project_dir=self.repo, **kw)

    def test_period_selects_each_kind_and_toc(self):
        files = self.bundle()
        self.assertEqual(sorted(files), ["00-목차.md", "01-결정.md", "02-리뷰.md", "03-세션.md", "04-측정.md"])
        self.assertIn("DEC-2026-10-10-01", files["01-결정.md"])
        self.assertNotIn("## DEC-2026-11-02-01", files["01-결정.md"])
        self.assertNotIn("## DEC-2026-09-01-01", files["01-결정.md"])
        self.assertIn("session a", files["03-세션.md"])
        self.assertNotIn("session old", files["03-세션.md"])
        self.assertIn("aaa", files["04-측정.md"])
        self.assertNotIn("bbb", files["04-측정.md"])
        self.assertIn("2026-10-01", files["00-목차.md"])

    def test_decision_has_alternatives_background_and_chain(self):
        d = self.bundle()["01-결정.md"]
        new = d.split("## DEC-2026-10-10-01")[1].split("\n## ")[0]
        for text in ("new 결론", "new 이유", "색인 밖: 찾지 못해 짐", "NotebookLM 학습 방식", "DEC-2026-09-01-01", "old topic"):
            self.assertIn(text, new)
        plain = d.split("## DEC-2026-10-12-01")[1]
        self.assertNotIn("### 진 대안", plain)          # no empty sections for old records
        self.assertNotIn("### 배경", plain)

    def test_files_stand_alone(self):
        files = self.bundle()
        for name, text in files.items():
            self.assertNotIn("[[", text, name)
        s = files["03-세션.md"]
        self.assertIn("DEC-2026-10-10-01 — new topic", s)   # wikilink → target title
        self.assertIn("1차 리뷰", s)                         # alias kept
        self.assertIn("nowhere", s)                          # unresolved → plain text
        self.assertIn("#### 판단 과정", s)                  # outline kept under the session heading
        self.assertIn("\n# 주석\n", s)                       # code block comments are not headings
        self.assertIn("교차 검증 1차", files["01-결정.md"])   # links inside decision records too

    def test_node_and_query_filters(self):
        files = self.bundle(node="kb")
        self.assertIn("DEC-2026-10-10-01", files["01-결정.md"])        # kb.search is under kb
        self.assertNotIn("## DEC-2026-10-12-01", files["01-결정.md"])
        self.assertNotIn("교차 검증 1차", files["02-리뷰.md"])
        files = self.bundle(query="그래프")
        self.assertIn("session a", files["03-세션.md"])
        self.assertNotIn("## DEC-2026-10-12-01", files["01-결정.md"])

    def test_rerun_identical_and_existing_dir_refused(self):
        self.assertEqual(self.bundle(), self.bundle())
        out = self.vault / "outputs" / "retro" / "x"
        self.assertEqual(write_bundle(out, self.bundle())["result"], "written")
        (out / "note.txt").write_text("keep", encoding="utf-8")
        self.assertEqual(write_bundle(out, self.bundle())["result"], "exists")
        self.assertEqual(write_bundle(out, self.bundle(), force=True)["result"], "written")
        self.assertTrue((out / "note.txt").is_file())                    # never deletes what it did not write

    def test_bundle_not_indexed(self):
        from kb.providers import VaultScanner
        write_bundle(self.vault / "outputs" / "retro" / "x", self.bundle())
        ids = {n.id for n in VaultScanner(self.vault).collect().nodes}
        self.assertFalse(any(i.startswith("doc:outputs/") for i in ids))


class RetroFocusTest(RetroBundleTest):
    """Order 2026.10.30-04 task-01 — acceptance 1~4 of planning/retro-focus (DEC-2026-10-30-07)."""

    def setUp(self):
        super().setUp()
        p = self.vault / "projects" / "demo"
        dec(self.repo, "DEC-2026-11-05-01", "newest", "  supersedes: [DEC-2026-10-10-01]\n")
        w(p / "reviews" / "r2.md", "---\ntitle: 교차 검증 2차\ntype: review\nreceived: 2026-12-01\n"
          "decisions_made: [DEC-2026-09-01-01]\n---\n# r2\n")
        w(p / "sessions" / "session-2026-11-05-b.md", "---\ntitle: session b\ntype: session\ncreated: 2026-11-05\n"
          "decisions_made: [DEC-2026-11-05-01]\n---\n# b\n")
        dec(self.repo, "DEC-2026-11-06-01", "colon", "  supersedes: [DEC-2026-11-05-01]\n")
        rec = self.repo / ".strata" / "decisions" / "DEC-2026-11-06-01-colon.yaml"
        rec.write_text(rec.read_text(encoding="utf-8").replace("topic: colon topic", "topic: '짧은 제목: 긴 설명이 뒤에 붙는다'"), encoding="utf-8")

    def focus(self, rid="DEC-2026-10-10-01", **kw):
        return build_bundle(self.vault, "demo", None, None, project_dir=self.repo, decision=rid, **kw)

    def test_decision_chain_both_ways_only(self):
        d = self.focus()["01-결정.md"]
        for rid in ("DEC-2026-09-01-01", "DEC-2026-10-10-01", "DEC-2026-11-05-01"):
            self.assertIn(f"## {rid}", d)
        for rid in ("DEC-2026-10-12-01", "DEC-2026-11-02-01"):
            self.assertNotIn(f"## {rid}", d)
        self.assertEqual(self.focus("DEC-2026-09-01-01")["01-결정.md"].count("\n## DEC-"), 4)   # several steps from the other end

    def test_docs_linked_to_chain_without_period(self):
        files = self.focus()
        self.assertIn("교차 검증 2차", files["02-리뷰.md"])          # decisions_made names the chain, outside any period
        self.assertNotIn("## 교차 검증 1차", files["02-리뷰.md"])
        self.assertIn("session b", files["03-세션.md"])              # decisions_made names the chain
        self.assertNotIn("session a", files["03-세션.md"])           # body mention only — DEC-2026-10-31-01
        self.assertNotIn("session old", files["03-세션.md"])

    def test_toc_lists_items_with_facts_not_conclusions(self):
        toc = self.focus()["00-목차.md"]
        self.assertIn("## 항목", toc)
        self.assertIn("DEC-2026-10-10-01 — new topic", toc)
        self.assertIn("2026-10-10", toc)
        self.assertIn("DEC-2026-11-05-01(newest topic) 에 대신됨", toc)        # ids carry their titles
        self.assertIn("DEC-2026-11-06-01(짧은 제목) 에 대신됨", toc)            # the title before ': ', not the whole topic
        self.assertIn("결정 DEC-2026-11-05-01(newest topic)", toc.split("session b")[1].split("\n")[0])
        self.assertIn("리뷰 1", toc.split("DEC-2026-09-01-01 — old topic")[1].split("\n")[0])
        self.assertNotIn("new 결론", toc)
        self.assertIn("교차 검증 2차", toc)
        self.assertNotIn("session a", toc)
        self.assertIn("## 항목", self.bundle()["00-목차.md"])       # the period bundle lists items too

    def test_colliding_titles_are_told_apart(self):
        # MB-strata-kit-2026-032: two decisions whose topics share the part before ': ' read the same in the list
        dec(self.repo, "DEC-2026-11-07-01", "twin", "  supersedes: [DEC-2026-11-06-01]\n")
        rec = self.repo / ".strata" / "decisions" / "DEC-2026-11-07-01-twin.yaml"
        rec.write_text(rec.read_text(encoding="utf-8").replace("topic: twin topic", "topic: '짧은 제목: 다른 설명 — 꼬리'"), encoding="utf-8")
        toc = self.focus()["00-목차.md"]
        self.assertIn("DEC-2026-11-06-01(짧은 제목: 긴 설명이 뒤에 붙는다) 를 대신함", toc)
        self.assertIn("DEC-2026-11-07-01(짧은 제목: 다른 설명) 에 대신됨", toc)
        self.assertIn("DEC-2026-11-05-01(newest topic) 에 대신됨", toc)       # labels that do not collide stay short

    def test_needs_period_or_decision(self):
        from kb.retro import main
        import os
        os.environ["STRATA_VAULT"] = str(self.vault)
        with self.assertRaises(SystemExit) as cm:
            main(["--project", "demo"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
