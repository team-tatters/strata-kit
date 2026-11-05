"""Empty-rule guard (MB-strata-kit-2026-057 step 1): a declared rule that evaluates no target is 'judgement
impossible — the declaration does not match the code', never clean. Covers the edit hook (unmapped file), the layer
map audit (a mapping that matches no file), kb boundaries check (a module or changelog that is not there, no table
found), kb enforce (a run without the expected output marker, or one that says it is indeterminate) and the ArchUnit
templates (no silent allowEmptyShould, failOnEmptyShould left at its default)."""
import contextlib
import io
import json
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

KB = Path(__file__).resolve().parents[1]
KIT = KB.parent
ENF = KIT / "profiles" / "backend.kotlin-spring-cqrs" / "enforcement"

MAP = """version: "1.0"
project: "demo"
project_type: "backend"
mappings:
  - path: "svc/l2/"
    layer: "L2_DataLayer"
  - path: "svc/l3/"
    layer: "L3_Composite"
excluded:
  - "svc/old/"
"""


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LayerHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "demo"
        w(self.repo / "CLAUDE.md", "# demo\n")
        w(self.repo / ".strata" / "layer-map.yaml", MAP)
        w(self.repo / "svc" / "l2" / "OrderRepository.kt", "package x\n")
        w(self.repo / "svc" / "l3" / "OrderCompositeService.kt", "package x\n")

    def tearDown(self):
        self.tmp.cleanup()

    def kb(self, *args, payload=None):
        return subprocess.run(["python3", str(KB), *args], input=json.dumps(payload) if payload else None, cwd=self.repo,
                              capture_output=True, text=True)

    def edit(self, rel):
        f = self.repo / rel
        w(f, "package x\nclass A\n")
        return self.kb("check-layer", payload={"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(f)}})

    def test_unmapped_code_file_is_reported_not_passed_silently(self):
        r = self.edit("svc/misc/OrderHelper.kt")
        self.assertEqual(r.returncode, 0, r.stderr)                     # advisory: told, not blocked
        self.assertIn("판정 불가", r.stdout)
        self.assertIn("additionalContext", r.stdout)

    def test_mapped_excluded_test_and_build_files_stay_quiet(self):
        for rel in ("svc/l2/OrderQuery.kt", "svc/old/Legacy.kt", "svc/src/test/kotlin/ATest.kt", "build.gradle.kts", "docs/a.md",
                    "tests/test_a.py"):
            r = self.edit(rel)
            self.assertNotIn("판정 불가", r.stdout + r.stderr, rel)

    def test_a_package_named_test_under_src_main_is_code(self):
        # a test-support module's production sources (components/test-descriptor/src/main/kotlin/…/components/test/)
        self.assertIn("판정 불가", self.edit("svc/x/src/main/kotlin/io/a/test/Builder.kt").stdout)

    def test_no_layer_map_no_notice(self):
        (self.repo / ".strata" / "layer-map.yaml").unlink()
        self.assertNotIn("판정 불가", self.edit("svc/misc/OrderHelper.kt").stdout)

    def test_audit_reports_a_mapping_that_matches_no_file(self):
        ok = self.kb("check-layer", "--audit", "--project", str(self.repo))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertNotIn("indeterminate", ok.stdout)
        w(self.repo / ".strata" / "layer-map.yaml", MAP.replace('"svc/l3/"', '"svc/composite/"'))
        bad = self.kb("check-layer", "--audit", "--project", str(self.repo))
        self.assertEqual(bad.returncode, 3, bad.stdout + bad.stderr)
        self.assertIn("[strata] indeterminate:", bad.stdout)
        self.assertIn("svc/composite/", bad.stdout)

    def test_audit_with_no_mapped_file_at_all_is_indeterminate(self):
        w(self.repo / ".strata" / "layer-map.yaml", MAP.replace("svc/l2/", "nope/a/").replace("svc/l3/", "nope/b/"))
        r = self.kb("check-layer", "--audit", "--project", str(self.repo))
        self.assertEqual(r.returncode, 3)
        self.assertIn("판정 불가", r.stdout)


RES = "src/main/resources/config/liquibase"


class BoundariesGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def module(self, rel, sql=None):
        d = self.root / rel
        w(d / "build.gradle.kts", "")
        w(d / "src/main/kotlin/demo/A.kt", "package demo\n")
        for name, text in (sql or {}).items():
            w(d / RES / "changelogs" / name, text)

    def check(self, modules):
        return bd.check(self.root, {"boundaries": {"modules": modules}}, today=date(2026, 11, 5))

    def main(self, modules):
        w(self.root / ".strata/layer-map.yaml", yaml.safe_dump({"boundaries": {"modules": modules}}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = bd.main(["check", "--project", str(self.root)])
        return rc, out.getvalue()

    def test_a_module_path_that_does_not_exist_is_indeterminate_not_clean(self):
        self.module("domain/a", {"init.sql": "CREATE TABLE a (id int);"})
        r = self.check({"domain/a": "x", "domain/gone": "x"})
        self.assertEqual(r["findings"], [])
        self.assertTrue(any("domain/gone" in i for i in r["indeterminate"]))
        rc, out = self.main({"domain/a": "x", "domain/gone": "x"})
        self.assertEqual(rc, 3)
        self.assertIn("[strata] indeterminate:", out)

    def test_a_module_with_no_changelog_is_indeterminate(self):
        self.module("domain/a", {"init.sql": "CREATE TABLE a (id int);"})
        self.module("domain/b")
        r = self.check({"domain/a": "x", "domain/b": "x"})
        self.assertTrue(any("domain/b" in i and "changelog" in i for i in r["indeterminate"]))

    def test_an_explicit_changelog_that_is_not_there_is_indeterminate(self):
        self.module("domain/a", {"init.sql": "CREATE TABLE a (id int);"})
        r = self.check({"domain/a": {"db": "x", "changelogs": ["src/main/resources/nope.yaml"]}})
        self.assertTrue(any("nope.yaml" in i for i in r["indeterminate"]))

    def test_no_table_found_anywhere_is_indeterminate(self):
        self.module("domain/a", {"init.sql": "-- nothing here\nSELECT 1;"})
        r = self.check({"domain/a": "x"})
        self.assertTrue(any("테이블" in i for i in r["indeterminate"]))

    def test_findings_still_win_over_indeterminate(self):
        self.module("domain/a", {"init.sql": "CREATE TABLE t (id int);"})
        self.module("domain/b", {"init.sql": "CREATE TABLE t (id int);"})
        rc, out = self.main({"domain/a": "x", "domain/b": "x", "domain/gone": "x"})
        self.assertEqual(rc, 1)
        self.assertIn("[strata] indeterminate:", out)

    def test_a_matching_declaration_stays_clean(self):
        self.module("domain/a", {"init.sql": "CREATE TABLE a (id int);"})
        rc, out = self.main({"domain/a": "x"})
        self.assertEqual(rc, 0, out)
        self.assertNotIn("indeterminate", out)


class EnforceGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name)
        self.project, self.vault = r / "demo", r / "vault"
        (self.project / ".strata").mkdir(parents=True)
        self.vault.mkdir()
        self.old = os.environ.get("STRATA_VAULT")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("STRATA_VAULT", None)
        else:
            os.environ["STRATA_VAULT"] = self.old
        self.tmp.cleanup()

    def manifest(self, enforcement):
        w(self.project / ".strata" / "profile.yaml", yaml.safe_dump({"profile": "embedded", "project": "demo", "enforcement": enforcement}))

    def ledger(self):
        return yaml.safe_load((self.vault / "projects/demo/measurements/violations.yaml").read_text(encoding="utf-8"))["entries"]

    @staticmethod
    def out(text, rc=0):
        return [sys.executable, "-c", f"print({text!r}); raise SystemExit({rc})"]

    def test_quiet_run_without_the_expected_marker_is_not_clean(self):
        # `./gradlew archCheck -q` hides the test output: exit 0 and nothing printed used to be recorded as clean
        self.manifest({"layers": "advisory"})
        rc, lines = enforce.run(self.project, "layers", self.out(""), expect_pattern=r"\[strata-arch\] layers warnings")
        self.assertEqual(rc, 0, lines)                               # advisory: recorded, not blocking
        self.assertIn("판정 불가", "\n".join(lines))
        e = self.ledger()[-1]
        self.assertEqual(e["kind"], "checker_error")
        self.assertTrue(e["indeterminate"])
        self.manifest({"layers": "block"})
        self.assertEqual(enforce.run(self.project, "layers", self.out(""), expect_pattern=r"\[strata-arch\] layers warnings")[0], 2)

    def test_expected_marker_present_is_clean(self):
        self.manifest({"layers": "block"})
        rc, _ = enforce.run(self.project, "layers", self.out("[strata-arch] layers warnings 0 (baseline 0)"),
                            expect_pattern=r"\[strata-arch\] layers warnings")
        self.assertEqual(rc, 0)
        self.assertEqual(self.ledger()[-1]["kind"], "clean")

    def test_checker_that_says_indeterminate_is_not_clean(self):
        self.manifest({"boundaries": "advisory"})
        for rc_ in (0, 3):
            rc, lines = enforce.run(self.project, "boundaries", self.out("[strata] indeterminate: domain/gone: module directory not found", rc_))
            self.assertEqual(rc, 0, lines)
            e = self.ledger()[-1]
            self.assertEqual((e["kind"], e.get("indeterminate")), ("checker_error", True))
            self.assertIn("domain/gone", e["reason"])

    def test_violations_with_an_indeterminate_part_stay_violations(self):
        self.manifest({"boundaries": "advisory"})
        enforce.run(self.project, "boundaries", self.out("finding x\n[strata] indeterminate: y", 1))
        e = self.ledger()[-1]
        self.assertEqual(e["kind"], "violation")
        self.assertEqual(e["indeterminate"], ["y"])

    def test_cli_flag(self):
        self.manifest({"layers": "advisory"})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            enforce.main(["run", "--family", "layers", "--project", str(self.project), "--expect-pattern", "ran", "--", *self.out("")])
        self.assertTrue(self.ledger()[-1]["indeterminate"])


class ArchUnitTemplateTest(unittest.TestCase):
    def templates(self):
        return {p.name: p.read_text(encoding="utf-8") for p in ENF.rglob("*.template")}

    def test_no_rule_allows_an_empty_should(self):
        # ArchUnit's archRule.failOnEmptyShould (default true since 0.23, verified on 1.4.1) fails a rule whose that()
        # matches nothing; allowEmptyShould(true) would turn that into a silent pass
        for name, text in self.templates().items():
            self.assertNotIn("allowEmptyShould(true)", text, name)

    def test_warning_mode_reports_an_empty_rule_as_indeterminate(self):
        t = self.templates()
        self.assertIn("failed to check any classes", t["StrataWarnings.kt.template"])
        self.assertIn('"[strata-arch] $family indeterminate:', t["StrataWarnings.kt.template"])
        self.assertIn("unmatchedMappings", t["StrataLayerMapTest.kt.template"])
        self.assertIn("unmatchedMappings", t["StrataLayerWarningsTest.kt.template"])

    def test_readme_explains_fail_on_empty_should_and_expects_the_marker(self):
        readme = (ENF / "README.md").read_text(encoding="utf-8")
        self.assertIn("archRule.failOnEmptyShould", readme)
        self.assertIn("archunit.properties", readme)
        self.assertIn("--expect-pattern '\\[strata-arch\\] layers warnings'", readme)
        self.assertIn("--expect-pattern '\\[strata-arch\\] boundaries warnings'", readme)


if __name__ == "__main__":
    unittest.main()
