"""Coverage ratio (MB-strata-kit-2026-057 step 2): every batch run says how much of the code the declaration covers —
the layer map audit (files), kb boundaries check (modules with a changelog), the ArchUnit layer warning test (classes)
— and kb enforce keeps the figure in the ledger entry."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import boundaries as bd  # noqa: E402
from kb.gates import enforce  # noqa: E402
from kb.legacy import check_layer_violation as clv  # noqa: E402

KB = Path(__file__).resolve().parents[1]
ENF = KB.parent / "profiles" / "backend.kotlin-spring-cqrs" / "enforcement"

MAP = """project_type: "backend"
mappings:
  - path: "svc/l2/"
    layer: "L2_DataLayer"
excluded:
  - "svc/old/"
"""


def w(path: Path, text: str = "package x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LayerAuditRatioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "demo"
        w(self.repo / "CLAUDE.md", "# demo\n")
        w(self.repo / ".strata" / "layer-map.yaml", MAP)
        for rel in ("svc/l2/A.kt", "svc/l2/B.kt", "svc/l2/C.kt", "svc/misc/D.kt", "svc/old/E.kt"):
            w(self.repo / rel)

    def tearDown(self):
        self.tmp.cleanup()

    def test_ratio_counts_mapped_over_files_in_scope(self):
        r = clv.audit(str(self.repo))
        self.assertEqual(r["coverage"], {"in_scope": 4, "mapped": 3, "unmapped": 1, "excluded": 1, "percent": 75.0})
        out = clv.render_audit(r)
        self.assertIn("레이어 맵이 덮는 비율 75% (미대응 1파일", out)
        self.assertIn("[strata] coverage:", out)

    def test_cli_prints_the_ratio(self):
        r = subprocess.run(["python3", str(KB), "check-layer", "--audit", "--project", str(self.repo)], capture_output=True, text=True)
        self.assertIn("레이어 맵이 덮는 비율 75%", r.stdout)


RES = "src/main/resources/config/liquibase"


class BoundariesRatioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        for m in ("domain/a", "domain/b", "domain/c", "domain/d"):
            w(self.root / m / "src/main/kotlin/demo/A.kt")
        for m in ("domain/a", "domain/b", "domain/c"):
            w(self.root / m / RES / "changelogs/init.sql", f"CREATE TABLE {m[-1]}_t (id int);")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ratio_counts_changelog_modules_the_map_names(self):
        r = bd.check(self.root, {"boundaries": {"modules": {"domain/a": "x", "domain/b": "x"}}}, today=date(2026, 11, 5))
        cov = r["coverage"]
        self.assertEqual((cov["modules_with_changelog"], cov["mapped"], cov["percent"]), (3, 2, 66.7))
        self.assertEqual(cov["unmapped_modules"], ["domain/c"])
        out = bd.render(r)
        self.assertIn("경계 대응표가 덮는 비율 67% (미대응 1모듈", out)
        self.assertIn("[strata] coverage:", out)


class EnforceRecordsCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.project, self.vault = r / "demo", r / "vault"
        (self.project / ".strata").mkdir(parents=True)
        self.vault.mkdir()
        w(self.project / ".strata" / "profile.yaml", yaml.safe_dump({"project": "demo", "enforcement": {"layers": "advisory"}}))
        self.old = os.environ.get("STRATA_VAULT")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STRATA_VAULT", None)
        else:
            os.environ["STRATA_VAULT"] = self.old
        self.tmp.cleanup()

    def last(self):
        return yaml.safe_load((self.vault / "projects/demo/measurements/violations.yaml").read_text(encoding="utf-8"))["entries"][-1]

    def run_with(self, text, rc=0):
        enforce.run(self.project, "layers", [sys.executable, "-c", f"print({text!r}); raise SystemExit({rc})"])
        return self.last()

    def test_clean_and_violation_entries_carry_the_ratio(self):
        e = self.run_with("[strata] coverage: 레이어 맵이 덮는 비율 82% (미대응 41파일, 대상 228)")
        self.assertEqual((e["kind"], e["coverage"]), ("clean", {"percent": 82.0, "unmapped": 41}))
        e = self.run_with("[strata-arch] layers coverage: 64.5% of classes mapped (unmapped 120 of 338, excluded 10)\nx", 1)
        self.assertEqual((e["kind"], e["coverage"]), ("violation", {"percent": 64.5, "unmapped": 120}))

    def test_no_ratio_line_no_field(self):
        self.assertNotIn("coverage", self.run_with("ok"))


class TemplateRatioTest(unittest.TestCase):
    def test_layer_warning_test_prints_the_ratio(self):
        mp = (ENF / "StrataLayerMapTest.kt.template").read_text(encoding="utf-8")
        wt = (ENF / "opt-in" / "StrataLayerWarningsTest.kt.template").read_text(encoding="utf-8")
        self.assertIn("fun coverageLine()", mp)
        self.assertIn("layers coverage: ", mp)
        self.assertIn("StrataLayerMapTest.coverageLine()", wt)
        line = '"[strata-arch] layers coverage: 64.5% of classes mapped (unmapped 120 of 338, excluded 10)"'
        self.assertRegex(line, enforce.COVERAGE_RE)


if __name__ == "__main__":
    unittest.main()
