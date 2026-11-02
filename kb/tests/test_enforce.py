"""kb enforce (DEC-2026-10-29-17, order 2026.10.29-14 task-08): the project's grade decides what a checker's failure does."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from kb.gates import enforce

FAIL = [sys.executable, "-c", "print('src/a.ts -> src/b.ts'); print('2 violations'); raise SystemExit(1)"]
PASS = [sys.executable, "-c", "print('ok')"]


class EnforceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.project, self.vault = r / "demo", r / "vault"
        (self.project / ".strata").mkdir(parents=True); self.vault.mkdir()
        self.old = os.environ.get("STRATA_VAULT"); os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        if self.old is None: os.environ.pop("STRATA_VAULT", None)
        else: os.environ["STRATA_VAULT"] = self.old
        self.tmp.cleanup()

    def manifest(self, enforcement=None):
        m = {"profile": "embedded", "project": "demo"}
        if enforcement: m["enforcement"] = enforcement
        (self.project / ".strata" / "profile.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")

    def ledger(self):
        return yaml.safe_load((self.vault / "projects/demo/measurements/violations.yaml").read_text(encoding="utf-8"))["entries"]

    def test_undeclared_family_blocks_as_before(self):
        self.manifest()
        rc, lines = enforce.run(self.project, "layers", FAIL)
        self.assertEqual(rc, 2); self.assertTrue(lines[0].startswith("BLOCK"))

    def test_undeclared_coverage_only_reports(self):
        # DEC-2026-10-31-31: coverage counts gaps older than the baseline, so undeclared it is advisory
        self.manifest({"layers": "default"})
        self.assertEqual((enforce.grade_of(self.project, "coverage"), enforce.grade_of(self.project, "naming")), ("advisory", "block"))

    def test_undeclared_stages_only_reports(self):
        # DEC-2026-11-01-18: the newer stages' checks (planning · design · taste · ideas · signals) start advisory
        self.manifest({})
        self.assertEqual(enforce.grade_of(self.project, "stages"), "advisory")

    def test_advisory_records_and_passes(self):
        self.manifest({"layers": "advisory"})
        rc, _ = enforce.run(self.project, "layers", FAIL, count_regex=r"(\d+) violations")
        rc2, _ = enforce.run(self.project, "layers", FAIL, count_regex=r"->")
        self.assertEqual((rc, rc2), (0, 0))
        e = self.ledger()
        self.assertEqual([x["count"] for x in e], [2, 1])
        self.assertEqual((e[0]["family"], e[0]["grade"], e[0]["exit_code"]), ("layers", "advisory", 1))
        self.assertIn("2 violations", e[0]["tail"])

    def test_default_needs_a_live_override(self):
        self.manifest({"naming": "default"})
        self.assertEqual(enforce.run(self.project, "naming", FAIL, today="2026-10-29")[0], 2)
        (self.project / ".strata" / "gate-overrides.yaml").write_text(
            "overrides:\n- {check: enforce, key: naming, reason: 기준선 정리 중, until: 2026-11-30}\n", encoding="utf-8")
        self.assertEqual(enforce.run(self.project, "naming", FAIL, today="2026-10-29")[0], 0)
        self.assertEqual(enforce.run(self.project, "naming", FAIL, today="2026-12-01")[0], 2)

    def test_clean_run_is_recorded_as_evidence(self):
        # DEC-2026-10-31-23: a clean run leaves one line, so doctor can tell "ran and found nothing" from "never ran"
        self.manifest({"layers": "advisory"})
        self.assertEqual(enforce.run(self.project, "layers", PASS)[0], 0)
        (e,) = self.ledger()
        self.assertEqual((e["kind"], e["exit_code"], e["family"]), ("clean", 0, "layers"))

    def test_checker_failure_is_not_a_violation(self):
        """DEC-2026-10-29-19: advisory records violations, it never turns a broken checker into a pass."""
        self.manifest({"layers": "advisory"})
        crash = [sys.executable, "-c", "print('cannot load config'); raise SystemExit(2)"]
        rc, lines = enforce.run(self.project, "layers", crash)
        self.assertEqual(rc, 2); self.assertIn("검사 실패", lines[0])
        self.assertEqual(enforce.run(self.project, "layers", ["/nonexistent/checker"])[0], 2)
        e = self.ledger()
        self.assertEqual([x["kind"] for x in e], ["checker_error", "checker_error"])
        self.assertEqual(e[1]["exit_code"], 127)

    def test_violation_exit_range_and_pattern(self):
        self.manifest({"layers": "advisory"})
        many = [sys.executable, "-c", "print('error no-orphans: a.ts'); raise SystemExit(7)"]   # dependency-cruiser: exit = error count
        self.assertEqual(enforce.run(self.project, "layers", many)[0], 2)                           # default: only exit 1
        self.assertEqual(enforce.run(self.project, "layers", many, violation_exit="1-255", violation_pattern=r"^error ")[0], 0)
        odd = [sys.executable, "-c", "print('Traceback'); raise SystemExit(7)"]
        self.assertEqual(enforce.run(self.project, "layers", odd, violation_exit="1-255", violation_pattern=r"(?m)^error ")[0], 2)
        self.assertEqual(enforce.exit_codes("1,3-4"), {1, 3, 4})

    def test_warning_mode_checker_exits_zero_with_violations(self):
        # MB-strata-kit-2026-046: a backend project's archCheck prints violations and exits 0 — with 0 in --violation-exit the
        # pattern decides; without the pattern it was recorded as clean
        self.manifest({"layers": "advisory"})
        warn = [sys.executable, "-c", "print('Architecture Violation [Priority: MEDIUM] x'); print('violations: 41')"]
        quiet = [sys.executable, "-c", "print('violations: 0')"]
        rc, lines = enforce.run(self.project, "layers", warn, count_regex=r"violations: (\d+)", violation_exit="0,1",
                                violation_pattern=r"Architecture Violation")
        self.assertEqual(rc, 0, lines)                                   # advisory passes, but it is a violation
        self.assertEqual(enforce.run(self.project, "layers", quiet, violation_exit="0,1", violation_pattern=r"Architecture Violation")[0], 0)
        e = self.ledger()
        self.assertEqual([(x["kind"], x.get("count")) for x in e], [("violation", 41), ("clean", None)])
        self.assertEqual(e[0]["exit_code"], 0)

    def test_exit_zero_as_violation_needs_a_pattern(self):
        self.manifest({"layers": "advisory"})
        with self.assertRaises(ValueError):
            enforce.run(self.project, "layers", PASS, violation_exit="0,1")
        with self.assertRaises(SystemExit):
            enforce.main(["run", "--project", str(self.project), "--family", "layers", "--violation-exit", "0", "--", *PASS])

    def test_a_wrong_entry_is_corrected_by_appending(self):
        # the ledger is append-only: a correction names the entry by time and family and says what it really was
        self.manifest({"layers": "advisory"})
        enforce.run(self.project, "layers", PASS)
        at = self.ledger()[0]["at"]
        self.assertEqual(enforce.main(["correct", "--project", str(self.project), "--family", "layers", "--at", at,
                                       "--as", "violation", "--count", "41", "--reason", "warning-mode checker exits 0"]), 0)
        raw = self.ledger()
        self.assertEqual([x["kind"] for x in raw], ["clean", "correction"])        # nothing is rewritten
        (eff,) = enforce.effective(raw)
        self.assertEqual((eff["kind"], eff["count"], eff["corrected_by"]["reason"]), ("violation", 41, "warning-mode checker exits 0"))
        self.assertNotEqual(enforce.main(["correct", "--project", str(self.project), "--family", "layers", "--at", "2000-01-01T00:00:00+00:00",
                                          "--as", "void", "--reason", "x"]), 0)  # an entry that does not exist
        with self.assertRaises(SystemExit):
            enforce.main(["correct", "--project", str(self.project), "--family", "layers", "--at", at, "--as", "void"])   # reason required

    def test_unknown_grade_is_refused(self):
        self.manifest({"layers": "soft"})
        with self.assertRaises(SystemExit):
            enforce.grades(self.project)


if __name__ == "__main__":
    unittest.main()
