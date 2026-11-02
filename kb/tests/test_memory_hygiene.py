"""Memory hygiene (planning/memory-hygiene acceptance 3·4·5, DEC-2026-10-31-13~19·34): one memory directory in, names,
reasons and evidence out; the directory is left byte for byte as it was, a rule that names a state is shown as a match
only, contradiction candidates pair feedback facts of the same directory, and the index is compared with the files."""
import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import hygiene  # noqa: E402
from kb.gates import memory_hygiene as mh  # noqa: E402


def fact(name, typ, body, desc="", **meta):
    extra = "".join(f"  {k}: {v}\n" for k, v in meta.items())
    return f"---\nname: {name}\ndescription: {desc or name}\nmetadata:\n  type: {typ}\n{extra}---\n\n{body}\n"


class MemoryHygieneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mem = Path(self.tmp.name) / "memory"
        self.mem.mkdir()
        files = {
            "rule.md": fact("vault-sync-rule", "project", "다른 세션의 미커밋 파일이 있으면 임시 복제본에서 자기 커밋만 push 한다.", verified="2026-10-20"),
            "state.md": fact("order-progress", "project", "오더 3 은 진행 중이다.\n다음은 task-04.", modified="2026-07-01T00:00:00Z"),
            "nodate.md": fact("old-note", "reference", "참고 링크"),
            "fb-a.md": fact("commit-trailer", "feedback", "커밋 메시지에 서명 트레일러를 넣지 않는다.", desc="커밋 서명 트레일러 규칙", verified="2026-10-30"),
            "fb-b.md": fact("commit-trailer-ok", "feedback", "커밋 메시지에 서명 트레일러를 넣는다.", desc="커밋 서명 트레일러 허용", verified="2026-10-30"),
            "raw.md": "그냥 메모\n",
        }
        for n, t in files.items():
            (self.mem / n).write_text(t, encoding="utf-8")
        (self.mem / "MEMORY.md").write_text("".join(f"- [{n}]({n}) — x\n" for n in files if n != "raw.md") + "- [gone](gone.md) — x\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def digest(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.mem.iterdir())}

    def test_reasons_and_read_only(self):
        before = self.digest()
        r = mh.report(self.mem, today=date(2026, 10, 31), days=60)
        self.assertEqual(self.digest(), before)                                   # acceptance 3: nothing changed
        by = {c["name"]: {x["kind"]: x["evidence"] for x in c["reasons"]} for c in r["candidates"]}
        self.assertEqual(set(by["order-progress"]), {"stale", "status_words"})
        self.assertIn("modified 2026-07-01", by["order-progress"]["stale"])
        self.assertIn("'진행 중'", by["order-progress"]["status_words"])
        self.assertEqual(set(by["vault-sync-rule"]), {"status_words"})            # acceptance 4: a rule matches, no verdict
        self.assertIn("표현 일치", by["vault-sync-rule"]["status_words"])
        self.assertIn("no_date", by["old-note"])
        self.assertIn("unknown", by["raw"])
        self.assertEqual((r["index_only"], r["file_only"]), (["gone.md"], ["raw.md"]))

    def test_contradiction_pairs_are_feedback_only(self):
        r = mh.report(self.mem, today=date(2026, 10, 31), days=60)
        self.assertEqual(len(r["pairs"]), 1)                                      # acceptance 5
        p = r["pairs"][0]
        self.assertEqual({p["a"], p["b"]}, {"commit-trailer", "commit-trailer-ok"})
        self.assertIn("트레일러", p["shared"])

    def test_render_has_no_body_and_index_budget_warns(self):
        (self.mem / "MEMORY.md").write_text("x" * (13 * 1024), encoding="utf-8")
        text = "\n".join(mh.render(mh.report(self.mem, today=date(2026, 10, 31), days=60)))
        self.assertIn("12288B 초과", text)
        self.assertNotIn("task-04", text)                                         # names and evidence only, never the body
        self.assertNotIn("임시 복제본", text)

    def test_cli_and_directory_name(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(hygiene.main(["--memory", str(self.mem)]), 0)
        self.assertIn("상태성 표현", out.getvalue())
        self.assertEqual(mh.memory_dir_for(Path("/work/alice/shop_web"), home=Path("/h")),
                         Path("/h/.claude/projects/-work-alice-shop-web/memory"))


if __name__ == "__main__":
    unittest.main()
