"""Runtime moved from strata/scripts into the kit (order 2026.10.29-11, MB-strata-kit-2026-011): `kb stamp`
stamps knowledge docs inside the vault and leaves other files alone, `kb atom-notify` never fails a hook, and
`kb handoff` refuses an option as a slug instead of creating a 'session-<date>---help' handoff."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]


def kb(*args, env=None, stdin=None):
    return subprocess.run([sys.executable, "-m", "kb", *args], cwd=KIT, env=env, input=stdin, capture_output=True, text=True)


class RuntimeMovedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "_meta").mkdir(parents=True)
        (self.vault / "_meta" / "taxonomy.yaml").write_text((KIT / "core/templates/vault/_meta/taxonomy.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        self.env = {**os.environ, "STRATA_VAULT": str(self.vault), "KB_NO_REFRESH": "1"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_stamp_updates_knowledge_doc_in_vault(self):
        doc = self.vault / "projects" / "p" / "knowledge-base" / "a.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("---\ntitle: A\nid: kb-p-a\ntype: concept\nproject: p\nstatus: active\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n# A\n", encoding="utf-8")
        r = kb("stamp", stdin=json.dumps({"tool_input": {"file_path": str(doc)}}), env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"updated: {datetime.date.today().isoformat()}", doc.read_text(encoding="utf-8"))

    def test_stamp_ignores_files_outside_the_vault(self):
        other = Path(self.tmp.name) / "notes.md"
        other.write_text("---\ntitle: x\nupdated: 2026-01-01\n---\n", encoding="utf-8")
        r = kb("stamp", stdin=json.dumps({"tool_input": {"file_path": str(other)}}), env=self.env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("updated: 2026-01-01", other.read_text(encoding="utf-8"))

    def test_atom_notify_never_fails(self):
        r = kb("atom-notify", "thinking", env={**self.env, "ATOM_PORT": "/dev/does-not-exist", "ATOM_TIMEOUT": "0.1"})
        self.assertEqual(r.returncode, 0)

    def test_handoff_rejects_option_as_slug(self):
        for arg, rc in (("--help", 0), ("-x", 2)):
            r = kb("handoff", arg, env=self.env)
            self.assertEqual(r.returncode, rc, r.stderr)
            self.assertIn("사용법", r.stderr)
        self.assertFalse(list(self.vault.rglob("session-*")))


    def test_handoff_blocks_follow_section_titles(self):
        """DEC-2026-10-30-03: each yaml block sits under its own section title, so a new section (판단 과정) does not shift
        warnings under the wrong heading."""
        r = kb("handoff", "demo", "t", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        (f,) = self.vault.rglob("session-*-demo.md")
        text = f.read_text(encoding="utf-8")
        for title, key in (("완료", "completed"), ("진행 중", "in_progress"), ("결정 사항", "decisions_made"),
                           ("판단 과정", "judgement"), ("사실과 가설", "findings"), ("주의 사항", "warnings")):
            self.assertIn(f"## {title}\n```yaml\n{key}: []\n", text)

    def test_handoff_shows_pending_divergence_requests(self):
        """DEC-2026-10-31-35: the handoff shows how many plan-versus-code requests wait for a person's judgement."""
        inbox = self.vault / "projects" / "demo-proj" / "_meta" / "divergence-inbox.yaml"
        inbox.parent.mkdir(parents=True)
        inbox.write_text("requests:\n- {id: DV-1, status: pending, planning: p.md, spec: null, diff: d}\n- {id: DV-2, status: judged, planning: q.md, spec: null, diff: d}\n", encoding="utf-8")
        proj = Path(self.tmp.name) / "demo-proj"; proj.mkdir(); (proj / "CLAUDE.md").write_text("x\n")
        r = subprocess.run([sys.executable, str(KIT / "kb"), "handoff", "demo", "t"], cwd=proj, env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        (f,) = self.vault.rglob("session-*-demo.md")
        self.assertIn("> 어긋남 판정 대기: 1건", f.read_text(encoding="utf-8"))

    def test_ledger_takes_the_documented_restart_entry(self):
        """DEC-2026-10-31-11 (session-restart-signals acceptance 6): the restart entry shown in agent-operations 5.3 —
        confirmed · assumed · discarded — appends to a ledger and the ledger validates."""
        import re
        doc = (KIT / "core/docs/en/methodology/agent-operations.md").read_text(encoding="utf-8")
        body = re.search(r"## \[primary\] 2026-06-01T15:10:00\+09:00\n\u200b```yaml\n(.*?)\n\u200b```", doc, re.S).group(1)
        for k in ("confirmed:", "assumed:", "discarded:"):
            self.assertIn(k, body)
        led = Path(self.tmp.name) / "ledger.md"
        led.write_text('---\nsession_id: s\nproject: p\nstatus: open\nactors: [primary]\ntopic: t\ncreated: 2026-10-31\nnext_session: null\n---\n', encoding="utf-8")
        r = kb("ledger", "append", str(led), "--actor", "primary", "--body", body, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = kb("ledger", "close", str(led), "--next", "session-x.md", "--reason", "restart signal", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = kb("ledger", "validate", str(led), env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

if __name__ == "__main__":
    unittest.main()
