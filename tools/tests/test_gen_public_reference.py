"""Public reference pages (DEC-2026-11-02-09): generated from the sources in ko and en, one row per active card, skill
and profile, and no decision or backlog id in the text."""
import re
import sys
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import gen_public_reference as g  # noqa: E402


class GenPublicReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = g.generate(KIT)

    def test_both_locales_and_four_pages(self):
        self.assertEqual(sorted(self.pages), sorted(f"{l}/reference/{k}.md" for l in ("ko", "en") for k in ("cards", "skills", "cli", "profiles")))

    def test_every_active_card_and_profile_has_a_row(self):
        active = [c["card"]["id"] for c in (yaml.safe_load(p.read_text(encoding="utf-8")) for p in (KIT / "core/cards").glob("*.yaml"))
                  if c["card"].get("status") == "active"]
        for l in ("ko", "en"):
            for cid in active:
                self.assertIn(f"`{cid}`", self.pages[f"{l}/reference/cards.md"])
            self.assertEqual(self.pages[f"{l}/reference/profiles.md"].count("\n| `"), len(list((KIT / "profiles").glob("*/profile.yaml"))))

    def test_no_private_ids(self):
        for rel, text in self.pages.items():
            self.assertIsNone(re.search(r"\b(DEC|MB)-\d{4}", text), rel)

    def test_pages_are_ready(self):
        for text in self.pages.values():
            self.assertIn("status: ready", text.split("---")[1])


if __name__ == "__main__":
    unittest.main()
