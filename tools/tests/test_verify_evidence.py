"""tools/verify_evidence.py — test-time evidence for strata.verify."""
import subprocess, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_evidence as ve  # noqa: E402

PASS = [sys.executable, "-c", "print('ok')"]
FAIL = [sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"]


class VerifyEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        (self.p / "src").mkdir()
        (self.p / "src" / "a.py").write_text("x = 1\n")
        (self.p / "other.py").write_text("y = 1\n")
        subprocess.run(["git", "init", "-q", str(self.p)], check=True)
        subprocess.run(["git", "-C", str(self.p), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.p), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, cmd, files=("src",)):
        return ve.main(["record", "--project", str(self.p), "--session", "s1", "--files", *files, "--", *cmd])

    def _check(self):
        return ve.check(self.p, "s1")

    def test_file_changed_during_run_is_unstable(self):
        edit = [sys.executable, "-c", f"open({str(self.p / 'src' / 'a.py')!r}, 'a').write('z = 2\\n')"]
        self.assertEqual(self._record(edit), 0)
        rc, rows = self._check()
        self.assertEqual(rc, 1)
        self.assertFalse(rows[0]["fresh"])
        self.assertEqual(rows[0]["unstable"], ["src"])

    def test_no_evidence_is_not_verified(self):
        rc, rows = self._check()
        self.assertEqual((rc, rows), (2, []))

    def test_fresh_after_passing_run(self):
        self.assertEqual(self._record(PASS), 0)
        rc, rows = self._check()
        self.assertEqual(rc, 0)
        self.assertTrue(rows[0]["fresh"])
        data = ve._load(ve.evidence_path(self.p, "s1"))
        self.assertEqual(data["entries"][0]["output_tail"], "ok")

    def test_task_file_change_makes_it_stale(self):
        self._record(PASS)
        (self.p / "src" / "a.py").write_text("x = 2\n")
        rc, rows = self._check()
        self.assertEqual(rc, 1)
        self.assertEqual(rows[0]["changed"], ["src"])

    def test_change_outside_task_files_keeps_it_fresh(self):
        # another session editing the same checkout must not stale this task's evidence
        self._record(PASS)
        (self.p / "other.py").write_text("y = 2\n")
        self.assertEqual(self._check()[0], 0)

    def test_commit_after_test_keeps_it_fresh(self):
        self._record(PASS)
        (self.p / "other.py").write_text("y = 3\n")
        subprocess.run(["git", "-C", str(self.p), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "c"], check=True)
        self.assertEqual(self._check()[0], 0)

    def test_failed_run_returns_its_exit_code_and_blocks(self):
        self.assertEqual(self._record(FAIL), 3)
        self.assertEqual(self._check()[0], 2)

    def test_latest_entry_per_command_wins(self):
        self._record(FAIL)
        self._record(FAIL[:2] + ["print('fixed')"])
        rc, rows = self._check()
        self.assertEqual(len(rows), 2)  # different commands are both kept
        self.assertEqual(rc, 2)
        self._record(FAIL)  # same failing command again: still failing
        self.assertEqual(len(self._check()[1]), 2)

    def test_session_defaults_to_newest_active_file(self):
        active = self.p / ".strata" / "local" / "active"
        active.mkdir(parents=True)
        (active / "session-x.yaml").write_text("task: t\n")
        self.assertEqual(ve.session_name(self.p, None), "session-x")
        self.assertEqual(ve.session_name(self.p, "given"), "given")
        self.assertEqual(ve.session_name(Path(self.tmp.name) / "src", None), "default")

    def test_missing_file_is_recorded_as_absent(self):
        self._record(PASS, files=("nope.py",))
        data = ve._load(ve.evidence_path(self.p, "s1"))
        self.assertEqual(data["entries"][0]["files"], {"nope.py": "absent"})
        (self.p / "nope.py").write_text("now here\n")
        self.assertEqual(self._check()[0], 1)


if __name__ == "__main__":
    unittest.main()
