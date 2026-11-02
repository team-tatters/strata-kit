import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import grades as g  # noqa: E402


class GradesTest(unittest.TestCase):
    """오더 2026.10.29-02 task-01 (MB-strata-kit-2026-003): block 은 진행 불가, default 는 사유·기한 있는 덮어쓰기로 넘어감,
    advisory 는 보고만. 덮어쓰기는 기한이 지나면 효력이 없다."""

    def findings(self):
        return [g.Finding("verify", "budget_with_inherited", "default", "상속 포함 27,078 B > 12,288 B"),
                g.Finding("verify", "revision_header:AGENTS.md", "block", "생성본 머리말 없음"),
                g.Finding("hygiene", "hub_covers:projects/x/a.md", "advisory", "공용 허브 covers")]

    def test_without_overrides(self):
        r = g.evaluate(self.findings(), [], today="2026-10-29")
        self.assertEqual(r["rc"], 2)
        self.assertEqual([f.key for f in r["blocked"]], ["revision_header:AGENTS.md"])
        self.assertEqual([f.key for f in r["unresolved"]], ["budget_with_inherited"])
        self.assertEqual([f.key for f in r["advisory"]], ["hub_covers:projects/x/a.md"])

    def test_default_overridden_until_expiry_block_never(self):
        ov = [{"check": "verify", "key": "budget_*", "reason": "지침 축소 대기(MB-004)", "until": "2026-11-05", "by": "alice"},
              {"check": "verify", "key": "revision_header:*", "reason": "x", "until": "2026-12-31"}]
        r = g.evaluate(self.findings(), ov, today="2026-10-29")
        self.assertEqual([(f.key, o["reason"]) for f, o in r["overridden"]], [("budget_with_inherited", "지침 축소 대기(MB-004)")])
        self.assertEqual([f.key for f in r["blocked"]], ["revision_header:AGENTS.md"])   # block is not overridable
        later = g.evaluate(self.findings()[:1], ov, today="2026-11-06")
        self.assertEqual((later["rc"], [f.key for f in later["unresolved"]], len(later["expired"])), (2, ["budget_with_inherited"], 1))

    def test_override_needs_reason_and_expiry(self):
        # order 2026.10.31-04: an override with no reason (or no expiry) passed every module — key '*' and nothing else
        f = self.findings()[:1]
        for bad in ({"check": "verify", "key": "*", "until": "2026-12-31"},
                    {"check": "verify", "key": "*", "reason": "  ", "until": "2026-12-31"},
                    {"check": "verify", "key": "*", "reason": "x"}):
            r = g.evaluate(f, [bad], today="2026-10-29")
            self.assertEqual((r["rc"], len(r["unresolved"]), len(r["invalid"])), (2, 1, 1), bad)
        self.assertTrue(any("무효" in line for line in g.render(g.evaluate(f, [{"check": "verify", "key": "*", "until": "2026-12-31"}], today="2026-10-29"))))

    def test_advisory_only_passes(self):
        self.assertEqual(g.evaluate(self.findings()[2:], [], today="2026-10-29")["rc"], 0)

    def test_overrides_file_and_lines(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "gate-overrides.yaml"
            self.assertEqual(g.load_overrides(p), [])
            p.write_text("overrides:\n- {check: verify, key: budget_with_inherited, reason: r, until: 2026-11-05}\n", encoding="utf-8")
            ov = g.load_overrides(p)
            self.assertEqual(ov[0]["until"], "2026-11-05")
            lines = g.render(g.evaluate(self.findings(), ov, today="2026-10-29"))
            self.assertIn("BLOCK  verify revision_header:AGENTS.md — 생성본 머리말 없음", lines)
            self.assertIn("pass   verify budget_with_inherited — 덮어씀: r (~2026-11-05)", lines)
            self.assertIn("note   hygiene hub_covers:projects/x/a.md — 공용 허브 covers", lines)

    def test_unknown_grade_rejected(self):
        with self.assertRaises(ValueError):
            g.Finding("x", "k", "warn", "m")


if __name__ == "__main__":
    unittest.main()
