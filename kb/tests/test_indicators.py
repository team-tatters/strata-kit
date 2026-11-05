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
            # broken and silent fail: the history is still written, and the exit code says so (librarian counts it)
            self.assertEqual(I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"]), 1)
        (self.repo / "counts.txt").write_text("9\n", encoding="utf-8")
        with redirect_stdout(StringIO()):
            I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"])
        data = yaml.safe_load(I.history_path(self.vault, "shop").read_text(encoding="utf-8"))
        self.assertEqual([h["values"]["qa.recheck"] for h in data["history"]], [7, 9])
        self.assertEqual(data["indicators"]["tc.coverage"]["better"], "higher")
        lines = I.show(data)
        self.assertTrue(any(l.strip().startswith("qa.recheck") and "7 → 9 — 나빠짐" in l for l in lines), lines)
        self.assertTrue(any("broken" in l and "오류" in l for l in lines))

    def test_all_values_exit_zero(self):
        p = self.repo / ".strata" / "indicators.yaml"
        p.write_text("indicators:\n  - {id: x, command: 'echo 1'}\n", encoding="utf-8")
        with redirect_stdout(StringIO()):
            self.assertEqual(I.main(["collect", "--project", "shop", "--repo", str(self.repo), "--write"]), 0)

    def test_kit_commands_run_with_strata_python_and_kit(self):
        """Under launchd bare python3 is /usr/bin/python3 without PyYAML: a kit command's python3 becomes
        STRATA_PYTHON (default: the python running the collector), and STRATA_KIT/STRATA_PYTHON reach the command."""
        fake = Path(self.tmp.name) / "fakepy"
        fake.write_text("#!/bin/sh\necho 42\n", encoding="utf-8"); fake.chmod(0o755)
        saved = {k: os.environ.get(k) for k in ("STRATA_PYTHON", "STRATA_KIT")}
        try:
            os.environ["STRATA_PYTHON"] = str(fake)
            os.environ.pop("STRATA_KIT", None)
            its = [{"id": "kit", "command": 'python3 "$STRATA_KIT/kb" indicators read junit "*.xml"'},
                   {"id": "kitm", "command": "cd . && python3 -m kb indicators read junit x"},
                   {"id": "env", "command": 'test -d "$STRATA_KIT/kb" && echo "$STRATA_PYTHON" | grep -q fakepy && echo 1'},
                   {"id": "own", "command": "python3 -c 'print(5)'"}]
            row = I.collect(its, self.repo, now="t")
            self.assertEqual(row["values"], {"kit": 42, "kitm": 42, "env": 1, "own": 5}, row)
            self.assertEqual(I.resolve_kit_python('python3 "$STRATA_KIT/kb" x', "/p y/py"), "'/p y/py' \"$STRATA_KIT/kb\" x")
            self.assertEqual(I.resolve_kit_python("python3 scripts/own.py", "/py"), "python3 scripts/own.py")
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

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
