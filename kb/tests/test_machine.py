import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import machine  # noqa: E402

REG = """# header comment
environments:
  work-laptop:
    description: "office"
    os: darwin
    fingerprint: "aaaaaaaaaaaa"
    last_active: 2026-11-03
  home-laptop:
    description: "home"
    os: darwin
    former_aliases: [laptop-old]
    last_active: 2026-11-03
"""


class FingerprintTest(unittest.TestCase):
    def test_hash_is_short_stable_and_never_the_raw_value(self):
        a = machine.fingerprint("F18DD972-0000-1111-2222-333344445555")
        self.assertEqual(a, machine.fingerprint("F18DD972-0000-1111-2222-333344445555"))
        self.assertEqual(len(a), 12)
        self.assertNotIn("F18DD972".lower(), a)
        self.assertNotEqual(a, machine.fingerprint("other"))

    def test_override_for_tests_and_other_os(self):
        self.assertEqual(machine.raw_machine_id({"STRATA_MACHINE_ID": "x"}), "x")


class AliasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Path(self.tmp.name) / "config.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_wins_and_a_disagreeing_config_is_named(self):
        self.cfg.write_text('machine:\n  alias: "other"\n', encoding="utf-8")
        alias, note = machine.current_alias({"STRATA_ENV": "work-laptop"}, self.cfg)
        self.assertEqual(alias, "work-laptop")
        self.assertIn("other", note)

    def test_config_when_env_is_unset(self):
        self.cfg.write_text('machine:\n  alias: "work-laptop"\n', encoding="utf-8")
        self.assertEqual(machine.current_alias({}, self.cfg), ("work-laptop", None))

    def test_none_when_neither(self):
        self.assertEqual(machine.current_alias({}, self.cfg)[0], None)


class CheckTest(unittest.TestCase):
    def setUp(self):
        self.reg = yaml.safe_load(REG)["environments"]

    def test_ok(self):
        self.assertEqual(machine.check(self.reg, "work-laptop", "aaaaaaaaaaaa").status, "ok")

    def test_alias_used_on_another_machine(self):
        self.assertEqual(machine.check(self.reg, "work-laptop", "bbbbbbbbbbbb").status, "alias-on-other-machine")

    def test_fingerprint_known_under_another_alias_is_a_rename(self):
        r = machine.check(self.reg, "new-name", "aaaaaaaaaaaa")
        self.assertEqual(r.status, "renamed")
        self.assertIn("work-laptop", r.message)

    def test_former_alias_points_to_the_current_one(self):
        r = machine.check(self.reg, "laptop-old", None)
        self.assertEqual(r.status, "former-alias")
        self.assertIn("home-laptop", r.message)

    def test_registered_without_fingerprint_is_pending(self):
        self.assertEqual(machine.check(self.reg, "home-laptop", "cccccccccccc").status, "fingerprint-pending")

    def test_unregistered_and_missing(self):
        self.assertEqual(machine.check(self.reg, "brand-new", "dddddddddddd").status, "unregistered")
        self.assertEqual(machine.check(self.reg, None, "dddddddddddd").status, "no-alias")

    def test_header_line_never_blocks_and_names_the_alias(self):
        line = machine.header_line(self.reg, "work-laptop", "aaaaaaaaaaaa")
        self.assertTrue(line.startswith("machine: work-laptop"))
        self.assertIn("python3 -m kb machine register", machine.header_line(self.reg, "brand-new", "d" * 12))


class RegisterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "env-config.yaml").write_text(REG, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_fills_a_pending_fingerprint(self):
        machine.register(self.vault, "home-laptop", "cccccccccccc", today="2026-11-04")
        e = machine.load_registry(self.vault)["home-laptop"]
        self.assertEqual(e["fingerprint"], "cccccccccccc")
        self.assertEqual(e["former_aliases"], ["laptop-old"])
        self.assertTrue((self.vault / "env-config.yaml").read_text(encoding="utf-8").startswith("#"))

    def test_rename_moves_the_old_alias_to_former(self):
        machine.register(self.vault, "work-mac", "aaaaaaaaaaaa", today="2026-11-04")
        reg = machine.load_registry(self.vault)
        self.assertNotIn("work-laptop", reg)
        self.assertIn("work-laptop", reg["work-mac"]["former_aliases"])

    def test_changed_fingerprint_keeps_the_old_one(self):
        machine.register(self.vault, "work-laptop", "eeeeeeeeeeee", today="2026-11-04", replace_fingerprint=True)
        e = machine.load_registry(self.vault)["work-laptop"]
        self.assertEqual(e["fingerprint"], "eeeeeeeeeeee")
        self.assertIn("aaaaaaaaaaaa", e["former_fingerprints"])

    def test_refuses_to_take_an_alias_another_machine_holds(self):
        with self.assertRaises(ValueError):
            machine.register(self.vault, "work-laptop", "eeeeeeeeeeee", today="2026-11-04")


class SessionDocTest(unittest.TestCase):
    def test_new_session_doc_must_carry_this_machine(self):
        self.assertIsNone(machine.session_machine_problem({"type": "session", "machine": "work-laptop"}, "work-laptop", None))
        p = machine.session_machine_problem({"type": "session", "machine": "home-laptop"}, "work-laptop", None)
        self.assertIn("work-laptop", p)

    def test_editing_another_machines_handoff_keeps_its_value(self):
        self.assertIsNone(machine.session_machine_problem({"type": "session", "machine": "home-laptop"}, "work-laptop", "home-laptop"))
        p = machine.session_machine_problem({"type": "session", "machine": "laptop"}, "work-laptop", "home-laptop")
        self.assertIsNotNone(p)

    def test_editing_a_legacy_handoff_without_machine_may_leave_it_unset(self):
        # a handoff committed before the machine field existed: leaving it unset is not a forgery
        self.assertIsNone(machine.session_machine_problem({"type": "session"}, "work-laptop", machine.UNRECORDED))
        self.assertIsNone(machine.session_machine_problem({"type": "session", "machine": "work-laptop"}, "work-laptop", machine.UNRECORDED))
        self.assertIsNotNone(machine.session_machine_problem({"type": "session", "machine": "laptop"}, "work-laptop", machine.UNRECORDED))
        # a new file (nothing committed) still has to carry this machine
        self.assertIsNotNone(machine.session_machine_problem({"type": "session"}, "work-laptop", None))

    def test_other_docs_and_unknown_alias_are_not_judged(self):
        self.assertIsNone(machine.session_machine_problem({"type": "concept", "machine": "x"}, "work-laptop", None))
        self.assertIsNone(machine.session_machine_problem({"type": "session", "machine": "x"}, None, None))


HANDOFF = """---
type: session
machine: work-laptop
next_session: "none"
---
## 진행 중
```yaml
in_progress:
  - description: "a"
    blocker: "b"
    unblocked_by: "c"
  - description: "push shuttle commit"
    machine: home-laptop
    blocker: "commit only there"
    unblocked_by: "push there"
  - description: "x"
    machine: work-laptop
    blocker: "b"
    unblocked_by: "c"
```
"""


class PendingTest(unittest.TestCase):
    def test_items_split_by_machine(self):
        here, others = machine.pending_by_machine(HANDOFF, "work-laptop")
        self.assertEqual(here, 2)
        self.assertEqual(others, {"home-laptop": ["push shuttle commit"]})

    def test_handoff_without_block(self):
        self.assertEqual(machine.pending_by_machine("---\ntype: session\n---\n", "work-laptop"), (0, {}))


if __name__ == "__main__":
    unittest.main()
