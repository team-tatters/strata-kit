"""diagnose and recommend are read-only unless --apply (or --out DIR), recommend never replaces an approved proposal
(it writes proposal.next.yaml beside it), and a detached project's previous answers come from the vault proposal
first — the repo copy can be stale (a detached project lost a person's soft-delete adoption that way, audit 2026-11-05)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
WIZ = KIT / "tools" / "wizard.py"
SOFT = "rec.data.soft-delete-only"


class ProposalWriteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.project, self.vault = root / "demo", root / "vault"
        (self.project / ".strata" / "local").mkdir(parents=True)
        self.kit = self.project / ".strata" / "kit"
        self.env = {**os.environ, "STRATA_VAULT": str(self.vault), "STRATA_USER_CONFIG": str(root / "none.yaml")}

    def tearDown(self):
        self.tmp.cleanup()

    def wiz(self, *args) -> subprocess.CompletedProcess:
        r = subprocess.run([sys.executable, str(WIZ), *args], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def detach(self) -> Path:
        tier = self.vault / "projects" / "demo" / "strata"
        (tier / "kit").mkdir(parents=True)
        (self.project / ".strata" / "local" / "vault-link.yaml").write_text(f"profile: detached\nvault_project_path: {tier.parent}\n")
        return tier

    def test_diagnose_and_recommend_are_read_only_without_apply(self):
        self.wiz("diagnose", str(self.project))
        self.wiz("recommend", str(self.project), "--profile", "core.generic")
        self.assertFalse(self.kit.exists() and any(self.kit.iterdir()), list(self.kit.iterdir()) if self.kit.exists() else [])

    def test_out_and_apply_write(self):
        out = Path(self.tmp.name) / "review"
        self.wiz("diagnose", str(self.project), "--out", str(out))
        self.wiz("recommend", str(self.project), "--profile", "core.generic", "--out", str(out))
        self.assertTrue((out / "diagnosis.yaml").is_file() and (out / "proposal.yaml").is_file())
        self.wiz("recommend", str(self.project), "--profile", "core.generic", "--apply")
        self.assertTrue((self.kit / "proposal.yaml").is_file())

    def test_approved_proposal_is_never_overwritten(self):
        self.kit.mkdir(parents=True)
        approved = {"profile": "core.generic", "approved": True, "cards": [], "marker": "human-approved"}
        (self.kit / "proposal.yaml").write_text(yaml.safe_dump(approved))
        r = self.wiz("recommend", str(self.project), "--profile", "core.generic", "--apply")
        self.assertEqual(yaml.safe_load((self.kit / "proposal.yaml").read_text())["marker"], "human-approved")
        nxt = yaml.safe_load((self.kit / "proposal.next.yaml").read_text())
        self.assertFalse(nxt["approved"])
        self.assertIn("proposal.next.yaml", r.stdout)

    def test_detached_previous_answers_come_from_the_vault(self):
        tier = self.detach()
        (tier / "kit" / "proposal.yaml").write_text(yaml.safe_dump({"approved": True, "adoption": [
            {"id": SOFT, "adopted": True, "answered": True}]}))
        self.kit.mkdir(parents=True)
        (self.kit / "proposal.yaml").write_text(yaml.safe_dump({"approved": False, "adoption": [
            {"id": SOFT, "adopted": False, "answered": False}]}))   # stale repo copy
        out = Path(self.tmp.name) / "review"
        self.wiz("recommend", str(self.project), "--profile", "core.generic", "--out", str(out))
        p = yaml.safe_load((out / "proposal.yaml").read_text())
        soft = next(a for a in p["adoption"] if a["id"] == SOFT)
        self.assertTrue(soft["adopted"] and soft["answered"], soft)
        self.assertIn("$STRATA_VAULT/projects/demo/strata/kit/proposal.yaml", soft["answer_from"])
        self.assertIn(SOFT, [c["id"] for c in p["cards"]])

    def test_a_given_answer_beats_the_previous_one(self):
        tier = self.detach()
        (tier / "kit" / "proposal.yaml").write_text(yaml.safe_dump({"adoption": [{"id": SOFT, "adopted": True, "answered": True}]}))
        out = Path(self.tmp.name) / "review"
        self.wiz("recommend", str(self.project), "--profile", "core.generic", "--decline", f"{SOFT}=아카이브 저장소", "--out", str(out))
        soft = next(a for a in yaml.safe_load((out / "proposal.yaml").read_text())["adoption"] if a["id"] == SOFT)
        self.assertEqual((soft["adopted"], soft["declined_reason"]), (False, "아카이브 저장소"))

    def test_help_says_what_writes(self):
        r = self.wiz("--help")
        self.assertNotIn("all read-only unless --apply)", r.stdout)
        self.assertIn("proposal.next.yaml", r.stdout)


if __name__ == "__main__":
    unittest.main()
