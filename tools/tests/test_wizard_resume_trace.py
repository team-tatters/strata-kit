"""Resume when the handoff cannot be reached (MB-strata-kit-2026-043): the header shows the latest handoff's next step
on a normal start too; with no active file and no handoff it says where it looked (the resolved path, or that the vault
variable is unset) and points at the traces inside the repository — notes, git log, branches — instead of leaving the
agent to search the vault and ask."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402


class ResumeTraceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "demo"
        (self.project / ".strata").mkdir(parents=True)
        (self.project / ".strata" / "profile.yaml").write_text("profile: embedded\nproject: demo\n", encoding="utf-8")
        self.sessions = self.root / "vault" / "projects" / "demo" / "sessions"
        self.sessions.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def header(self, env):
        with mock.patch.dict(os.environ, env, clear=False):
            if "STRATA_VAULT" not in env:
                os.environ.pop("STRATA_VAULT", None)
            return wizard.header(self.project, wizard.KIT, "en", {"hook_event_name": "SessionStart", "source": "startup"})

    def test_no_handoff_no_active_file_points_at_repo_traces(self):
        h = self.header({"STRATA_VAULT": str(self.root / "vault")})
        line = next(l for l in h.splitlines() if l.startswith("resume:"))
        self.assertIn(str(self.sessions / "latest.md"), line)
        self.assertIn("git log", line)
        self.assertIn("NOTES", line)

    def test_vault_unset_is_named(self):
        h = self.header({})
        line = next(l for l in h.splitlines() if l.startswith("resume:"))
        self.assertIn("STRATA_VAULT unset", line)

    def test_handoff_next_on_normal_start_and_no_trace_line(self):
        (self.sessions / "session-x.md").write_text('---\ntitle: x\nnext_session: "do the next thing"\n---\n', encoding="utf-8")
        (self.sessions / "latest.md").symlink_to("session-x.md")
        h = self.header({"STRATA_VAULT": str(self.root / "vault")})
        self.assertIn("latest handoff next: do the next thing [sessions/session-x.md]", h)
        self.assertFalse(any(l.startswith("resume:") for l in h.splitlines()))

    def test_active_file_alone_needs_no_trace_line(self):
        act = self.project / ".strata" / "local" / "active"; act.mkdir(parents=True)
        (act / "session-a.yaml").write_text("next: keep going\n", encoding="utf-8")
        h = self.header({"STRATA_VAULT": str(self.root / "vault")})
        self.assertFalse(any(l.startswith("resume:") for l in h.splitlines()))

    def test_generated_guidance_names_the_fallback(self):
        lines = wizard._claude_kb_section(self.project, None, "en")
        self.assertTrue(any("latest.md" in l and "git log" in l for l in lines))
        ko = wizard._claude_kb_section(self.project, None, "ko")
        self.assertTrue(any("latest.md" in l and "git log" in l for l in ko))


if __name__ == "__main__":
    unittest.main()
