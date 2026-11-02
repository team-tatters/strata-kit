"""tools/metrics.py (order 2026.10.29-14 task-07, DEC-2026-10-29-16): transcript counters and the accumulating store."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import metrics  # noqa: E402


def a(mid, ctx, out, *tools, side=False, ts="2026-10-29T10:00:00Z"):
    content = [{"type": "tool_use", "name": n, "input": inp} for n, inp in tools] or [{"type": "text", "text": "x"}]
    return {"type": "assistant", "sessionId": "s1", "timestamp": ts, "isSidechain": side,
            "message": {"id": mid, "usage": {"input_tokens": ctx, "cache_read_input_tokens": 0, "output_tokens": out}, "content": content}}


class SessionRowTest(unittest.TestCase):
    def test_counters(self):
        lines = [
            {"type": "user", "timestamp": "2026-10-29T10:00:00Z", "message": {"content": "hi"}},
            a("m1", 1000, 10, ("Skill", {"skill": "using-strata"})),
            a("m1", 1000, 10, ("Bash", {})),                      # same message id: usage counted once
            a("m2", 1200, 20, ("Read", {})),
            a("sub", 999, 999, ("Edit", {}), side=True),          # a subagent's turn is not the session's
            {"type": "user", "permissionDecision": {"decision": "accept", "source": "user_temporary"}, "message": {"content": [{"type": "tool_result", "is_error": True}]}},
            {"type": "user", "toolDenialKind": "automode-blocked", "message": {"content": []}},
            a("m3", 1500, 30, ("Edit", {}), ts="2026-10-29T10:30:00Z"),
            {"type": "cost-state", "totalCostUSD": 1.23456, "totalLinesAdded": 5, "totalLinesRemoved": 1},
            "not an object",
        ]
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s1.jsonl"
            f.write_text("\n".join(json.dumps(l) for l in lines) + "\n{broken\n", encoding="utf-8")
            r = metrics.session_row(f)
        self.assertEqual(r["session"], "s1")
        self.assertEqual(r["assistant_turns"], 3)
        self.assertEqual(r["first_turn_context_tokens"], 1000)
        self.assertEqual(r["output_tokens"], 60)
        self.assertEqual((r["turns_before_first_edit"], r["output_tokens_before_first_edit"]), (3, 60))
        self.assertEqual(r["skills"], {"using-strata": 1})
        self.assertEqual(r["tool_calls"], 4)
        self.assertEqual((r["approvals_by_person"], r["denials"], r["tool_errors"]), (1, {"automode-blocked": 1}, 1))
        self.assertEqual((r["cost_usd"], r["lines_added"], r["minutes"]), (1.2346, 5, 30.0))

    def test_loaded_revision_from_the_header(self):
        hook = {"type": "attachment", "attachment": {"type": "hook_success", "hookEvent": "SessionStart",
                "content": "strata · project demo\ncore revision: aaa111+dirty · adapter revision: bbb222 (kit now: ccc333)\n"}}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.jsonl"; f.write_text(json.dumps(hook) + "\n" + json.dumps(a("m1", 10, 1)) + "\n")
            r = metrics.session_row(f)
        self.assertEqual(r["loaded"], {"guidance_revision": "aaa111+dirty", "adapter_revision": "bbb222", "kit_revision": "ccc333"})

    def test_no_edit_leaves_the_field_absent(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.jsonl"; f.write_text(json.dumps(a("m1", 10, 1, ("Read", {}))) + "\n")
            r = metrics.session_row(f)
        self.assertNotIn("turns_before_first_edit", r)
        self.assertFalse(r["edited"])


class StoreTest(unittest.TestCase):
    def test_transcript_dir_encoding(self):
        self.assertEqual(metrics.transcript_dir(Path("/work/alice/shop_web"), Path("/h")),
                         Path("/h/.claude/projects/-work-alice-shop-web"))

    def test_merge_keeps_deleted_transcripts(self):
        old = {"sessions": {"a": {"minutes": 1}}, "revisions": {"r1": {}}, "evidence": {"entries": 1}}
        new = {"sessions": {"b": {"minutes": 2}}, "revisions": {"r2": {}}, "evidence": {"entries": 3}}
        m = metrics.merge(old, new)
        self.assertEqual(set(m["sessions"]), {"a", "b"}); self.assertEqual(set(m["revisions"]), {"r1", "r2"})
        self.assertEqual(m["evidence"], {"entries": 3})

    def test_merge_appends_history(self):
        old = {"collected": "t1", "sessions": {}, "revisions": {}, "handoffs": {"handoffs": 2, "pending_items": 4}}
        new = {"collected": "t2", "sessions": {}, "revisions": {}, "handoffs": {"handoffs": 3, "pending_items": 9}, "git": None}
        m = metrics.merge(old, new)   # a file without history seeds it with its own last collection
        self.assertEqual([h["collected"] for h in m["history"]], ["t1", "t2"])
        self.assertEqual(m["history"][1]["handoffs"]["pending_items"], 9)
        self.assertNotIn("git", m["history"][1])
        m2 = metrics.merge(m, {**new, "collected": "t3"})
        self.assertEqual([h["collected"] for h in m2["history"]], ["t1", "t2", "t3"])
        self.assertEqual(metrics.merge({}, new)["history"], [metrics.snapshot(new)])

    def test_reverts_counted_by_subject_start_only(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            env = {"GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@x", "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@x", "PATH": "/usr/bin:/bin"}
            run = lambda *c: subprocess.run(["git", "-C", d, *c], check=True, capture_output=True, env=env)
            run("init", "-q")
            for msg in ("feature: count 되돌림 and Revert in metrics", 'Revert "feature"', "되돌림: 잘못 넣은 설정", "Reverted wording"):
                run("commit", "-q", "--allow-empty", "-m", msg)
            g = metrics.git_counts(Path(d), "2000-01-01")
            self.assertEqual((g["commits"], g["reverts"]), (4, 2))

    def test_recollected_revision_moves_to_the_end(self):
        old = {"sessions": {}, "revisions": {"r1": {"n": 1}, "r2": {"n": 2}}}
        m = metrics.merge(old, {"sessions": {}, "revisions": {"r1": {"n": 3}}})
        self.assertEqual(list(m["revisions"]), ["r2", "r1"]); self.assertEqual(m["revisions"]["r1"], {"n": 3})

    def test_summary_medians_per_revision(self):
        s = metrics.summary({"sessions": {"a": {"kit_revision": "r1", "first_turn_context_tokens": 10, "denials": {"x": 1}},
                                          "b": {"kit_revision": "r1", "first_turn_context_tokens": 30, "denials": {}},
                                          "c": {"kit_revision": "r2"}}})
        self.assertEqual(s["r1"]["first_turn_context_tokens"], 20)
        self.assertEqual(s["r1"]["denials"], 1)
        self.assertIsNone(s["r2"]["first_turn_context_tokens"])



class ViolationCountsTest(unittest.TestCase):
    """MB-strata-kit-2026-046: the ledger is counted with corrections applied, and metrics finds the kit's kb package
    when it runs from another directory (the librarian runs it from the vault)."""

    def test_corrections_apply_from_any_directory(self):
        import json, subprocess, sys, tempfile
        from pathlib import Path
        kit = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as d:
            led = Path(d) / "projects" / "demo" / "measurements"; led.mkdir(parents=True)
            (led / "violations.yaml").write_text(
                'entries:\n  - {"at": "t1", "family": "layers", "kind": "clean", "grade": "advisory"}\n'
                '  - {"at": "t2", "family": "layers", "kind": "correction", "corrects": "t1", "as": "violation", "count": 41, "reason": "exit 0"}\n')
            code = (f"import sys; sys.path.insert(0, {str(kit / 'tools')!r}); import metrics, json; from pathlib import Path; "
                    f"print(json.dumps(metrics.violation_counts('demo', Path({d!r}))))")
            r = subprocess.run([sys.executable, "-c", code], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"layers:violation:advisory": {"runs": 1, "last_count": 41, "last_at": "t1"}})


if __name__ == "__main__":
    unittest.main()
