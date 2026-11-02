"""kb design check (planning/design-stage acceptance 2, DEC-2026-11-01-07): screen tasks — a design_ref, or an order
that declares an entry_point — are checked for a missing design_ref, kind none without a reason, completion without
design_sync or with stale, and waived without reason · until or past it; other tasks are left alone."""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import design as D  # noqa: E402

TODAY = date(2026, 11, 1)


def w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def task(d: Path, name: str, ref: str = "", completion: str = "") -> Path:
    body = "task:\n  id: x\n"
    if ref:
        body += "inputs:\n  design_ref:\n" + "".join(f"    {l}\n" for l in ref.splitlines())
    if completion:
        body += "completion:\n" + "".join(f"  {l}\n" for l in completion.splitlines())
    return w(d / f"task-{name}.yaml", body)


class DesignCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ui = self.root / "01-ui"
        w(self.ui / "_order.yaml", "order:\n  id: o\n  entry_point: spec_first\n")
        self.plain = self.root / "02-api"
        w(self.plain / "_order.yaml", "order:\n  id: p\n")

    def tearDown(self):
        self.tmp.cleanup()

    def r(self, p):
        return D.check_task(p, TODAY)

    def test_non_screen_task_is_left_alone(self):
        self.assertEqual(self.r(task(self.plain, "a", completion="status: completed")), [])

    def test_missing_ref_under_entry_point(self):
        self.assertEqual(self.r(task(self.ui, "a")), ["no-design-ref"])

    def test_none_needs_reason(self):
        self.assertEqual(self.r(task(self.ui, "a", ref="kind: none")), ["none-no-reason"])
        self.assertEqual(self.r(task(self.ui, "b", ref="kind: none\nreason: text-only admin screen")), [])

    def test_completion_sync_states(self):
        ref = "kind: storybook\nref: button--primary"
        self.assertEqual(self.r(task(self.ui, "a", ref, "status: completed")), ["no-sync"])
        self.assertEqual(self.r(task(self.ui, "b", ref, "status: completed\ndesign_sync: stale")), ["stale"])
        self.assertEqual(self.r(task(self.ui, "c", ref, "status: completed\ndesign_sync: aligned")), [])
        self.assertEqual(self.r(task(self.ui, "d", ref, "status: completed\ndesign_sync: ok")), ["bad-sync"])
        self.assertEqual(self.r(task(self.ui, "e", ref, "status: blocked\ndesign_sync: stale")), [])   # not a done claim

    def test_waived_needs_reason_until_and_not_expired(self):
        ref = "kind: figma\nref: f"
        c = lambda reason: f"status: completed\ndesign_sync: waived\ndesign_sync_reason: \"{reason}\""
        self.assertEqual(self.r(task(self.plain, "a", ref, c("brand refresh pending until 2026-12-01"))), [])   # design_ref alone makes it a screen task
        self.assertEqual(self.r(task(self.ui, "b", ref, c("brand refresh pending"))), ["waived-no-until"])
        self.assertEqual(self.r(task(self.ui, "c", ref, c("until 2026-12-01"))), ["waived-no-until"])
        self.assertEqual(self.r(task(self.ui, "d", ref, c("brand refresh pending until 2026-10-01"))), ["waived-expired"])

    def test_cli_walks_folders_and_exits_1_on_problems(self):
        task(self.ui, "a")
        task(self.plain, "b")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(D.main(["check", str(self.root), "--today", "2026-11-01"]), 1)
        out = buf.getvalue()
        self.assertIn("task-a.yaml: design_ref 없음", out)
        self.assertIn("태스크 2 · 화면 태스크 1 · 문제 1", out)

    def test_markdown_is_not_read(self):
        w(self.root / "brief.md", "---\ntitle: b\ntype: design-brief\n---\n#1A2B3C\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(D.main(["check", str(self.root / "brief.md")]), 0)
        self.assertIn("태스크 0 · 화면 태스크 0 · 문제 0", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
