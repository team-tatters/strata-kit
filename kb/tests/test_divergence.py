"""Divergence judgement (planning/divergence-judgement acceptance 2·3·4, DEC-2026-10-31-35): the gate's recheck rows
queue as requests without doubling, a person judges with one of four values and a name, judging moves the plan's
implementation.reviewed so the gate stops asking for the same changes, and plan gaps go to the plan's owner."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import coverage as cov  # noqa: E402
from kb.gates import divergence as dv  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class DivergenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        p = self.vault / "projects" / "demo"
        w(p / "knowledge-base" / "scope3.md", "---\ntitle: Scope 3\nid: kb-demo-scope3\ntype: specification\nproject: demo\ncreated: 2026-04-01\n"
          "covers:\n  paths: [\"service/scope3/\"]\n---\n## 본문\nx\n")
        w(p / "planning" / "done.md", "---\ntitle: done\ntype: planning\nproject: demo\nowner: 기획팀 김\ncreated: 2026-09-01\n"
          "implementation:\n  status: implemented\n  reviewed: 2026-10-01\n  spec: \"[[scope3]]\"\n---\n## 기획\ny\n")
        self.project_dir = root / "demo"; self.project_dir.mkdir()
        self.env = {"STRATA_VAULT": str(self.vault)}
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, since):
        store = SqliteStore(); store.rebuild([VaultScanner(self.vault)], kit_rev="t")
        return cov.run_gate(str(self.project_dir), files=["service/scope3/Foo.kt"], since=since, store=store, knowledge=([], []))

    def test_gate_rows_queue_once_and_judging_clears_the_recheck(self):
        r = self.gate("2026-10-31")
        self.assertEqual([d["action"] for d in r["desired_shape"]], ["recheck"])
        self.assertEqual(dv.from_gate(self.vault, "demo", r["desired_shape"], r["since"], today="2026-10-31"), ["DV-1"])
        self.assertEqual(dv.from_gate(self.vault, "demo", r["desired_shape"], r["since"], today="2026-10-31"), [])   # no double
        dv.add(self.vault, "demo", "projects/demo/planning/other.md", None, "구현 검토 차이", source="review")
        self.assertEqual(len(dv.pending(self.vault, "demo")), 2)
        req, line = dv.judge(self.vault, "demo", "DV-1", "consistent", "alice", today="2026-10-31")
        self.assertEqual((req["status"], req["judgement"], req["by"]), ("judged", "consistent", "alice"))
        self.assertIn("정합", line)
        fm = yaml.safe_load((self.vault / "projects/demo/planning/done.md").read_text(encoding="utf-8").split("---")[1])
        self.assertEqual((str(fm["implementation"]["reviewed"]), fm["implementation"]["status"]), ("2026-10-31", "implemented"))
        self.assertEqual(self.gate("2026-10-31")["desired_shape"], [])                # judged: no recheck for these changes
        self.assertEqual(len(self.gate("2026-11-02")["desired_shape"]), 1)            # later changes ask again
        r2 = self.gate("2026-11-02")
        self.assertEqual(dv.from_gate(self.vault, "demo", r2["desired_shape"], r2["since"]), ["DV-3"])   # the judged one stays
        kept = {x["id"]: x["status"] for x in dv.load(self.vault, "demo")["requests"]}
        self.assertEqual(kept, {"DV-1": "judged", "DV-2": "pending", "DV-3": "pending"})

    def test_judge_needs_a_value_from_the_list_and_a_person(self):
        dv.add(self.vault, "demo", "projects/demo/planning/done.md", "projects/demo/knowledge-base/scope3.md", "d")
        for value, by in (("maybe", "alice"), ("doc_stale", " ")):
            with self.assertRaises(ValueError):
                dv.judge(self.vault, "demo", "DV-1", value, by)
        self.assertEqual(dv.pending(self.vault, "demo")[0]["status"], "pending")
        _, line = dv.judge(self.vault, "demo", "DV-1", "plan_gap", "alice", today="2026-10-31")
        self.assertIn("기획 소유자 기획팀 김", line)                                  # the plan's owner, not the user

    def test_reviewed_is_added_when_missing(self):
        plan = self.vault / "projects/demo/planning/bare.md"
        w(plan, "---\ntitle: bare\ntype: planning\nimplementation:\n  status: partial\n---\nbody\n")
        dv.add(self.vault, "demo", "projects/demo/planning/bare.md", None, "d")
        _, line = dv.judge(self.vault, "demo", "DV-1", "impl_defect", "alice", today="2026-10-31")
        self.assertIn("기획 소유자", dv.JUDGEMENTS["plan_gap"][1])
        self.assertIn("strata.order", line)
        fm = yaml.safe_load(plan.read_text(encoding="utf-8").split("---")[1])
        self.assertEqual((fm["implementation"]["status"], str(fm["implementation"]["reviewed"])), ("partial", "2026-10-31"))
        self.assertTrue(plan.read_text(encoding="utf-8").endswith("---\nbody\n"))


if __name__ == "__main__":
    unittest.main()
