"""Operations signals (planning/operations-signal acceptance 1~3·5·6, DEC-2026-11-01-14): the note format and its check
(evidence required, routed needs a person and an existing target, dropped needs a reason, open over 14 days is shown);
candidates from the measurement table (one per kind, previous collection or revision as the basis, the 10% threshold,
no duplicates, nothing written without --write); route records the person's choice and refuses a missing target."""
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT))

from kb import signals as S  # noqa: E402

TODAY = date(2026, 11, 2)
P = "demo"


def metrics(history=None, revisions=None, sessions=None) -> dict:
    return {"project": P, "collected": (history or [{}])[-1].get("collected", "t0"), "history": history or [],
            "revisions": revisions or {}, "sessions": sessions or {}}


def snap(at, failed=0, unstable=0, handoffs=10, pending=20, reverts=1):
    return {"collected": at, "evidence": {"entries": 30, "failed": failed, "unstable": unstable},
            "handoffs": {"handoffs": handoffs, "pending_items": pending, "with_pending": handoffs},
            "git": {"since": "2026-10-28", "commits": 90, "reverts": reverts}}


class SignalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        (self.vault / "projects" / P / "backlog").mkdir(parents=True)
        (self.vault / "projects" / P / "backlog" / "methodology-backlog.yaml").write_text(
            'items:\n  - id: "MB-demo-001"\n    signal: x\n', encoding="utf-8")
        (self.vault / "ideas").mkdir()
        (self.vault / "ideas" / "2026-11-02-x.md").write_text("---\ntype: idea\n---\n", encoding="utf-8")
        self.old_env = os.environ.get("STRATA_VAULT")
        os.environ["STRATA_VAULT"] = str(self.vault)

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("STRATA_VAULT", None)
        else:
            os.environ["STRATA_VAULT"] = self.old_env
        self.tmp.cleanup()

    def add(self, **kw):
        args = dict(source="indicator", title="다시 확인할 결함 3 → 7", observation="제품 흐름 지표가 나빠졌다",
                    evidence=["qa.recheck-pending = 7 (수집 t2)"], observed=TODAY, today=TODAY)
        args.update(kw)
        return S.write_note(self.vault, P, **args)

    def run_cli(self, *argv) -> tuple[int, str]:
        buf = StringIO()
        with redirect_stdout(buf):
            rc = S.main([*argv, "--project", P, "--today", TODAY.isoformat()])
        return rc, buf.getvalue()

    # --- format and check (acceptance 1·2·5) ---

    def test_written_note_passes_check(self):
        p = self.add()
        self.assertTrue(p.name.startswith("2026-11-02-"))
        fm, body = S.split(p.read_text(encoding="utf-8"))
        self.assertEqual((fm["type"], fm["status"], fm["source"]), ("signal", "open", "indicator"))
        self.assertEqual(set(S.sections(body)), set(S.SECTIONS))
        lines, rc = S.check(S.all_signals(self.vault, P), TODAY)
        self.assertEqual(rc, 0, lines)

    def test_note_without_evidence_is_refused_and_flagged(self):
        with self.assertRaises(ValueError):
            self.add(evidence=[""])
        p = self.add()
        p.write_text(p.read_text(encoding="utf-8").replace("- qa.recheck-pending = 7 (수집 t2)", "비어 있음"), encoding="utf-8")
        lines, rc = S.check(S.all_signals(self.vault, P), TODAY)
        self.assertEqual(rc, 2)
        self.assertTrue(any("근거가 비었다" in l for l in lines))

    def test_bad_frontmatter_values(self):
        p = self.add()
        t = p.read_text(encoding="utf-8").replace("source: indicator", "source: rumour").replace("status: open", "status: maybe")
        p.write_text(t, encoding="utf-8")
        probs = S.load(p, self.vault, P).problems
        self.assertTrue(any(x.startswith("source rumour") for x in probs))
        self.assertTrue(any(x.startswith("status maybe") for x in probs))

    def test_routed_needs_person_and_existing_target(self):
        p = self.add()
        fm, body = S.split(p.read_text(encoding="utf-8"))
        fm.update(status="routed", routed_to="MB-demo-999")
        p.write_text(S.join(fm, body), encoding="utf-8")
        probs = S.load(p, self.vault, P).problems
        self.assertTrue(any("decided_by 없음" in x for x in probs))
        self.assertTrue(any("decided(고른 날짜) 없음" in x for x in probs))
        self.assertTrue(any("MB-demo-999" in x and "찾지 못했다" in x for x in probs))
        fm.update(routed_to="MB-demo-001", decided_by="alice", decided="2026-11-02")
        p.write_text(S.join(fm, body), encoding="utf-8")
        self.assertEqual(S.load(p, self.vault, P).problems, [])

    def test_dropped_needs_reason(self):
        p = self.add()
        fm, body = S.split(p.read_text(encoding="utf-8"))
        fm.update(status="dropped", decided_by="alice", decided="2026-11-02")
        p.write_text(S.join(fm, body), encoding="utf-8")
        self.assertTrue(any("dropped_reason 없음" in x for x in S.load(p, self.vault, P).problems))

    def test_stale_open_signal_is_shown_not_failed(self):
        self.add(observed=date(2026, 10, 18))   # 15 days
        self.add(title="어제 본 것", observed=date(2026, 10, 20))   # 13 days
        lines, rc = S.check(S.all_signals(self.vault, P), TODAY)
        self.assertEqual(rc, 0)
        stale = [l for l in lines if l.strip().startswith("오래 열림:")]
        self.assertEqual(len(stale), 1)
        self.assertIn("15일째", stale[0])
        _, rc7 = S.check(S.all_signals(self.vault, P), TODAY, stale_days=7)
        self.assertEqual(rc7, 0)

    def test_target_kinds(self):
        self.assertTrue(S.target_exists(self.vault, P, "MB-demo-001"))
        self.assertFalse(S.target_exists(self.vault, P, "MB-demo-002"))
        self.assertTrue(S.target_exists(self.vault, P, "ideas/2026-11-02-x.md"))
        self.assertFalse(S.target_exists(self.vault, P, "ideas/none.md"))
        self.assertIsNone(S.target_exists(self.vault, P, "notion:0123456789abcdef0123456789abcdef"))

    # --- route (acceptance 6) ---

    def test_route_records_choice_and_refuses_missing_target(self):
        p = self.add()
        with self.assertRaises(ValueError):
            S.route(p, self.vault, P, by="alice", today=TODAY, to="MB-demo-404")
        with self.assertRaises(ValueError):
            S.route(p, self.vault, P, by="", today=TODAY, to="MB-demo-001")
        S.route(p, self.vault, P, by="alice", today=TODAY, to="MB-demo-001")
        fm, body = S.split(p.read_text(encoding="utf-8"))
        self.assertEqual((fm["status"], fm["routed_to"], fm["decided_by"], fm["decided"]), ("routed", "MB-demo-001", "alice", "2026-11-02"))
        dest = S.sections(body)["행선지"]
        self.assertIn("alice 가 고름 → MB-demo-001", dest)
        self.assertNotIn("비어 있음", dest)
        self.assertEqual(S.load(p, self.vault, P).problems, [])
        S.route(p, self.vault, P, by="alice", today=TODAY, drop="한 번뿐이었다")
        fm, _ = S.split(p.read_text(encoding="utf-8"))
        self.assertEqual((fm["status"], fm["dropped_reason"]), ("dropped", "한 번뿐이었다"))
        self.assertNotIn("routed_to", fm)

    # --- candidates (acceptance 3) ---

    def test_candidates_one_per_kind_against_previous(self):
        data = metrics(history=[snap("t1"), snap("t2", failed=1, unstable=0, handoffs=11, pending=33, reverts=2)],
                       revisions={"r1": {"date": "2026-10-30", "entry_path_bytes": 10000},
                                  "r2": {"date": "2026-10-31", "entry_path_bytes": 11200}},
                       sessions={"a": {"kit_revision": "k1", "start": "2026-10-30T01", "output_tokens_before_first_edit": 1000},
                                 "a2": {"kit_revision": "k1", "start": "2026-10-30T02", "output_tokens_before_first_edit": 1000},
                                 "b": {"kit_revision": "k2", "start": "2026-10-31T01", "output_tokens_before_first_edit": 1500},
                                 "b2": {"kit_revision": "k2+dirty", "start": "2026-10-31T02", "output_tokens_before_first_edit": 1500}})
        kinds = {c.kind: c for c in S.candidates(data, "m.yaml")}
        self.assertEqual(set(kinds), {"evidence-failed", "handoff-pending", "reverts", "entry-path-bytes", "first-edit-tokens"})
        self.assertEqual(kinds["entry-path-bytes"].basis, "r1..r2")
        self.assertEqual(kinds["first-edit-tokens"].basis, "k2")
        for c in kinds.values():
            self.assertTrue(any("비교 기준" in e for e in c.evidence), c.kind)

    def test_threshold_and_no_change(self):
        data = metrics(history=[snap("t1"), snap("t2", handoffs=11, pending=22)],   # 2.0 per handoff both times
                       revisions={"r1": {"entry_path_bytes": 10000}, "r2": {"entry_path_bytes": 10900}})   # +9%
        self.assertEqual(S.candidates(data, "m.yaml"), [])
        self.assertEqual([c.kind for c in S.candidates(data, "m.yaml", threshold=0.05)], ["entry-path-bytes"])

    def test_first_edit_tokens_latest_revision_against_pooled_baseline(self):
        s = lambda rev, start, tok=None: {"kit_revision": rev, "start": start, **({"output_tokens_before_first_edit": tok} if tok else {})}
        # the latest revision has one session with a first edit: not enough
        one = {"a": s("k1", "2026-10-28", 100), "b": s("k2", "2026-10-29", 100), "c": s("k3", "2026-10-30", 300)}
        self.assertEqual(S.candidates({"sessions": one}, "m"), [])
        # one session per earlier revision is pooled into the baseline (k1, k2), the latest revision needs two
        one["d"] = s("k3+dirty", "2026-10-30T1", 300)   # "+dirty" counts as k3
        got = S.candidates({"sessions": one}, "m")
        self.assertEqual([c.key for c in got], ["first-edit-tokens@k3"])
        self.assertIn("k1, k2", got[0].evidence[1])
        # the newest revision has sessions but no first edit yet: nothing to compare
        one["e"] = s("k4", "2026-10-31")
        self.assertEqual(S.candidates({"sessions": one}, "m"), [])
        # the baseline keeps only the newest BASELINE_SESSIONS earlier sessions
        many = {f"o{i}": s(f"r{i}", f"2026-10-{10 + i:02d}", 1000) for i in range(6)}
        many |= {f"n{i}": s(f"r{6 + i}", f"2026-10-{20 + i:02d}", 100) for i in range(S.BASELINE_SESSIONS)}
        many |= {"x": s("last", "2026-10-30", 150), "y": s("last", "2026-10-30T1", 150)}
        self.assertEqual([c.key for c in S.candidates({"sessions": many}, "m")], ["first-edit-tokens@last"])

    def test_route_removes_english_placeholder_without_extra_blank(self):
        d = S.signals_dir(self.vault, P); d.mkdir(parents=True)
        p = d / "2026-11-02-en.md"
        p.write_text("---\ntype: signal\nsource: metrics\nobserved: 2026-10-30\nstatus: open\n---\n\n## Observation\n\nx\n\n"
                     "## Evidence\n\n- quote\n\n## Destination\n\nempty\n", encoding="utf-8")
        S.route(p, self.vault, P, by="alice", today=TODAY, to="MB-demo-001")
        tail = p.read_text(encoding="utf-8").split("## Destination", 1)[1]
        self.assertEqual(tail, "\n\n- 2026-11-02 alice 가 고름 → MB-demo-001\n")
        self.assertEqual(S.load(p, self.vault, P).problems, [])

    def test_without_history_only_absolute_counts(self):
        data = {"collected": "t0", "evidence": {"failed": 0, "unstable": 2}, "handoffs": {"handoffs": 1, "pending_items": 9},
                "git": {"since": "x", "reverts": 3}}
        self.assertEqual([c.kind for c in S.candidates(data, "m.yaml")], ["evidence-unstable"])

    def test_cli_previews_by_default_writes_with_flag_and_dedupes(self):
        mp = S.metrics_path(self.vault, P)
        mp.parent.mkdir(parents=True)
        mp.write_text(yaml.safe_dump(metrics(history=[snap("t1"), snap("t2", failed=2)])), encoding="utf-8")
        rc, out = self.run_cli("candidates")
        self.assertEqual(rc, 0)
        self.assertIn("신호 후보 1", out)
        self.assertFalse(S.signals_dir(self.vault, P).exists())
        rc, out = self.run_cli("candidates", "--write")
        notes = S.all_signals(self.vault, P)
        self.assertEqual(len(notes), 1)
        n = notes[0]
        self.assertEqual((n.status, n.fm["source"], n.fm["candidate"]), ("open", "metrics", "evidence-failed@t2"))
        self.assertNotIn("routed_to", n.fm)
        self.assertEqual(n.problems, [])
        rc, out = self.run_cli("candidates", "--write")   # same candidate again: nothing new
        self.assertIn("신호 후보 0", out)
        self.assertEqual(len(S.all_signals(self.vault, P)), 1)
        # a later collection with another increase is a new basis, but the open note of the same kind holds it back
        mp.write_text(yaml.safe_dump(metrics(history=[snap("t1"), snap("t2", failed=2), snap("t3", failed=3)])), encoding="utf-8")
        rc, out = self.run_cli("candidates", "--write")
        self.assertIn("신호 후보 0", out)

    def test_product_incident_sources_are_not_taken(self):
        with self.assertRaises(ValueError):   # DEC-2026-11-01-17: incidents and feedback belong to the product
            self.add(source="incident")
        with self.assertRaises(SystemExit):
            S.main(["add", "--project", P, "--source", "feedback", "--title", "x", "--evidence", "y"])

    def test_indicator_candidates_worse_way_only(self):
        hist = lambda *rows: {"indicators": {"qa.recheck": {"label": "다시 확인", "better": "lower", "threshold": 0.1},
                                             "tc.coverage": {"label": "커버리지", "better": "higher", "threshold": 0.05}},
                              "history": [{"collected": f"t{i}", "values": v} for i, v in enumerate(rows)]}
        got = S.indicator_candidates(hist({"qa.recheck": 3, "tc.coverage": 80}, {"qa.recheck": 7, "tc.coverage": 70}), "i.yaml")
        self.assertEqual(sorted(c.key for c in got), ["indicator.qa.recheck@t1", "indicator.tc.coverage@t1"])
        self.assertEqual(S.indicator_candidates(hist({"qa.recheck": 7, "tc.coverage": 70}, {"qa.recheck": 3, "tc.coverage": 81}), "i.yaml"), [])
        self.assertEqual(S.indicator_candidates(hist({"qa.recheck": 10}, {"qa.recheck": 10.5}), "i.yaml"), [])   # +5% < 10%
        zero = S.indicator_candidates(hist({"qa.recheck": 0}, {"qa.recheck": 1}), "i.yaml")
        self.assertIn("0 에서 나빠짐", zero[0].evidence[1])
        self.assertEqual(S.indicator_candidates(hist({"qa.recheck": 3}), "i.yaml"), [])

    def test_cli_writes_indicator_notes_with_indicator_source(self):
        from kb.indicators import history_path
        hp = history_path(self.vault, P); hp.parent.mkdir(parents=True)
        hp.write_text(yaml.safe_dump({"indicators": {"qa.recheck": {"label": "다시 확인", "better": "lower", "threshold": 0.1}},
                                      "history": [{"collected": "t1", "values": {"qa.recheck": 2}},
                                                  {"collected": "t2", "values": {"qa.recheck": 5}}]}), encoding="utf-8")
        rc, out = self.run_cli("candidates", "--write")
        self.assertIn("신호 후보 1", out)
        n = S.all_signals(self.vault, P)[0]
        self.assertEqual((n.fm["source"], n.fm["candidate"], n.problems), ("indicator", "indicator.qa.recheck@t2", []))
        rc, out = self.run_cli("check")
        self.assertEqual(rc, 0, out)

if __name__ == "__main__":
    unittest.main()
