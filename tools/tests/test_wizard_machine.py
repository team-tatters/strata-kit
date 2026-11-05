"""The header names this machine and the latest handoff's work tied to other machines (MB-strata-kit-2026-049)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402

HANDOFF = """---
type: session
machine: work-laptop
next_session: "none"
---
```yaml
in_progress:
  - description: "here"
    blocker: "b"
    unblocked_by: "c"
  - description: "push the shuttle commit"
    machine: home-laptop
    blocker: "only there"
    unblocked_by: "push there"
```
"""


class MachineHeaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.project = root / "demo"
        (self.project / ".strata").mkdir(parents=True)
        (self.project / ".strata" / "profile.yaml").write_text("profile: embedded\nproject: demo\n", encoding="utf-8")
        self.vault = root / "vault"
        s = self.vault / "projects" / "demo" / "sessions"; s.mkdir(parents=True)
        (s / "session-x.md").write_text(HANDOFF, encoding="utf-8")
        (s / "latest.md").symlink_to("session-x.md")
        (self.vault / "env-config.yaml").write_text(
            "environments:\n  work-laptop:\n    fingerprint: \"%s\"\n" % wizard_fp(), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def header(self, alias):
        env = {"STRATA_VAULT": str(self.vault), "STRATA_ENV": alias, "STRATA_MACHINE_ID": "id-1"}
        with mock.patch.dict(os.environ, env, clear=False):
            return wizard.header(self.project, wizard.KIT, "en", {"hook_event_name": "SessionStart", "source": "startup"})

    def test_registered_machine_and_other_machines_work(self):
        h = self.header("work-laptop").splitlines()
        self.assertTrue(any(l.startswith("machine: work-laptop (registered)") for l in h))
        other = next(l for l in h if l.startswith("latest handoff pending for other machines:"))
        self.assertIn("home-laptop 1 (push the shuttle commit)", other)

    def test_on_the_other_machine_its_own_work_is_not_flagged(self):
        h = self.header("home-laptop").splitlines()
        self.assertTrue(any(l.startswith("machine: home-laptop — WARN") for l in h))
        self.assertFalse(any(l.startswith("latest handoff pending for other machines:") for l in h))


def wizard_fp():
    from kb.machine import fingerprint
    return fingerprint("id-1")


if __name__ == "__main__":
    unittest.main()
