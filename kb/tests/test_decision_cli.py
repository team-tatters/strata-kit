import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb.legacy import gen_decision_notes  # noqa: E402


def _add(project: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(KIT / "kb"), "decision", "add", "--project-dir", str(project), "--no-notes",
         "--slug", "demo", "--topic", "t", "--decision", "d", "--reason", "r", "--date", "2026-10-30", *extra],
        capture_output=True, text=True)


class DecisionRetroMaterialTest(unittest.TestCase):
    """DEC-2026-10-30-03: a record keeps the alternatives weighed (and why they lost) and the background consulted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / ".strata" / "decisions").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self) -> dict:
        (f,) = (self.project / ".strata" / "decisions").glob("DEC-*.yaml")
        return yaml.safe_load(f.read_text(encoding="utf-8"))["decision"]

    def test_alternatives_and_background_are_written(self):
        r = _add(self.project, "--alternative", "A: 비용이 커서", "--alternative", 'B: "따옴표" 포함',
                 "--background", "개념 X")
        self.assertEqual(r.returncode, 0, r.stderr)
        body = self.record()
        self.assertEqual(body["alternatives"], ["A: 비용이 커서", 'B: "따옴표" 포함'])
        self.assertEqual(body["background"], ["개념 X"])
        self.assertNotIn("검토한 대안이 없음", r.stderr)

    def test_without_alternatives_warns_but_passes(self):
        r = _add(self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("검토한 대안이 없음", r.stderr)
        body = self.record()
        self.assertNotIn("alternatives", body)
        self.assertNotIn("background", body)

    def test_note_shows_both_sections(self):
        _add(self.project, "--alternative", "A: 진 이유", "--background", "자료 Y")
        (f,) = (self.project / ".strata" / "decisions").glob("DEC-*.yaml")
        text = gen_decision_notes.note_text(f, self.record(), "demo")
        self.assertIn("## Alternatives\n\n- A: 진 이유\n", text)
        self.assertIn("## Background\n\n- 자료 Y\n", text)
        self.assertLess(text.index("## Reason"), text.index("## Alternatives"))



class WithdrawnSupersederTest(unittest.TestCase):
    """A withdrawn record does not retire what it named in supersedes: the old decision stays active unless a live
    record supersedes it (2026-11-02 — DEC-2026-11-02-04 was withdrawn and re-recorded as -05)."""

    def test_withdrawn_record_does_not_supersede(self):
        from pathlib import Path
        from kb.legacy.decision import derive_status
        recs = [(Path("a"), {"id": "D-1"}),
                (Path("b"), {"id": "D-2", "supersedes": ["D-1"], "status": "withdrawn"})]
        self.assertEqual(derive_status(recs)["D-1"], ("active", []))
        self.assertEqual(derive_status(recs)["D-2"], ("withdrawn", []))
        recs.append((Path("c"), {"id": "D-3", "supersedes": ["D-1"]}))
        self.assertEqual(derive_status(recs)["D-1"], ("superseded", ["D-3"]))

    def test_store_side_derivation_agrees(self):
        from pathlib import Path
        from kb import decisions
        recs = [(Path("a"), {"id": "D-1"}), (Path("b"), {"id": "D-2", "supersedes": ["D-1"], "status": "withdrawn"})]
        self.assertEqual(decisions.derive_status(recs)["D-1"], ("active", []))


if __name__ == "__main__":
    unittest.main()
