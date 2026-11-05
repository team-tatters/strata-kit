"""kb boundaries (DEC-2026-11-05-02, MB-strata-kit-2026-051): data ownership and FDW read windows from Liquibase
changelogs and entity mappings, judged per database — never by table name across databases."""
import contextlib
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import boundaries as bd  # noqa: E402

KIT = Path(__file__).resolve().parents[2]
RES = "src/main/resources/config/liquibase"


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MASTER = """databaseChangeLog:
  - changeSet:
      id: 1
      author: t
      changes:
        - sqlFile:
            path: {res}/changelogs/{f}
            relativeToChangelogFile: false
"""


class BoundariesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def module(self, rel, sql=None, entities=None, master=True):
        d = self.root / rel
        w(d / "build.gradle.kts", "")
        for name, text in (sql or {}).items():
            w(d / RES / "changelogs" / name, text)
        if master and sql:
            items = "".join(MASTER.format(res=RES, f=n).split("\n", 1)[1] for n in sql if n.endswith(".sql"))
            w(d / RES / "changelog-master.yml", "databaseChangeLog:\n" + items)
        for name, text in (entities or {}).items():
            w(d / "src/main/kotlin/demo" / name, text)

    def run_check(self, boundaries, today=date(2026, 11, 5)):
        return bd.check(self.root, {"boundaries": boundaries}, today=today)

    def live(self, report, check=None):
        return [f for f in report["findings"] if not f["exempted_by"] and not f["excluded"] and (check is None or f["check"] == check)]

    # ---- data ownership: changelogs

    def test_same_table_in_two_modules_of_one_database(self):
        self.module("domain/mail-a", {"init.sql": 'CREATE TABLE IF NOT EXISTS "public"."email_logs" (id int8);'})
        self.module("domain/mail-b", {"init.sql": "create table email_logs (id bigint);"})
        r = self.run_check({"modules": {"domain/mail-a": "mail", "domain/mail-b": "mail"}})
        found = self.live(r, bd.CHECK_CHANGELOG)
        self.assertEqual(sorted(f["module"] for f in found), ["domain/mail-a", "domain/mail-b"])
        self.assertEqual({f["table"] for f in found}, {"email_logs"})
        self.assertTrue(all(f["line"] == 1 for f in found))

    def test_same_name_in_different_databases_is_not_compared(self):
        # 2.0 and 3.0 keep same-name tables in different databases: comparing names alone was +65 noise
        self.module("domain/old-entity", {"init.sql": "CREATE TABLE public.formula (id int);"})
        self.module("domain/new-entity", {"init.sql": "CREATE TABLE formula (id int);"})
        r = self.run_check({"modules": {"domain/old-entity": "legacy", "domain/new-entity": "orders"}})
        self.assertEqual(r["findings"], [])

    def test_yaml_create_rename_and_drop_follow_changelog_order(self):
        self.module("domain/a", {"1.sql": "CREATE TABLE associations (id int);\nCREATE TABLE tmp_seed (id int);",
                                 "2.sql": "ALTER TABLE IF EXISTS associations RENAME TO organization;\nDROP TABLE IF EXISTS tmp_seed CASCADE;"})
        d = self.root / "domain/b"
        w(d / "build.gradle.kts", "")
        w(d / RES / "changelog-master.yaml", """databaseChangeLog:
  - changeSet:
      id: 1
      author: t
      changes:
        - createTable:
            tableName: associations
            columns: []
        - createTable:
            tableName: tmp_seed
            columns: []
  - changeSet:
      id: 2
      author: t
      changes:
        - renameTable:
            oldTableName: tmp_seed
            newTableName: seed_archive
""")
        r = self.run_check({"modules": {"domain/a": "commons", "domain/b": "commons"}})
        # a renamed associations away and dropped tmp_seed; b renamed tmp_seed away — only associations is b's
        self.assertEqual(self.live(r), [])
        self.assertEqual((r["modules"]["domain/a"]["owned"], r["modules"]["domain/b"]["owned"]), (1, 2))

    def test_comments_and_rollback_lines_do_not_count(self):
        self.module("domain/a", {"1.sql": "--liquibase formatted sql\n--changeset t:1\nCREATE TABLE orders (id int);\n"
                                          "--rollback DROP TABLE orders;\n/* CREATE TABLE ghost (id int); */\n"
                                          "COMMENT ON TABLE orders IS 'create table quoted (x)';"})
        self.module("domain/b", {"1.sql": "CREATE TABLE orders (id int);"})
        r = self.run_check({"modules": {"domain/a": "shop", "domain/b": "shop"}})
        self.assertEqual({f["table"] for f in self.live(r)}, {"orders"})
        self.assertEqual(r["modules"]["domain/a"]["owned"], 1)

    def test_literal_dynamic_sql_counts(self):
        self.module("domain/a", {"1.sql": "CREATE TABLE legacy_sets (id int);",
                                 "2.sql": "DO $$ BEGIN\n  RAISE NOTICE 'create table not_this (x)';\n"
                                          "  EXECUTE 'DROP TABLE IF EXISTS legacy_sets';\nEND $$;"})
        r = self.run_check({"modules": {"domain/a": "x"}})
        self.assertEqual(r["modules"]["domain/a"]["owned"], 0)

    def test_alter_or_write_of_another_modules_table(self):
        self.module("domain/users", {"1.sql": "CREATE TABLE users (id int);"})
        self.module("domain/billing", {"1.sql": "CREATE TABLE invoices (id int, user_id int REFERENCES users (id) ON UPDATE CASCADE);\n"
                                                "ALTER TABLE users ADD COLUMN plan text;\nINSERT INTO public.users (id) VALUES (1);"})
        r = self.run_check({"modules": {"domain/users": "app", "domain/billing": "app"}})
        msgs = sorted(f["message"].split(" users")[0] for f in self.live(r, bd.CHECK_CHANGELOG))
        self.assertEqual(msgs, ["changelog of domain/billing alters", "changelog of domain/billing writes rows of"])

    def test_only_files_the_master_reaches_are_read(self):
        self.module("domain/a", {"1.sql": "CREATE TABLE a1 (id int);"})
        w(self.root / "domain/a" / RES / "changelogs/stale_copy.sql", "CREATE TABLE b1 (id int);")
        self.module("domain/b", {"1.sql": "CREATE TABLE b1 (id int);"})
        r = self.run_check({"modules": {"domain/a": "x", "domain/b": "x"}})
        self.assertEqual(self.live(r), [])
        self.assertEqual(r["unreached_changelogs"], {"domain/a": [f"domain/a/{RES}/changelogs/stale_copy.sql"]})

    def test_include_all_and_classpath_paths(self):
        d = self.root / "domain/a"
        w(d / "build.gradle.kts", "")
        w(d / RES / "db.changelog-master.xml", """<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">
  <include file="/config/liquibase/one.yaml"/>
  <includeAll path="config/liquibase/more/"/>
</databaseChangeLog>""")
        w(d / RES / "one.yaml", "databaseChangeLog:\n  - changeSet:\n      id: 1\n      author: t\n      changes:\n"
                                "        - sql:\n            sql: CREATE TABLE t_one (id int)\n")
        w(d / RES / "more/2.sql", "CREATE MATERIALIZED VIEW IF NOT EXISTS v_two AS SELECT 1;")
        r = self.run_check({"modules": {"domain/a": "x"}})
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["modules"]["domain/a"]["owned"], 2)

    # ---- data ownership: entity mappings

    def test_entity_mapping_a_table_another_module_owns(self):
        self.module("domain/users", {"1.sql": "CREATE TABLE users (id int);\nCREATE TABLE user_roles (id int);"})
        self.module("domain/admin", {"1.sql": "CREATE TABLE operators (id int);"}, entities={
            "User.kt": '@Entity\n@Table(name = "users", schema = "public")\nclass User(val id: Long)\n',
            "Role.kt": '@Table("user_roles")\ndata class Role(val id: Long)\n',
            "Operator.kt": "@Entity\nclass Operator(val id: Long)\n",
            "UserRoles.kt": "@Entity\nclass UserRoles(val id: Long)\n",
        })
        r = self.run_check({"modules": {"domain/users": "users", "domain/admin": "users"}})
        found = self.live(r, bd.CHECK_ENTITY)
        self.assertEqual(sorted((f["table"], f["path"].rsplit("/", 1)[-1], f["line"]) for f in found),
                         [("user_roles", "Role.kt", 2), ("user_roles", "UserRoles.kt", 2), ("users", "User.kt", 3)])
        self.assertIn("name from the class", next(f["message"] for f in found if f["path"].endswith("UserRoles.kt")))

    def test_entity_of_a_table_nobody_creates_is_info_only(self):
        self.module("domain/scm", entities={"Survey.kt": '@Entity\n@Table(name = "survey")\nclass Survey\n'})
        r = self.run_check({"modules": {"domain/scm": "scm"}})
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["mapped_without_owner"], {"domain/scm": ["survey"]})

    # ---- cross-domain read: FDW windows

    FDW = ("DO $$ BEGIN CREATE SERVER commons_fdw FOREIGN DATA WRAPPER postgres_fdw OPTIONS (dbname '${db}'); END $$;\n"
           "CREATE FOREIGN TABLE common_units_mv (id bigint) SERVER commons_fdw OPTIONS (schema_name 'public', table_name 'common_units_mv');")

    def fdw_project(self):
        self.module("domain/commons", {"1.sql": "CREATE MATERIALIZED VIEW common_units_mv AS SELECT 1 AS id;"})
        self.module("domain/orders", {"1.sql": self.FDW},
                    entities={"Unit.kt": '@Entity\n@Table(name = "common_units_mv")\nclass Unit\n'})

    def test_foreign_tables_are_read_windows_not_ownership(self):
        self.fdw_project()
        r = self.run_check({"modules": {"domain/commons": "commons", "domain/orders": "orders"}, "fdw_servers": {"commons_fdw": "commons"}})
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["modules"]["domain/orders"]["owned"], 0)
        [win] = r["read_windows"]
        self.assertEqual((win["consumer_db"], win["provider_db"], win["foreign_table"], win["remote"], win["canonical"]),
                         ("orders", "commons", "common_units_mv", "common_units_mv", None))
        self.assertEqual(r["undecided_read_windows"], ["orders → commons"])

    def test_server_placeholder_needs_fdw_servers(self):
        self.fdw_project()
        r = self.run_check({"modules": {"domain/commons": "commons", "domain/orders": "orders"}})
        self.assertTrue(any("commons_fdw" in p and "fdw_servers" in p for p in r["problems"]))

    def test_canonical_window_is_judged_only_when_decided(self):
        self.fdw_project()
        base = {"modules": {"domain/commons": "commons", "domain/orders": "orders"}, "fdw_servers": {"commons_fdw": "commons"}}
        feign = self.run_check({**base, "read_windows": {"orders": {"commons": "feign"}}})
        fdw = self.run_check({**base, "read_windows": {"orders": {"commons": "fdw"}}})
        self.assertEqual([f["check"] for f in self.live(feign)], [bd.CHECK_FDW])
        self.assertEqual((self.live(fdw), fdw["undecided_read_windows"]), ([], []))

    # ---- exemptions

    def dual(self):
        self.module("domain/a", {"1.sql": "CREATE TABLE audit_logs (id int);"})
        self.module("domain/b", {"1.sql": "CREATE TABLE audit_logs (id int);"})

    def test_exemption_needs_reason_and_decision_or_sunset(self):
        self.dual()
        mods = {"domain/a": "x", "domain/b": "x"}
        ok = self.run_check({"modules": mods, "exemptions": [
            {"id": "BX-1", "rule": "boundary.data_ownership", "table": "public.audit_logs", "reason": "audit", "decision": "DEC-1"}]})
        self.assertEqual((self.live(ok), {f["exempted_by"] for f in ok["findings"]}), ([], {"BX-1"}))
        bad = self.run_check({"modules": mods, "exemptions": [
            {"id": "BX-2", "rule": "boundary.data_ownership.changelog", "table": "audit_logs", "decision": "DEC-1"},
            {"id": "BX-3", "rule": "boundary.data_ownership.changelog", "table": "audit_logs", "reason": "r"},
            {"id": "BX-4", "rule": "boundary.data_ownership.changelog", "table": "audit_logs", "reason": "r", "sunset": "2026-01-01"},
            {"id": "BX-5", "rule": "boundary.nope", "table": "audit_logs", "reason": "r", "decision": "DEC-1"},
            {"id": "BX-6", "rule": "boundary.data_ownership.changelog", "table": "audit_logs", "reason": "r", "decision": "DEC-1", "status": "retired"},
        ]})
        self.assertEqual(len(self.live(bad)), 2)
        self.assertEqual(sorted(p.split(":")[0] for p in bad["problems"]), ["exemption BX-2", "exemption BX-3", "exemption BX-4", "exemption BX-5"])

    def test_future_sunset_and_narrow_exemption(self):
        self.dual()
        r = self.run_check({"modules": {"domain/a": "x", "domain/b": "x"}, "exemptions": [
            {"id": "BX-7", "rule": "boundary.data_ownership.changelog", "module": "domain/b", "reason": "moving", "sunset": "2026-12-31"}]})
        self.assertEqual([f["module"] for f in self.live(r)], ["domain/a"])

    def test_excluded_scope_is_counted_not_listed(self):
        # user decision 2026-11-05: the layer map's excluded: applies to the boundaries too — counted per module, apart from exemptions
        self.dual()
        self.module("service/legacy-api", {"1.sql": "INSERT INTO audit_logs VALUES (1);"})
        mods = {"domain/a": "x", "domain/b": "x", "service/legacy-api": "x"}
        r = bd.check(self.root, {"excluded": ["service/legacy-api/"], "boundaries": {"modules": mods}})
        self.assertEqual(sorted(f["module"] for f in self.live(r)), ["domain/a", "domain/b"])
        self.assertEqual(r["excluded_by_module"], {"service/legacy-api": 1})
        # a source path entry matches the module's other files too, as in the hook (fragments around src/main/kotlin/)
        r2 = bd.check(self.root, {"excluded": ["domain/b/src/main/kotlin/"], "boundaries": {"modules": mods}})
        self.assertEqual(r2["excluded_by_module"], {"domain/b": 1})
        self.assertTrue(all(f["exempted_by"] is None for f in r["findings"]))
        self.assertIn("1 in excluded scope", bd.render(r))
        self.assertTrue(bd.excluded_path("domain/b/build/classes/kotlin/main/demo/X.class", ["domain/b/src/main/kotlin/demo/"]))
        w(self.root / "archunit/layer-map.yaml", yaml.safe_dump({"excluded": ["service/legacy-api/"],
                                                                   "boundaries": {"modules": {"domain/a": "x", "service/legacy-api": "x"}}}))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bd.main(["check", "--project", str(self.root)]), 0)   # only the excluded module writes a's table

    # ---- configuration and CLI

    def test_module_by_unique_directory_name(self):
        self.dual()
        r = self.run_check({"modules": {"a": "x", "b": "x", "missing": "x"}})
        self.assertEqual(len(self.live(r)), 2)
        self.assertTrue(any(p.startswith("boundaries.modules.missing") for p in r["problems"]))

    def test_cli_exit_codes_and_map_lookup_order(self):
        self.dual()
        cfg = {"boundaries": {"modules": {"domain/a": "x", "domain/b": "x"}}}
        w(self.root / "archunit/layer-map.yaml", yaml.safe_dump(cfg))
        w(self.root / ".strata/layer-map.yaml", yaml.safe_dump({"boundaries": {"modules": {"domain/a": "x"}}}))
        self.assertEqual(bd.find_map(self.root), self.root / ".strata/layer-map.yaml")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            clean = bd.main(["check", "--project", str(self.root)])
            dirty = bd.main(["check", "--project", str(self.root), "--map", str(self.root / "archunit/layer-map.yaml")])
        self.assertEqual((clean, dirty), (0, 1))
        self.assertIn("audit_logs", out.getvalue())
        (self.root / ".strata/layer-map.yaml").unlink()
        self.assertEqual(bd.find_map(self.root), self.root / "archunit/layer-map.yaml")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bd.main(["check", "--project", str(Path(self.tmp.name))]), 2)

    def test_check_ids_match_layer_rules(self):
        rules = yaml.safe_load((KIT / "core/rules/layer-rules.yaml").read_text(encoding="utf-8"))["boundaries"]["rules"]
        self.assertEqual(set(rules), set(bd.BOUNDARIES))
        checks = {c for r in rules.values() for c in r["checks"]}
        self.assertEqual(checks, set(bd.KNOWN_CHECKS))
        self.assertTrue(all(c.startswith(b + ".") for b, r in rules.items() for c in r["checks"]))


if __name__ == "__main__":
    unittest.main()
