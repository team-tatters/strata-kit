"""Product-flow indicators (DEC-2026-11-01-17): a project's read-only commands print one number each; the kit runs
them in the repository, records failures as errors (never zero), keeps the history, and says which moved the worse way."""
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import indicators as I  # noqa: E402


class IndicatorsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault, self.repo = root / "vault", root / "shop"
        self.vault.mkdir(); (self.repo / ".strata").mkdir(parents=True)
        (self.repo / "counts.txt").write_text("7\n", encoding="utf-8")
        (self.repo / ".strata" / "indicators.yaml").write_text(yaml.safe_dump({"indicators": [
            {"id": "qa.recheck", "label": "다시 확인", "command": "cat counts.txt", "better": "lower"},
            {"id": "tc.coverage", "label": "커버리지", "command": "echo '{\"value\": 81.5}'", "better": "higher", "threshold": 0.05},
            {"id": "broken", "command": "exit 3"},
            {"id": "silent", "command": "echo hello"}]}), encoding="utf-8")
        self.old = os.environ.get("STRATA_VAULT")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STRATA_VAULT", None)
        else:
            os.environ["STRATA_VAULT"] = self.old
        self.tmp.cleanup()

    def test_collect_runs_in_repo_and_records_errors_not_zero(self):
        cfg = I.config_path(self.repo)
        self.assertEqual(cfg, self.repo / ".strata" / "indicators.yaml")
        row = I.collect(I.load_config(cfg), self.repo, now="t1")
        self.assertEqual(row["values"], {"qa.recheck": 7, "tc.coverage": 81.5})
        self.assertEqual(set(row["errors"]), {"broken", "silent"})
        self.assertIn("exit 3", row["errors"]["broken"])
        self.assertIn("숫자를 출력하지 않음", row["errors"]["silent"])

    def test_bad_better_is_refused(self):
        p = self.repo / ".strata" / "indicators.yaml"
        p.write_text("indicators:\n  - {id: x, command: 'echo 1', better: sideways}\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            I.load_config(p)

    def test_worse_respects_direction_threshold_and_zero(self):
        low, high = {"better": "lower", "threshold": 0.1}, {"better": "higher", "threshold": 0.1}
        self.assertAlmostEqual(I.worse(low, 10, 12), 0.2)
        self.assertIsNone(I.worse(low, 10, 10.5))
        self.assertIsNone(I.worse(low, 10, 5))
        self.assertAlmostEqual(I.worse(high, 80, 60), 0.25)
        self.assertIsNone(I.worse(high, 80, 90))
        self.assertEqual(I.worse(low, 0, 1), 1.0)

    def test_cli_write_appends_history_and_show_marks_worse(self):
        run = lambda *a: (lambda buf: (I.main(list(a)), buf.getvalue())[1])(StringIO())
        buf = StringIO()
        with redirect_stdout(buf):
            self.assertEqual(I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"]), 0)
        (self.repo / "counts.txt").write_text("9\n", encoding="utf-8")
        with redirect_stdout(StringIO()):
            I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"])
        data = yaml.safe_load(I.history_path(self.vault, "shop").read_text(encoding="utf-8"))
        self.assertEqual([h["values"]["qa.recheck"] for h in data["history"]], [7, 9])
        self.assertEqual(data["indicators"]["tc.coverage"]["better"], "higher")
        lines = I.show(data)
        self.assertTrue(any(l.strip().startswith("qa.recheck") and "7 → 9 — 나빠짐" in l for l in lines), lines)
        self.assertTrue(any("broken" in l and "오류" in l for l in lines))

    def test_project_without_config_is_not_an_error(self):
        (self.repo / ".strata" / "indicators.yaml").unlink()
        buf = StringIO()
        with redirect_stdout(buf):
            self.assertEqual(I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"]), 0)
        self.assertIn("지표 설정 없음", buf.getvalue())
        self.assertFalse(I.history_path(self.vault, "shop").exists())

    def test_readers_for_common_formats(self):
        import json as _j
        cat = self.repo / "cat.json"
        cat.write_text(_j.dumps({"defects": {"a": {"status": "열림"}, "b": {"status": "확인 대기"}, "c": {"status": "확인됨"}},
                                 "pages": [{"tests": [{"x": 1}]}, {"tests": []}, {"tests": []}, {}]}), encoding="utf-8")
        self.assertEqual(I.read("json-count", [str(cat)], where="status=열림|확인 대기", path="defects"), 2)
        self.assertEqual(I.read("json-count", [str(cat)], path="defects"), 3)
        self.assertEqual(I.read("json-ratio", [str(cat)], has="tests", path="pages"), 25.0)
        rep = self.repo / "m" / "build" / "jacoco.xml"; rep.parent.mkdir(parents=True)
        rep.write_text('<report name="m"><package name="p"><counter type="LINE" missed="99" covered="1"/></package>'
                       '<counter type="LINE" missed="30" covered="70"/></report>', encoding="utf-8")
        self.assertEqual(I.read("jacoco", [str(self.repo / "*/build/jacoco.xml")]), 70.0)   # report-level counter only
        ju = self.repo / "r" / "TEST-a.xml"; ju.parent.mkdir()
        ju.write_text('<testsuite tests="5" failures="1" errors="2"/>', encoding="utf-8")
        self.assertEqual(I.read("junit", [str(self.repo / "r" / "*.xml")]), 3)
        with self.assertRaises(ValueError):
            I.read("jacoco", [str(self.repo / "none" / "*.xml")])

    def test_nodes_reach_the_signal_note(self):
        from datetime import date
        from kb import signals as S
        cfg = self.repo / ".strata" / "indicators.yaml"
        cfg.write_text("indicators:\n  - {id: q, command: 'cat counts.txt', better: lower, nodes: [qa.recheck]}\n", encoding="utf-8")
        ind = I.load_config(cfg)
        m = I.merge({}, {"collected": "t1", "values": {"q": 2}}, ind, "shop")
        m = I.merge(m, {"collected": "t2", "values": {"q": 5}}, ind, "shop")
        c = S.indicator_candidates(m, "i.yaml")[0]
        self.assertEqual(c.nodes, ["qa.recheck"])
        p = S.write_note(self.vault, "shop", source="indicator", title=c.title, observation=c.observation, evidence=c.evidence,
                         observed=date(2026, 11, 1), today=date(2026, 11, 1), candidate=c.key, nodes=c.nodes)
        fm, _ = S.split(p.read_text(encoding="utf-8"))
        self.assertEqual(fm["nodes"], ["qa.recheck"])

    def test_history_is_capped(self):
        old = {"history": [{"collected": str(i), "values": {}} for i in range(I.HISTORY_MAX)]}
        m = I.merge(old, {"collected": "new", "values": {}}, [], "shop")
        self.assertEqual(len(m["history"]), I.HISTORY_MAX)
        self.assertEqual(m["history"][-1]["collected"], "new")


if __name__ == "__main__":
    unittest.main()
