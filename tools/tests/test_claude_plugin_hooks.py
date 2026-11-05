"""The Claude plugin registers PreCompact next to SessionStart (planning/active-file-and-compact-hooks acceptance 3·8):
the generated hooks.json has both, a wrong STRATA_KIT ends either with one line and exit 0, and the generated guidance's
harness event table shows the plugin's hooks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import gen_claude_plugin  # noqa: E402
import wizard  # noqa: E402


class PluginHooksTest(unittest.TestCase):
    def test_generated_hooks_json_has_precompact(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "strata-kit"
            subprocess.run([sys.executable, str(KIT / "tools" / "gen_claude_plugin.py"), "--allow-dirty", "--out", str(out)],
                           check=True, capture_output=True, text=True)
            hooks = json.loads((out / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(hooks["PreCompact"][0]["hooks"][0]["command"], gen_claude_plugin.PRECOMPACT_HOOK)
        self.assertEqual(hooks["SessionStart"][0]["hooks"][0]["command"], gen_claude_plugin.HEADER_HOOK)

    def test_wrong_kit_path_is_one_line_and_exit_0(self):
        env = {**os.environ, "STRATA_KIT": "/nonexistent/strata-kit"}
        for cmd in (gen_claude_plugin.PRECOMPACT_HOOK, gen_claude_plugin.HEADER_HOOK):
            r = subprocess.run(["sh", "-c", cmd], env=env, input="{}", capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(len(r.stdout.strip().splitlines()), 1)
            self.assertIn("set STRATA_KIT", r.stdout)

    def test_event_table_shows_plugin_hooks(self):
        with tempfile.TemporaryDirectory() as d:
            table = "\n".join(wizard._claude_hooks_section(Path(d), "en"))
        self.assertIn("| `session.start` | `SessionStart` | plugin: wizard header |", table)
        self.assertIn("| `before.context.compact` | `PreCompact` | plugin: kb pre-compact |", table)


if __name__ == "__main__":
    unittest.main()
