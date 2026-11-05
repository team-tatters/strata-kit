"""The layer hook never passes silently (DEC-2026-09-30-03): when it cannot check — PyYAML missing in the hook's
python, or no layer rules — it tells the agent through hook JSON additionalContext, since an exit-0 stderr never
reaches the agent."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB.parent))


class UncheckedLayerHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "CLAUDE.md").write_text("# demo\n")
        self.file = self.root / "svc" / "A.kt"
        self.file.parent.mkdir()
        self.file.write_text("package x\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_pyyaml_reaches_the_agent(self):
        shim = self.root / "noyaml"
        shim.mkdir()
        (shim / "yaml.py").write_text("raise ImportError('No module named yaml')\n")
        env = {**os.environ, "PYTHONPATH": str(shim)}
        for event, cmd in (("PostToolUse", [str(KB / "legacy" / "check_layer_violation.py")]),
                           ("PreToolUse", [str(KB / "legacy" / "check_layer_violation.py")]),
                           ("PostToolUse", [str(KB), "check-layer"])):   # the kit CLI route the generated hooks use
            payload = {"hook_event_name": event, "tool_name": "Write",
                       "tool_input": {"file_path": str(self.file), "content": "package x\n"}}
            r = subprocess.run([sys.executable, *cmd], input=json.dumps(payload),
                               cwd=self.root, capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], event)
            self.assertIn("레이어 검사 안 함: PyYAML 없음 — STRATA_PYTHON 확인", out["additionalContext"])
            self.assertIn(sys.executable, out["additionalContext"])

    def test_missing_pyyaml_on_a_non_code_file_stays_quiet(self):
        shim = self.root / "noyaml"
        shim.mkdir()
        (shim / "yaml.py").write_text("raise ImportError('No module named yaml')\n")
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(self.root / "README.md")}}
        r = subprocess.run([sys.executable, str(KB / "legacy" / "check_layer_violation.py")], input=json.dumps(payload),
                           cwd=self.root, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(shim)})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_rules_not_found_reaches_the_agent(self):
        from kb.legacy import check_layer_violation as m
        saved = (m.find_strata_root, sys.argv, os.getcwd())
        out = io.StringIO()
        try:
            m.find_strata_root = lambda: None
            sys.argv = ["check_layer_violation.py", str(self.file)]
            os.chdir(self.root)
            with redirect_stdout(out), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                m.main()
        finally:
            m.find_strata_root, sys.argv = saved[0], saved[1]
            os.chdir(saved[2])
        self.assertEqual(cm.exception.code, 0)
        ctx = json.loads(out.getvalue())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("레이어 검사 안 함: 규칙 없음", ctx)


if __name__ == "__main__":
    unittest.main()
