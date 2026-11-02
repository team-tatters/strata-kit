"""An active must card carries short_claim (MB-strata-kit-2026-045): the generated entry view loads it every session,
and a card without one falls back to its whole claim — six such cards made a backend project's guidance exceed its budget."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]

CARD = {"card": {"id": "rec.demo.rule", "title": {"en": "t", "ko": "t"}, "claim": {"en": "c", "ko": "c"},
                 "verification": {"en": "v", "ko": "v"}, "evidence": [{"kind": "reference", "ref": "x"}],
                 "strength": "must", "status": "active"}}


class CardsShortClaimTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "core" / "cards").mkdir(parents=True)
        (self.root / "core" / "constitution").mkdir(parents=True)
        (self.root / "core" / "constitution" / "constitution.yaml").write_text(
            "constitution:\n  version: '1'\n  ratified: 2026-10-29\n  last_amended: 2026-10-29\n  articles: [rec.demo.rule]\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, card):
        (self.root / "core" / "cards" / "rec.demo.rule.yaml").write_text(yaml.safe_dump(card, allow_unicode=True), encoding="utf-8")
        return subprocess.run([sys.executable, str(KIT / "tools" / "cards_check.py"), "--root", str(self.root)], capture_output=True, text=True)

    def test_must_card_without_short_claim_is_an_error(self):
        r = self.check(CARD)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("needs short_claim", r.stdout)

    def test_must_card_with_short_claim_passes(self):
        card = {"card": {**CARD["card"], "short_claim": {"en": "s", "ko": "s"}}}
        r = self.check(card)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_should_card_needs_none(self):
        card = {"card": {**CARD["card"], "strength": "should"}}
        (self.root / "core" / "constitution" / "constitution.yaml").write_text(
            "constitution:\n  version: '1'\n  ratified: 2026-10-29\n  last_amended: 2026-10-29\n  articles: []\n", encoding="utf-8")
        self.assertEqual(self.check(card).returncode, 0)

    def test_every_kit_must_card_has_short_claim(self):
        for p in (KIT / "core" / "cards").glob("*.yaml"):
            c = yaml.safe_load(p.read_text(encoding="utf-8"))["card"]
            if c.get("strength") == "must" and c.get("status") == "active":
                self.assertEqual(set((c.get("short_claim") or {}).keys()), {"en", "ko", "ja", "zh", "es", "fr"}, c["id"])


if __name__ == "__main__":
    unittest.main()
