"""This session's active file (planning/active-file-and-compact-hooks acceptance 4·9): the compaction snapshot points
at this session's file even when another session's file is newer, says 'no active file for this session' with the
count when only others exist, and survives running twice (plugin hook and project settings hook both registered)."""
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.legacy import pre_compact_snapshot  # noqa: E402
from kb.legacy.active_session import pick  # noqa: E402

SID = "9496c8b3-81db-4f3c-887e-5a15eb0d83a5"


class PickTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.local = Path(self.tmp.name) / ".strata" / "local"
        (self.local / "active").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, body, age=0):
        f = self.local / "active" / name
        f.write_text(body, encoding="utf-8")
        t = time.time() - age
        os.utime(f, (t, t))
        return f

    def test_own_file_by_field_beats_newer_other(self):
        own = self.write("session-a.yaml", f"harness_session_id: {SID}\nnext: mine\n", age=100)
        self.write("session-b.yaml", "next: theirs\n")
        p = pick(self.local, SID, "compact")
        self.assertEqual((p.path, p.own, p.others), (own, True, 1))

    def test_own_file_by_name_and_by_list(self):
        named = self.write(f"{SID}.yaml", "next: x\n")
        self.assertEqual(pick(self.local, SID, "compact").path, named)
        named.unlink()
        listed = self.write("session-r.yaml", f"harness_session_id: [old-id, {SID}]\n")
        self.assertEqual(pick(self.local, SID, "compact").path, listed)

    def test_compact_never_uses_another_sessions_file(self):
        self.write("session-b.yaml", "next: theirs\n")
        p = pick(self.local, SID, "compact")
        self.assertIsNone(p.path)
        self.assertIn("no active file for this session, 1 other", p.label)

    def test_startup_and_hand_run_fall_back_to_newest(self):
        newest = self.write("session-b.yaml", "next: theirs\n")
        self.write("session-c.yaml", "next: older\n", age=100)
        self.assertEqual(pick(self.local, SID, "startup").path, newest)
        self.assertEqual(pick(self.local).label, "active/session-b.yaml, 1 older")

    def test_legacy_only_when_no_per_session_file(self):
        (self.local / "active-task.yaml").write_text("next: legacy\n", encoding="utf-8")
        self.assertEqual(pick(self.local, SID, "compact").label, "legacy active-task.yaml")
        self.write("session-b.yaml", "next: theirs\n")
        self.assertIsNone(pick(self.local, SID, "compact").path)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "CLAUDE.md").write_text("x", encoding="utf-8")
        self.active = self.root / ".strata" / "local" / "active"
        self.active.mkdir(parents=True)
        (self.root / ".strata" / "profile.yaml").write_text("profile: embedded\nproject: demo\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, sid, cwd=None):
        stdin = io.StringIO(json.dumps({"session_id": sid, "hook_event_name": "PreCompact", "cwd": cwd or str(self.root)}))
        out = io.StringIO()
        with mock.patch("sys.stdin", stdin), mock.patch("os.getcwd", return_value=str(self.root)), redirect_stdout(out):
            rc = pre_compact_snapshot.main()
        return rc, (self.root / ".strata" / "local" / "last-compaction.yaml").read_text(encoding="utf-8")

    def test_snapshot_points_at_this_session_twice(self):
        (self.active / "session-a.yaml").write_text(f"harness_session_id: {SID}\n", encoding="utf-8")
        t = time.time() - 100
        os.utime(self.active / "session-a.yaml", (t, t))
        (self.active / "session-b.yaml").write_text("next: theirs\n", encoding="utf-8")
        for _ in range(2):
            rc, snap = self.run_hook(SID)
            self.assertEqual(rc, 0)
            self.assertIn(".strata/local/active/session-a.yaml", snap)
            self.assertNotIn("session-b", snap)

    def test_snapshot_says_none_when_only_others(self):
        (self.active / "session-b.yaml").write_text("next: theirs\n", encoding="utf-8")
        rc, snap = self.run_hook(SID)
        self.assertEqual(rc, 0)
        self.assertIn("이 세션의 활성 파일 없음", snap)
        self.assertIn("1 other session file(s) not used", snap)
        self.assertNotIn("session-b.yaml", snap)

    def test_not_a_strata_project_writes_nothing(self):
        other = Path(self.tmp.name) / "plain" / "sub"; other.mkdir(parents=True)
        stdin = io.StringIO(json.dumps({"session_id": SID, "hook_event_name": "PreCompact", "cwd": str(other)}))
        with mock.patch("sys.stdin", stdin), redirect_stdout(io.StringIO()):
            self.assertEqual(pre_compact_snapshot.main(), 0)
        self.assertFalse((other / ".strata").exists())
        self.assertFalse((other.parent / ".strata").exists())


if __name__ == "__main__":
    unittest.main()
