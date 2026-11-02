"""verify shows whether a project's own closing command reaches the kit handoff (MB-strata-kit-2026-042): a project
command named like /handoff wins over the plugin skill when typed, so a body that does not route to strata.handoff
skips its steps (memory check, decision records) only when the command is used — a backend project, 2026-11-02."""
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402


class ClosingCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve() / "demo"
        (self.project / ".strata" / "kit").mkdir(parents=True)
        (self.project / ".strata" / "kit" / "registry.yaml").write_text("routes: []\n")
        self.cmds = self.project / ".claude" / "commands"; self.cmds.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def findings(self):
        _, rep = wizard.verify(self.project, KIT)
        return rep, {f.key: f for f in rep["_findings"] if f.key.startswith("closing_command")}

    def test_a_closing_command_off_the_kit_handoff_is_reported(self):
        (self.cmds / "handoff.md").write_text("Run $STRATA_ROOT/scripts/session-ledger.py close\n")
        (self.cmds / "deploy.md").write_text("deploy things\n")                       # not a closing command
        rep, f = self.findings()
        self.assertEqual(list(f), ["closing_command:handoff"])
        self.assertEqual(f["closing_command:handoff"].grade, "advisory")
        self.assertIn("strata.handoff", f["closing_command:handoff"].message)
        self.assertIn("handoff", rep["closing_commands"])

    def test_a_command_that_routes_to_the_kit_skill_passes(self):
        (self.cmds / "handoff.md").write_text("정본 절차는 strata-kit:strata-handoff 를 따른다.\n")
        (self.cmds / "wrap-up.md").write_text("follow strata.handoff\n")
        rep, f = self.findings()
        self.assertEqual(f, {})
        self.assertIn("ok", rep["closing_commands"])

    def test_no_commands_no_line(self):
        rep, f = self.findings()
        self.assertEqual(f, {}); self.assertNotIn("closing_commands", rep)


if __name__ == "__main__":
    unittest.main()
