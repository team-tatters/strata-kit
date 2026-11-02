"""Entry view trim (DEC-2026-11-02-01, MB-strata-kit-2026-045): the completion checklist is one pointer to the skills,
not their validation items copied in, and should cards are named by id only."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402


class EntryTrimTest(unittest.TestCase):
    def test_checklist_is_one_pointer(self):
        for loc in ("en", "ko"):
            L = [l for l in wizard._checklist_section(KIT, loc) if l]
            self.assertEqual(len(L), 2, L)                    # heading + one sentence
            self.assertIn("`strata.verify`", L[1]); self.assertIn("`strata.handoff`", L[1])
            self.assertNotIn("□", "\n".join(L))

    @unittest.skipUnless((KIT / ".strata" / "kit" / "proposal.yaml").is_file(), "the kit's own guidance proposal is not in this checkout")
    def test_kit_entry_view_names_should_cards_by_id(self):
        with tempfile.TemporaryDirectory() as out:   # generate the kit's own entry view without touching the checkout
            r = subprocess.run([sys.executable, str(KIT / "tools" / "wizard.py"), "generate", str(KIT), "--out", out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (Path(out) / "AGENTS.md").read_text(encoding="utf-8")
        should = text.split("## Should cards", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("**", should)
        self.assertIn("`rec.", should)


if __name__ == "__main__":
    unittest.main()
