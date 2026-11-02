"""Handoff reads the coverage grade (DEC-2026-10-29-08): the hook does not block, the handoff shows an unresolved
default or block result as no-go in the handoff body and on stderr, and still writes the handoff (exit 0)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
SCRIPT = KIT / "kb" / "legacy" / "session_handoff.sh"

# Stands in for python: `kb coverage-gate --save F` writes the fixture to F; other kb commands fail (the script
# tolerates that); everything else (python -c …) goes to the real interpreter.
FAKE = """#!{py}
import os, sys
a = sys.argv[1:]
if len(a) >= 2 and a[0].endswith("/kb") and a[1] == "coverage-gate":
    out = a[a.index("--save") + 1]
    open(out, "w", encoding="utf-8").write(open(os.environ["GATE_FIXTURE"], encoding="utf-8").read())
    print("gate report")
    sys.exit(0)
if a and a[0].endswith("/kb"):
    sys.exit(1)
os.execv({py!r}, [{py!r}] + a)
"""


class HandoffGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name).resolve()
        self.vault, self.project = r / "vault", r / "demo"
        self.vault.mkdir()
        self.project.mkdir()
        self.fake = r / "fakepy"
        self.fake.write_text(FAKE.format(py=sys.executable), encoding="utf-8")
        self.fake.chmod(0o755)
        self.fixture = r / "gate.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_handoff(self, gate: dict, slug: str):
        self.fixture.write_text(json.dumps(gate, ensure_ascii=False), encoding="utf-8")
        env = {**os.environ, "STRATA_VAULT": str(self.vault), "STRATA_PYTHON": str(self.fake),
               "GATE_FIXTURE": str(self.fixture)}
        p = subprocess.run(["bash", str(SCRIPT), slug], cwd=self.project, env=env, capture_output=True, text=True)
        files = list((self.vault / "projects" / "demo" / "sessions").glob(f"session-*-{slug}.md"))
        return p, files[0].read_text(encoding="utf-8") if files else ""

    def test_unresolved_default_is_no_go_but_handoff_is_written(self):
        p, body = self.run_handoff({"nodes": ["kb-engine"], "summary_line": "명세 없는 변경 코드 3 · 후보 0", "grade_rc": 2,
                                    "grades": ["FAIL   coverage new_spec:kb — 소유 명세 없는 변경 3개 (default: 사유·기한으로 덮어쓸 수 있음)"]},
                                   "nogo")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("> no-go — 커버리지 등급 미해결 1건", body)
        self.assertIn(">   FAIL   coverage new_spec:kb", body)
        self.assertIn("> 커버리지: 명세 없는 변경 코드 3", body)
        self.assertIn('nodes: ["kb-engine"]', body)
        self.assertIn("no-go", p.stderr)

    def test_resolved_grade_adds_nothing(self):
        p, body = self.run_handoff({"nodes": [], "summary_line": "명세 없는 변경 코드 0 · 후보 0", "grade_rc": 0,
                                    "grades": ["pass   coverage new_spec:kb — 덮어씀: 이관 중 (~2026-12-31)"]}, "go")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("no-go", body)
        self.assertNotIn("no-go", p.stderr)


if __name__ == "__main__":
    unittest.main()
