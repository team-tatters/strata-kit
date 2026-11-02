"""The header reads the SessionStart hook input (planning/active-file-and-compact-hooks acceptance 5·6, DEC-2026-10-31-08):
session_id picks this session's active file over a newer one; on source compact the header becomes a short restore
note with this session's next action and the latest handoff's; a hand run with no input is unchanged and never waits."""
import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402

SID = "9496c8b3-81db-4f3c-887e-5a15eb0d83a5"


class HeaderHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.project = root / "demo"; act = self.project / ".strata" / "local" / "active"; act.mkdir(parents=True)
        (self.project / ".strata" / "profile.yaml").write_text("profile: embedded\nproject: demo\n", encoding="utf-8")
        (act / "session-mine.yaml").write_text(f"harness_session_id: {SID}\nnext: 내 다음 일\n", encoding="utf-8")
        t = time.time() - 100
        os.utime(act / "session-mine.yaml", (t, t))
        (act / "session-other.yaml").write_text("next: 남의 다음 일\n", encoding="utf-8")
        sessions = root / "vault" / "projects" / "demo" / "sessions"; sessions.mkdir(parents=True)
        (sessions / "session-x.md").write_text('---\ntitle: x\nnext_session: "핸드오프 다음 일"\n---\n\n# x\n', encoding="utf-8")
        (sessions / "latest.md").symlink_to("session-x.md")
        self.env = mock.patch.dict(os.environ, {"STRATA_VAULT": str(root / "vault")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def hook(self, source):
        return {"hook_event_name": "SessionStart", "session_id": SID, "source": source}

    def test_session_id_picks_own_file_over_newer(self):
        h = wizard.header(self.project, wizard.KIT, "ko", self.hook("startup"))
        self.assertIn("next action: 내 다음 일 [active/session-mine.yaml, 1 other]", h)
        self.assertIn("남의 다음 일", wizard.header(self.project, wizard.KIT, "ko"))   # hand run: newest, as before

    def test_compact_is_short_restore_note(self):
        full = wizard.header(self.project, wizard.KIT, "ko")
        h = wizard.header(self.project, wizard.KIT, "ko", self.hook("compact"))
        self.assertIn("restored after compaction", h)
        self.assertIn("next action: 내 다음 일", h)
        self.assertIn("latest handoff next: 핸드오프 다음 일 [sessions/session-x.md]", h)
        self.assertLessEqual(len(h.splitlines()), len(full.splitlines()))
        self.assertLess(len(h.encode()), len(full.encode()))

    def test_compact_without_own_file_does_not_use_others(self):
        (self.project / ".strata" / "local" / "active" / "session-mine.yaml").unlink()
        h = wizard.header(self.project, wizard.KIT, "ko", self.hook("compact"))
        self.assertIn("no active file for this session, 1 other session file(s) not used", h)
        self.assertNotIn("남의 다음 일", h)

    def test_restart_signal_line_reads_user_config(self):
        # DEC-2026-10-31-09·33: fixed token counts, default 400K with a 600K limit, both in the user config
        cfg = Path(self.tmp.name) / "config.yaml"
        with mock.patch.dict(os.environ, {"STRATA_USER_CONFIG": str(cfg)}):
            self.assertIn("restart signal: past about 400K tokens (limit 600K), or two failures on one hypothesis", wizard.header(self.project, wizard.KIT, "ko"))
            cfg.write_text("session:\n  restart_tokens: 500000\n  restart_limit: 700000\n", encoding="utf-8")
            self.assertIn("restart signal: past about 500K tokens (limit 700K)", wizard.header(self.project, wizard.KIT, "ko"))
            self.assertNotIn("restart signal", wizard.header(self.project, wizard.KIT, "ko", self.hook("compact")))

    def test_hook_input_ignores_hand_runs(self):
        self.assertEqual(wizard.hook_input(io.StringIO('{"hook_event_name": "PreCompact", "session_id": "x"}')), {})
        self.assertEqual(wizard.hook_input(io.StringIO("not json")), {})
        self.assertEqual(wizard.hook_input(io.StringIO('{"hook_event_name": "SessionStart", "source": "compact"}'))["source"], "compact")
        r, w = os.pipe()   # left open with nothing written (an agent's shell): returns, does not wait
        try:
            with os.fdopen(r) as stream:
                t = time.time()
                self.assertEqual(wizard.hook_input(stream, wait=0.2), {})
                self.assertLess(time.time() - t, 2)
        finally:
            os.close(w)


if __name__ == "__main__":
    unittest.main()
