import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import orders  # noqa: E402

ORDER = """order:
  id: "2026.10.29-09"
  title: "demo"
  status: "planned"
  tasks:
    - {id: "task-01", title: "x"}
"""


class OrderClaimTest(unittest.TestCase):
    """MB-strata-kit-2026-009: an order is claimed (machine · session · time) before work starts, so another machine sees it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.path = self.vault / "projects" / "demo" / "tasks" / "2026.10.29" / "09-demo" / "_order.yaml"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(ORDER, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def load(self):
        return yaml.safe_load(self.path.read_text(encoding="utf-8"))["order"]

    def test_find_by_id(self):
        self.assertEqual(orders.find(self.vault, "2026.10.29-09"), self.path)
        self.assertEqual(orders.find(self.vault, str(self.path.parent)), self.path)
        self.assertIsNone(orders.find(self.vault, "2026.10.29-08"))

    def test_claim_free_order_then_same_session_again(self):
        r = orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T10:00")
        self.assertEqual(r["result"], "claimed")
        o = self.load()
        self.assertEqual(o["status"], "in-progress")
        self.assertEqual(o["claimed_by"], {"machine": "work-laptop", "session": "s1", "at": "2026-10-29T10:00"})
        self.assertEqual(o["tasks"], [{"id": "task-01", "title": "x"}])               # the rest of the file is kept
        self.assertEqual(orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T11:00")["result"], "claimed")

    def test_other_holder_is_refused_unless_forced(self):
        orders.claim(self.path, "macbook", "s0", now="2026-10-28T21:00")
        r = orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T10:00")
        self.assertEqual(r["result"], "held")
        self.assertEqual(r["holder"]["machine"], "macbook")
        self.assertEqual(self.load()["claimed_by"]["machine"], "macbook")              # unchanged
        self.assertEqual(orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T10:00", force=True)["result"], "claimed")
        self.assertEqual(self.load()["claimed_by"]["previous"], {"machine": "macbook", "session": "s0", "at": "2026-10-28T21:00"})

    def test_release(self):
        orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T10:00")
        self.assertEqual(orders.release(self.path, "work-laptop", "s1")["result"], "released")
        self.assertNotIn("claimed_by", self.load())
        self.assertEqual(self.load()["status"], "in-progress")                        # status is the order's, not the claim's

    def test_closed_order_is_not_claimed(self):
        self.path.write_text(ORDER.replace('"planned"', '"closed"'), encoding="utf-8")
        self.assertEqual(orders.claim(self.path, "work-laptop", "s1", now="2026-10-29T10:00")["result"], "closed")


if __name__ == "__main__":
    unittest.main()
