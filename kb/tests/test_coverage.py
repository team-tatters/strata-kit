import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import coverage as cov  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        p = self.vault / "projects" / "demo"
        w(p / "knowledge-base" / "domain" / "orders" / "refunds.md",
          "---\ntitle: Refunds\nid: kb-demo-refunds\ntype: specification\nproject: demo\ncreated: 2026-04-01\nupdated: 2026-08-20\n"
          "nodes: [orders.refunds, orders]\ncovers:\n  paths: [\"service/order-api/refunds/\", \"service/\"]\n  symbols: [RefundService]\n  tables: [payment_rows]\n---\n## 본문\nx\n")
        w(p / "knowledge-base" / "domain" / "orders" / "facility.md",
          "---\ntitle: Facility\nid: kb-demo-facility\ntype: concept\nproject: demo\ncreated: 2026-04-01\nupdated: 2026-09-30\n"
          "nodes: [orders]\ncovers:\n  paths: [\"service/order-api/facility/\"]\n---\n## 개념\ny\n")
        w(self.vault / "projects" / "other" / "knowledge-base" / "x.md",
          "---\ntitle: X\nid: kb-other-x\ntype: specification\nproject: other\ncreated: 2026-01-01\ncovers:\n  paths: [\"service/\"]\n---\n## 본문\nz\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_orders_longer_patterns_first_and_dedupes(self):
        res = cov.resolve(self.store, ["service/order-api/refunds/Foo.kt", "lib/RefundService.kt", "docs/readme.md"])
        items = res["service/order-api/refunds/Foo.kt"]
        self.assertEqual([(i["pattern"], i["node"], i["doc"].split("/")[1]) for i in items],
                         [("service/order-api/refunds/", "orders.refunds", "demo"), ("service/order-api/refunds/", "orders", "demo"),
                          ("service/", "orders.refunds", "demo"), ("service/", "orders", "demo"), ("service/", "", "other")])
        self.assertEqual(items[0]["updated"], "2026-08-20")
        self.assertEqual(items[0]["type"], "specification")
        self.assertEqual([i["kind"] for i in res["lib/RefundService.kt"]], ["symbols", "symbols"])
        self.assertEqual(res["docs/readme.md"], [])

    def test_nodes_unowned_docs_to_update_owners(self):
        paths = ["service/order-api/refunds/Foo.kt", "service/order-api/facility/Bar.kt", "zzz/Nope.kt"]
        self.assertEqual(cov.nodes_for(self.store, paths), ["orders", "orders.refunds"])
        self.assertEqual(cov.unowned(self.store, paths), ["zzz/Nope.kt"])
        d = cov.docs_to_update(self.store, paths)
        self.assertEqual([(e["node"], e["doc"]) for e in d], [("", "[[x]]"), ("orders", "[[facility]]"), ("orders.refunds", "[[refunds]]")])
        self.assertTrue(d[2]["reason"].startswith("covers 일치 — paths:service/order-api/refunds/ ← service/order-api/refunds/Foo.kt; paths:service/ ←"))
        owners = cov.owners_of_node(self.store, "orders")
        self.assertEqual([(o["type"], o["doc"].split("/")[-1], o["covers"]) for o in owners],
                         [("concept", "facility.md", {"paths": 1}), ("specification", "refunds.md", {"paths": 2, "symbols": 1, "tables": 1})])

    def test_run_gate_warnings_match_legacy_wording(self):
        pdir = Path(self.tmp.name) / "demo"
        pdir.mkdir()
        fm = {"created": "2026-09-01", "nodes": ["orders"], "kb_updates": ["[[facility]]"], "doc_change": "none"}
        res = cov.run_gate(str(pdir), fm, ["service/order-api/refunds/Foo.kt", "service/order-api/facility/Bar.kt", "misc/Loose.kt", "notes.txt"],
                           store=self.store)
        self.assertEqual(res["nodes"], ["orders", "orders.refunds"])
        self.assertEqual([o["doc"].split("/")[-1] for o in res["owners"]], ["refunds.md", "facility.md"])  # other project's doc filtered out
        self.assertEqual(res["unowned"], ["misc/Loose.kt"])
        self.assertIn("nodes 누락: orders.refunds — 세션 frontmatter nodes 에 추가", res["warnings"])
        self.assertIn("doc_change: none 인데 doc_change_reason 없음 — 빈 값 금지", res["warnings"])
        self.assertIn("미소유 표면 1건 (소유 명세 없음): misc/Loose.kt — 명세 생성 또는 covers 확장", res["warnings"])
        self.assertTrue(any(w.startswith("[[facility]] 을 kb_updates 에 적었으나 updated(2026-09-30) 가 세션 이전") is False for w in res["warnings"]))
        report = cov.format_report(res)
        self.assertIn("소유: [[refunds]] orders.refunds — 미갱신 (updated 2026-08-20)", report)
        self.assertIn("소유: [[facility]] orders — 갱신됨 (updated 2026-09-30)", report)
        # no changes → info only
        empty = cov.run_gate(str(pdir), {}, [], since="2026-09-01", store=self.store)
        self.assertEqual(empty["info"], ["변경 파일 없음 — 커버리지 검사 대상 없음"])

    def test_since_must_be_a_date(self):
        # MB-strata-kit-2026-030: a revision passed as --since made git log read the whole history (84 commits for 23 changed)
        pdir = Path(self.tmp.name) / "demo"
        pdir.mkdir()
        with self.assertRaises(ValueError):
            cov.run_gate(str(pdir), {}, None, since="a111cc2", store=self.store)
        with self.assertRaises(SystemExit) as cm:
            cov.main_gate(["--project-dir", str(pdir), "--since", "a111cc2"])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(cov.run_gate(str(pdir), {}, [], since="2026-09-01", store=self.store)["since"], "2026-09-01")

    def test_deleted_files_are_not_new_spec_but_warn_their_owner(self):
        # MB-strata-kit-2026-017: a session that only removed code got '새 명세 필요 34' and a FAIL grade
        import subprocess
        from datetime import date as _d
        pdir = Path(self.tmp.name) / "demo"
        git = lambda *a: subprocess.run(["git", "-C", str(pdir), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                        check=True, capture_output=True)
        for f in ("service/order-api/facility/Bar.kt", "misc/Old.kt", "misc/Gone.kt", "misc/Keep.kt"):
            w(pdir / f, "x\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-q", "-m", "base")
        git("rm", "-q", "misc/Gone.kt"); git("commit", "-q", "-m", "drop gone")        # deletion already committed
        (pdir / "service/order-api/facility/Bar.kt").unlink(); (pdir / "misc/Old.kt").unlink()   # deletions in the tree
        (pdir / "misc/Keep.kt").write_text("y\n")                                            # a live change
        today = _d.today().isoformat()
        self.assertEqual(sorted(cov.deleted_files(str(pdir), today)), ["misc/Gone.kt", "misc/Old.kt", "service/order-api/facility/Bar.kt"])
        res = cov.run_gate(str(pdir), {"doc_change": "none", "doc_change_reason": "t"}, None, since=today, store=self.store)
        self.assertEqual(res["unowned"], ["misc/Keep.kt"])
        self.assertEqual(sorted(res["deleted"]), ["misc/Gone.kt", "misc/Old.kt", "service/order-api/facility/Bar.kt"])
        self.assertTrue(res["summary_line"].startswith("명세 없는 변경 코드 1 · 후보 0"))
        self.assertIn("· 삭제 3", res["summary_line"])
        gone = [x for x in res["warnings"] if "코드 삭제" in x]
        self.assertTrue(any("[[facility]]" in x for x in gone), res["warnings"])
        self.assertTrue(any("[[refunds]]" in x and "파일 1개" in x for x in gone), gone)   # a spec with two nodes counts a file once
        self.assertFalse(any("형상 미갱신" in x for x in res["warnings"]))               # not double-reported as stale
        # --files with paths that are not in git as deletions stay ordinary changes
        res = cov.run_gate(str(Path(self.tmp.name) / "demo"), {}, ["misc/Hypothetical.kt"], since=today, store=self.store)
        self.assertEqual(res["deleted"], [])
        self.assertEqual(res["unowned"], ["misc/Hypothetical.kt"])

    def test_baseline_spares_old_gaps_and_grades_new_ones(self):
        # DEC-2026-10-31-31·32: grade from profile.yaml enforcement.coverage; files on the baseline are counted apart
        import subprocess
        from datetime import date as _d
        pdir = Path(self.tmp.name) / "demo"
        git = lambda *a: subprocess.run(["git", "-C", str(pdir), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                        check=True, capture_output=True)
        w(pdir / ".strata" / "profile.yaml", "profile: embedded\nproject: demo\nenforcement:\n  coverage: default\n")
        w(pdir / "CLAUDE.md", "x\n")
        for f in ("misc/Old.kt", "misc/Exempt.kt", "service/order-api/facility/Owned.kt"):
            w(pdir / f, "x\n")
        w(pdir / ".strata" / "coverage-policy.yaml", "exempt:\n- {path: misc/Exempt, reason: 빌드 파일}\n")
        git("init", "-q"); git("add", "-A"); git("commit", "-q", "-m", "base")
        today = _d.today().isoformat()
        (pdir / "misc/Old.kt").write_text("y\n"); w(pdir / "misc/New.kt", "n\n")
        res = cov.run_gate(str(pdir), {}, None, since=today, store=self.store)
        self.assertEqual(res["grade_rc"], 2)                                   # no baseline: the old gap fails too
        self.assertTrue(any(x.startswith("기준선 없음") for x in res["info"]), res["info"])
        bpath, n = cov.write_baseline(str(pdir), pdir / ".strata", self.store, today="2026-10-31")
        self.assertEqual(n, 1)                                                 # Old.kt only: Owned is owned, Exempt exempt, New untracked
        self.assertIn("misc/Old.kt", bpath.read_text(encoding="utf-8"))
        res = cov.run_gate(str(pdir), {}, None, since=today, store=self.store)
        m = cov.module_of
        self.assertEqual(res["new_spec_needed"], {m("misc/New.kt"): ["misc/New.kt"]})
        self.assertEqual(res["baselined"], {m("misc/Old.kt"): ["misc/Old.kt"]})
        self.assertIn("· 새 명세 필요 1 · 면제 1 · 기준선 1", res["summary_line"])   # the base commit is today too
        self.assertEqual(res["grade_rc"], 2)                                   # the new file still fails
        (pdir / "misc/New.kt").unlink()
        res = cov.run_gate(str(pdir), {}, None, since=today, store=self.store)
        self.assertEqual((res["new_spec_needed"], res["grade_rc"]), ({}, 0))   # only the old gap changed: passes

    def test_ungraded_warnings_not_labelled_default_and_save(self):
        # order 2026.10.31-04: warnings are report-only, yet printed as WARN[default]; handoff ran the gate three times
        import io, json
        from contextlib import redirect_stdout
        pdir = Path(self.tmp.name) / "demo"
        pdir.mkdir()
        res = cov.run_gate(str(pdir), {"created": "2026-09-01"}, ["service/order-api/refunds/Foo.kt", "misc/Loose.kt"], store=self.store)
        text = cov.format_report(res)
        self.assertTrue(res["warnings"])
        self.assertNotIn("WARN[default]", text)
        self.assertIn("WARN[advisory]", text)
        out = Path(self.tmp.name) / "gate.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            cov.main_gate(["--project-dir", str(pdir), "--since", "2026-09-01", "--files", "service/order-api/refunds/Foo.kt",
                           "--save", str(out)])
        self.assertIn("커버리지 게이트", buf.getvalue())          # the report still prints
        saved = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("nodes", saved)
        self.assertTrue(saved["summary_line"].startswith("명세 없는 변경 코드"))

    def test_stale_doc_without_declaration_is_warned(self):
        pdir = Path(self.tmp.name) / "demo"
        pdir.mkdir()
        res = cov.run_gate(str(pdir), {"created": "2026-09-01"}, ["service/order-api/refunds/Foo.kt"], store=self.store)
        self.assertTrue(any(w.startswith("형상 미갱신: [[refunds]] (updated 2026-08-20 < 세션 2026-09-01)") for w in res["warnings"]))

    def test_ensure_fresh_store_rebuilds_when_sources_change(self):
        from kb.engine import ensure_fresh_store
        store_path = Path(self.tmp.name) / "store.sqlite"
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        rev1 = s.revision(); s.close()
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        self.assertEqual(s.revision(), rev1); s.close()          # nothing changed → no rebuild
        import time; time.sleep(1.1)
        w(self.vault / "projects" / "demo" / "knowledge-base" / "new.md", "---\ntitle: N\nid: kb-demo-n\ntype: concept\ncreated: 2026-10-01\n---\n## 개념\nq\n")
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        self.assertNotEqual(s.revision().sources_hash, rev1.sources_hash)
        self.assertIsNotNone(s.get("doc:projects/demo/knowledge-base/new.md")); s.close()
        os.environ["KB_NO_REFRESH"] = "1"
        try:
            w(self.vault / "projects" / "demo" / "knowledge-base" / "new2.md", "---\ntitle: N2\nid: kb-demo-n2\ntype: concept\ncreated: 2026-10-01\n---\n## 개념\nq\n")
            s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
            self.assertIsNone(s.get("doc:projects/demo/knowledge-base/new2.md")); s.close()
        finally:
            del os.environ["KB_NO_REFRESH"]

    def test_ensure_fresh_store_sees_a_source_written_right_after_the_build(self):
        # a gate run, a file fix and the next gate run can fall within one second; the edit must not be missed
        from datetime import datetime
        from kb.engine import ensure_fresh_store
        store_path = Path(self.tmp.name) / "store.sqlite"
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        built = datetime.fromisoformat(s.revision().built_at).timestamp(); s.close()
        p = self.vault / "projects" / "demo" / "knowledge-base" / "quick.md"
        w(p, "---\ntitle: Q\nid: kb-demo-q\ntype: concept\ncreated: 2026-10-01\n---\n## 개념\nq\n")
        os.utime(p, (built + 0.2, built + 0.2))
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        self.assertIsNotNone(s.get("doc:projects/demo/knowledge-base/quick.md")); s.close()

    def test_ensure_fresh_store_ignores_a_source_older_than_the_build_start(self):
        # a source last written just before the build began is in the store — no needless rebuild
        from datetime import datetime
        from kb.engine import ensure_fresh_store
        store_path = Path(self.tmp.name) / "store.sqlite"
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        rev1 = s.revision(); s.close()
        built = datetime.fromisoformat(rev1.built_at).timestamp()
        for p in (self.vault / "projects").rglob("*.md"):
            os.utime(p, (built - 0.001, built - 0.001))
        s = ensure_fresh_store(store_path, self.vault, project_dirs=[])
        self.assertEqual(s.revision(), rev1); s.close()


if __name__ == "__main__":
    unittest.main()


class ImpactCandidatesTest(unittest.TestCase):
    def test_owners_of_importers_are_candidates(self):
        from kb.store import Edge, Node
        store = SqliteStore(":memory:")
        store.put_nodes([
            Node(id="doc:projects/demo/knowledge-base/a.md", kind="doc", project="demo", path="projects/demo/knowledge-base/a.md", title="A spec"),
            Node(id="doc:projects/demo/knowledge-base/b.md", kind="doc", project="demo", path="projects/demo/knowledge-base/b.md", title="B spec"),
            Node(id="code:demo:paths:svc/a/", kind="code", project="demo", path="svc/a/", title="a", payload={"kind": "dir"}),
            Node(id="code:demo:paths:svc/b/", kind="code", project="demo", path="svc/b/", title="b", payload={"kind": "dir"}),
            Node(id="code:demo:paths:svc/a/A.kt", kind="code", project="demo", path="svc/a/A.kt", title="A.kt", payload={"kind": "file"}),
            Node(id="code:demo:paths:svc/b/B.kt", kind="code", project="demo", path="svc/b/B.kt", title="B.kt", payload={"kind": "file"}),
        ])
        store.put_edges([
            Edge("doc:projects/demo/knowledge-base/a.md", "code:demo:paths:svc/a/", "covers", "declared", "covers.paths"),
            Edge("doc:projects/demo/knowledge-base/b.md", "code:demo:paths:svc/b/", "covers", "declared", "covers.paths"),
            Edge("code:demo:paths:svc/b/B.kt", "code:demo:paths:svc/a/A.kt", "imports", "extracted", "import"),
        ])
        r = cov.impact_candidates(store, "demo", ["svc/a/A.kt"], {"projects/demo/knowledge-base/a.md"})
        self.assertEqual(r["files"], 1)
        self.assertEqual([c["stem"] for c in r["candidates"]], ["b"])          # b owns the importer, a is the direct owner
        self.assertEqual(cov.impact_candidates(store, "demo", ["nowhere.kt"], set()), {"files": 0, "candidates": []})
        store.close()


class OwnerCandidatesTest(unittest.TestCase):
    """오더 2026.10.28-11 task-01: 소유 명세 없는 변경 파일 → 이웃 투표 후보 → covers 후보 Inbox(출처 impact)."""

    def setUp(self):
        from kb.store import Edge, Node
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        self.store = SqliteStore(":memory:")
        b = "projects/demo/knowledge-base/b.md"
        self.store.put_nodes([
            Node(id=f"doc:{b}", kind="doc", project="demo", path=b, title="B spec"),
            Node(id="code:demo:paths:svc/app/a/", kind="code", project="demo", path="svc/app/a/", title="a", payload={"kind": "dir"}),
            Node(id="code:demo:paths:svc/app/b/", kind="code", project="demo", path="svc/app/b/", title="b", payload={"kind": "dir"}),
            Node(id="code:demo:paths:svc/app/c/", kind="code", project="demo", path="svc/app/c/", title="c", payload={"kind": "dir"}),
            Node(id="code:demo:paths:svc/app/a/A.kt", kind="code", project="demo", path="svc/app/a/A.kt", title="A.kt", payload={"kind": "file"}),
            Node(id="code:demo:paths:svc/app/b/B.kt", kind="code", project="demo", path="svc/app/b/B.kt", title="B.kt", payload={"kind": "file"}),
            Node(id="code:demo:paths:svc/app/c/C.kt", kind="code", project="demo", path="svc/app/c/C.kt", title="C.kt", payload={"kind": "file"}),
        ])
        self.store.put_edges([
            Edge(f"doc:{b}", "code:demo:paths:svc/app/b/", "covers", "declared", "covers.paths"),
            Edge("code:demo:paths:svc/app/b/B.kt", "code:demo:paths:svc/app/a/A.kt", "imports", "extracted", "import"),
        ])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_unowned_file_with_owned_neighbour_gets_one_candidate(self):
        c = cov.owner_candidates(self.store, "demo", ["svc/app/a/A.kt"])
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0]["doc"], "projects/demo/knowledge-base/b.md")
        self.assertEqual((c[0]["source"], c[0]["status"]), ("impact", "pending"))
        self.assertEqual(c[0]["paths"], ["svc/app/a/"])
        self.assertEqual(c[0]["evidence"], [{"file": "svc/app/a/A.kt", "rank": 1, "votes": 1, "neighbours": 1, "voters": ["svc/app/b/B.kt"]}])

    def test_file_without_neighbours_gets_no_candidate(self):
        self.assertEqual(cov.owner_candidates(self.store, "demo", ["svc/app/c/C.kt"]), [])
        self.assertEqual(cov.owner_candidates(self.store, "demo", ["not/in/graph.kt"]), [])

    def test_inbox_merges_and_keeps_other_entries(self):
        import yaml
        inbox = self.vault / "projects" / "demo" / "_meta" / "covers-candidates.yaml"
        w(inbox, yaml.safe_dump({"project": "demo", "generated": "2026-10-01", "candidates": [
            {"doc": "projects/demo/knowledge-base/x.md", "title": "X", "status": "approved", "symbols": ["X"], "paths": ["svc/x/"]}]}))
        cands = cov.owner_candidates(self.store, "demo", ["svc/app/a/A.kt"])
        self.assertEqual(cov.write_impact_inbox(self.vault, "demo", cands), "projects/demo/_meta/covers-candidates.yaml")
        self.assertEqual(cov.write_impact_inbox(self.vault, "demo", cands), "projects/demo/_meta/covers-candidates.yaml")  # 다시 써도 중복 없음
        data = yaml.safe_load(inbox.read_text(encoding="utf-8"))
        self.assertEqual([(e["doc"].rsplit("/", 1)[1], e["status"], e.get("source", "hygiene")) for e in data["candidates"]],
                         [("x.md", "approved", "hygiene"), ("b.md", "pending", "impact")])
        self.assertEqual(data["candidates"][1]["paths"], ["svc/app/a/"])
        self.assertIsNone(cov.write_impact_inbox(self.vault, "demo", []))                   # 후보 없으면 쓰지 않는다

    def test_run_gate_reports_owner_candidates_for_unowned_sources(self):
        pdir = Path(self.tmp.name) / "demo"
        pdir.mkdir()
        res = cov.run_gate(str(pdir), {}, ["svc/app/a/A.kt", "svc/app/c/C.kt"], since="2026-10-01", store=self.store)
        self.assertEqual(res["unowned"], ["svc/app/a/A.kt", "svc/app/c/C.kt"])
        self.assertEqual([c["doc"] for c in res["owner_candidates"]], ["projects/demo/knowledge-base/b.md"])
        # task-03: 세션 종료 채널 한 줄 — 후보는 후보를 얻은 파일 수, 괄호 안은 후보 명세 수
        self.assertEqual(res["summary_line"], "명세 없는 변경 코드 2 · 후보 1 (후보 명세 1편) · 새 명세 필요 1")
        self.assertIn("  명세 없는 변경 코드 2 · 후보 1 (후보 명세 1편) · 새 명세 필요 1", cov.format_report(res).splitlines())
        # DEC-2026-10-29-03: 후보 없는 파일은 모듈별 묶음으로
        self.assertEqual(res["new_spec_needed"], {"svc/app": ["svc/app/c/C.kt"]})
        self.assertIn("  새 명세 필요 — svc/app 1", cov.format_report(res).splitlines())
        none = cov.run_gate(str(pdir), {}, ["notes.txt"], since="2026-10-01", store=self.store)
        self.assertEqual(none["summary_line"], "명세 없는 변경 코드 0 · 후보 0")


class OwnerCandidateFilterTest(unittest.TestCase):
    """DEC-2026-10-29-03: 같은 모듈(경로 앞 두 마디) 이웃만 투표하고, import 하는 파일이 많은 공용 허브의 표는 세지 않는다."""

    def setUp(self):
        from kb.store import Edge, Node
        self.store = SqliteStore(":memory:")
        docs = {"own": "projects/demo/knowledge-base/own.md", "other": "projects/demo/knowledge-base/other.md",
                "hub": "projects/demo/knowledge-base/hub.md"}
        files = ["service/app/x/X.kt", "service/app/y/Y.kt", "service/lib/z/Z.kt", "service/app/common/Types.kt"]
        files += [f"service/app/u{i}/U{i}.kt" for i in range(4)]
        nodes = [Node(id=f"doc:{d}", kind="doc", project="demo", path=d, title=k) for k, d in docs.items()]
        nodes += [Node(id=f"code:demo:paths:{f}", kind="code", project="demo", path=f, title=f, payload={"kind": "file"}) for f in files]
        nodes += [Node(id=f"code:demo:paths:{d}", kind="code", project="demo", path=d, title=d, payload={"kind": "dir"})
                  for d in ("service/app/y/", "service/lib/z/", "service/app/common/")]
        self.store.put_nodes(nodes)
        e = lambda s_, d_: Edge(f"code:demo:paths:{s_}", f"code:demo:paths:{d_}", "imports", "extracted", "import")
        self.store.put_edges([
            Edge(f"doc:{docs['own']}", "code:demo:paths:service/app/y/", "covers", "declared", "covers.paths"),
            Edge(f"doc:{docs['other']}", "code:demo:paths:service/lib/z/", "covers", "declared", "covers.paths"),
            Edge(f"doc:{docs['hub']}", "code:demo:paths:service/app/common/", "covers", "declared", "covers.paths"),
            e("service/app/x/X.kt", "service/app/y/Y.kt"),           # 같은 모듈 이웃 → 표
            e("service/app/x/X.kt", "service/lib/z/Z.kt"),           # 다른 모듈 이웃 → 무시
            e("service/app/x/X.kt", "service/app/common/Types.kt"),  # 허브 → 무시
            *[e(f"service/app/u{i}/U{i}.kt", "service/app/common/Types.kt") for i in range(4)],
        ])

    def tearDown(self):
        self.store.close()

    def test_owner_votes_default_is_unfiltered(self):
        from kb.code import owner_votes
        v = owner_votes(self.store, "demo", ["code:demo:paths:service/app/x/X.kt"])
        self.assertEqual(sorted(v["ranked"]), ["projects/demo/knowledge-base/hub.md", "projects/demo/knowledge-base/other.md",
                                               "projects/demo/knowledge-base/own.md"])

    def test_owner_votes_same_module_and_hub_filter(self):
        from kb.code import owner_votes
        fid = "code:demo:paths:service/app/x/X.kt"
        self.assertNotIn("projects/demo/knowledge-base/other.md", owner_votes(self.store, "demo", [fid], same_module=True)["ranked"])
        v = owner_votes(self.store, "demo", [fid], same_module=True, hub_min_in=5)   # Types.kt 를 import 하는 파일 5개
        self.assertEqual(v["ranked"], ["projects/demo/knowledge-base/own.md"])
        self.assertEqual(v["skipped"], {"other_module": 1, "hub": 1})
        self.assertIn("projects/demo/knowledge-base/hub.md",
                      owner_votes(self.store, "demo", [fid], same_module=True, hub_min_in=6)["ranked"])  # 기준 미만이면 허브 아님

    def test_owner_candidates_apply_filters_and_rest_is_new_spec(self):
        c = cov.owner_candidates(self.store, "demo", ["service/app/x/X.kt"], hub_min_in=5)
        self.assertEqual([x["doc"] for x in c], ["projects/demo/knowledge-base/own.md"])
        none = cov.owner_candidates(self.store, "demo", ["service/app/u0/U0.kt"], hub_min_in=5)  # 이웃이 허브뿐
        self.assertEqual(none, [])
        self.assertEqual(cov.new_spec_needed(["service/app/x/X.kt", "service/app/u0/U0.kt", "README"], c),
                         {"service/app": ["service/app/u0/U0.kt"], "README": ["README"]})

    def test_module_of(self):
        self.assertEqual(cov.module_of("service/catalog-api/src/main/A.kt"), "service/catalog-api")
        self.assertEqual(cov.module_of("apps/billing/src/x.tsx"), "apps/billing")
        self.assertEqual(cov.module_of("build.gradle.kts"), "build.gradle.kts")


class RecheckCodeTest(unittest.TestCase):
    """오더 2026.10.29-04 (MB-strata-kit-2026-012): 정책·개념·결정 문서가 바뀌면 같은 노드 명세의 covers 와 결정 affects 를
    '다시 확인할 코드'로 보인다 (advisory)."""

    def setUp(self):
        from kb.store import Node
        self.store = SqliteStore(":memory:")
        self.store.put_nodes([
            Node(id="doc:projects/demo/kb/policy.md", kind="doc", project="demo", path="projects/demo/kb/policy.md", title="권한 정책",
                 payload={"type": "concept", "nodes": ["authz"], "discovered": True}),
            Node(id="doc:projects/demo/kb/spec.md", kind="doc", project="demo", path="projects/demo/kb/spec.md", title="권한 명세",
                 payload={"type": "specification", "nodes": ["authz"], "discovered": True,
                          "covers": {"paths": ["service/a/security/"], "symbols": ["AuthChecker"]}}),
            Node(id="doc:projects/demo/kb/other.md", kind="doc", project="demo", path="projects/demo/kb/other.md", title="다른 명세",
                 payload={"type": "specification", "nodes": ["billing"], "discovered": True, "covers": {"paths": ["service/b/"]}}),
            Node(id="decision:demo:DEC-1", kind="decision", project="demo", path="", title="옛 결정", status="superseded",
                 payload={"affects": ["kb/gates/coverage.py(owner_candidates)", "kb/legacy/session_handoff.sh"], "superseded_by": ["DEC-2"]}),
            Node(id="decision:demo:DEC-2", kind="decision", project="demo", path="", title="새 결정", status="active",
                 payload={"affects": ["kb/code.py"], "supersedes": ["DEC-1"]}),
        ])

    def tearDown(self):
        self.store.close()

    def test_policy_doc_change_points_to_same_node_specs_covers(self):
        r = cov.recheck_code(self.store, "demo", docs=["projects/demo/kb/policy.md"])
        self.assertEqual(r, [{"from": "projects/demo/kb/policy.md", "via": "node authz", "owner": "projects/demo/kb/spec.md",
                              "paths": ["service/a/security/", "AuthChecker"]}])

    def test_spec_with_covers_is_left_to_the_forward_gate(self):
        self.assertEqual(cov.recheck_code(self.store, "demo", docs=["projects/demo/kb/spec.md"]), [])

    def test_superseding_decision_points_to_old_affects(self):
        r = cov.recheck_code(self.store, "demo", decisions=["DEC-2"])
        self.assertEqual(r, [{"from": "DEC-2", "via": "supersedes DEC-1", "owner": "DEC-1",
                              "paths": ["kb/gates/coverage.py", "kb/legacy/session_handoff.sh"]}])
        self.assertEqual(cov.recheck_code(self.store, "demo", decisions=["DEC-1"])[0]["via"], "superseded")

    def test_gate_line_is_advisory(self):
        lines = cov.recheck_lines(cov.recheck_code(self.store, "demo", docs=["projects/demo/kb/policy.md"], decisions=["DEC-2"]))
        self.assertEqual(lines[0], "다시 확인할 코드(advisory) — 문서·결정 2 → 경로 4")


class CoveragePolicyTest(unittest.TestCase):
    """오더 2026.10.29-03 (DEC-2026-10-29-08): coverage-policy.yaml 이 grade: default 를 선언하면 '새 명세 필요' 모듈은 default
    등급 결과가 되고(gate-overrides 로 넘어감), exempt 경로는 면제로 따로 센다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tier = Path(self.tmp.name) / "tier"
        self.tier.mkdir()
        self.store = SqliteStore(":memory:")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def policy(self, text):
        (self.tier / "coverage-policy.yaml").write_text(text, encoding="utf-8")
        return cov.load_coverage_policy(self.tier)

    def test_exempt_split_and_default_findings(self):
        pol = self.policy("grade: default\nexempt:\n- {path: components/commons/, reason: 공용 허브}\n- {path: service/order-api/, reason: 2.0 컷오버}\n")
        need = {"components/commons": ["components/commons/T.kt"], "service/order-api": ["service/order-api/A.kt"], "service/billing-api": ["service/billing-api/B.kt"]}
        kept, exempt = cov.apply_exemptions(need, pol)
        self.assertEqual(kept, {"service/billing-api": ["service/billing-api/B.kt"]})
        self.assertEqual(exempt, {"공용 허브": ["components/commons/T.kt"], "2.0 컷오버": ["service/order-api/A.kt"]})
        r = cov.grade_new_spec(kept, pol, self.tier, today="2026-10-29")
        self.assertEqual(r["rc"], 2)
        self.assertEqual([f.key for f in r["unresolved"]], ["new_spec:service/billing-api"])
        (self.tier / "gate-overrides.yaml").write_text("overrides:\n- {check: coverage, key: 'new_spec:service/billing-api', reason: 기획 확정 전, until: 2026-11-30}\n", encoding="utf-8")
        self.assertEqual(cov.grade_new_spec(kept, pol, self.tier, today="2026-10-29")["rc"], 0)

    def test_no_policy_means_report_only(self):
        pol = cov.load_coverage_policy(self.tier)
        self.assertEqual(pol, {"grade": "advisory", "exempt": [], "notes": []})
        self.assertEqual(cov.grade_new_spec({"m": ["m/a.kt"]}, pol, self.tier, today="2026-10-29")["rc"], 0)
        (self.tier / "profile.yaml").write_text("profile: embedded\nenforcement:\n  layers: block\n", encoding="utf-8")
        self.assertEqual(cov.load_coverage_policy(self.tier)["grade"], "advisory")   # undeclared coverage: not block (DEC-2026-10-31-31)

    def test_grade_lives_in_profile_enforcement(self):
        # DEC-2026-10-31-31: profile.yaml enforcement.coverage wins; the old coverage-policy grade is read with a note
        pol = self.policy("grade: default\n")
        self.assertEqual(pol["grade"], "default")
        self.assertIn("profile.yaml enforcement.coverage 로 옮긴다", pol["notes"][0])
        (self.tier / "profile.yaml").write_text("enforcement:\n  coverage: advisory\n", encoding="utf-8")
        pol = cov.load_coverage_policy(self.tier)
        self.assertEqual(pol["grade"], "advisory")
        self.assertIn("읽지 않는다", pol["notes"][0])
        (self.tier / "profile.yaml").write_text("enforcement:\n  coverage: block\n", encoding="utf-8")
        r = cov.grade_new_spec({"m": ["m/a.kt"]}, cov.load_coverage_policy(self.tier), self.tier, today="2026-10-29")
        self.assertEqual((r["rc"], [f.key for f in r["blocked"]]), (2, ["new_spec:m"]))
        (self.tier / "profile.yaml").write_text("enforcement:\n  coverage: strict\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            cov.load_coverage_policy(self.tier)

    def test_summary_line_counts_exempt(self):
        self.assertEqual(cov.summary_line(3, [], exempt_count=2), "명세 없는 변경 코드 3 · 후보 0 · 새 명세 필요 1 · 면제 2")


class DesiredShapeTest(unittest.TestCase):
    """DEC-2026-10-29-09 (오더 2026.10.29-03 task-02): a planning document reaches code only through implementation.spec →
    an as-built specification with covers. When changed code is owned by that specification, the gate lists the planning
    document by its implementation.status — advisory, it never changes the exit code."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.vault = root / "vault"
        p = self.vault / "projects" / "demo"
        w(p / "knowledge-base" / "refunds.md",
          "---\ntitle: Refunds\nid: kb-demo-refunds\ntype: specification\nproject: demo\ncreated: 2026-04-01\nupdated: 2026-10-29\n"
          "covers:\n  paths: [\"service/order-api/refunds/\"]\n---\n## 본문\nx\n")
        plan = lambda name, impl: w(p / "planning" / f"{name}.md",
                                    f"---\ntitle: {name}\ntype: planning\nproject: demo\ncreated: 2026-09-01\nimplementation:{impl}\n---\n## 기획\ny\n")
        plan("done", "\n  status: implemented\n  spec: \"[[refunds]]\"")
        plan("next", "\n  status: partial\n  spec: \"[[refunds]]\"")
        plan("old", "\n  status: superseded\n  spec: \"[[refunds]]\"")
        plan("loose", "\n  status: planned")
        plan("plain", " not-started")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")
        self.project_dir = root / "demo"
        self.project_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_scanner_indexes_implementation_spec_and_status(self):
        edges = {(e.src, e.dst, e.kind, e.source_ref) for e in self.store.neighbors("doc:projects/demo/knowledge-base/refunds.md", kind="implementation", direction="in")}
        self.assertEqual(edges, {(f"doc:projects/demo/planning/{n}.md", "doc:projects/demo/knowledge-base/refunds.md", "implementation", "implementation.spec")
                                 for n in ("done", "next", "old")})
        self.assertEqual(self.store.get("doc:projects/demo/planning/next.md").payload["implementation_status"], "partial")
        self.assertEqual(self.store.get("doc:projects/demo/planning/plain.md").payload["implementation_status"], "not-started")

    def test_gate_lists_planning_documents_of_changed_code_by_status(self):
        r = cov.run_gate(str(self.project_dir), files=["service/order-api/refunds/Foo.kt", "zzz/Nope.kt"], store=self.store, knowledge=([], []))
        self.assertEqual([(d["planning"], d["spec"], d["status"], d["action"]) for d in r["desired_shape"]],
                         [("projects/demo/planning/done.md", "projects/demo/knowledge-base/refunds.md", "implemented", "recheck"),
                          ("projects/demo/planning/next.md", "projects/demo/knowledge-base/refunds.md", "partial", "update-status")])
        self.assertTrue(any(i.startswith("바라는 형상 대조 — 기획 문서 2 (재대조는 coverage 등급") for i in r["info"]))
        self.assertEqual(r["desired_shape"][0]["paths"], ["service/order-api/refunds/Foo.kt"])

    def graded(self, grade, overrides=""):
        s = self.project_dir / ".strata"; s.mkdir(exist_ok=True)
        (s / "profile.yaml").write_text(f"profile: embedded\nproject: demo\nenforcement:\n  coverage: {grade}\n", encoding="utf-8")
        if overrides:
            (s / "gate-overrides.yaml").write_text(overrides, encoding="utf-8")

    def test_unjudged_implemented_plan_takes_the_coverage_grade(self):
        # DEC-2026-11-02-05: the recheck row of an implemented plan is a finding at the project's coverage grade;
        # the update-status row (partial) stays advisory
        self.graded("default")
        r = cov.run_gate(str(self.project_dir), files=["service/order-api/refunds/Foo.kt"], since="2026-11-02", store=self.store, knowledge=([], []))
        self.assertEqual(r["grade_rc"], 2)
        fails = [g for g in r["grades"] if g.startswith("FAIL")]
        self.assertEqual(len(fails), 1, r["grades"])
        self.assertIn("desired:done", fails[0])
        self.assertIn("kb divergence", fails[0])

    def test_advisory_grade_only_reports(self):
        r = cov.run_gate(str(self.project_dir), files=["service/order-api/refunds/Foo.kt"], since="2026-11-02", store=self.store, knowledge=([], []))
        self.assertEqual(r["grade_rc"], 0)

    def test_a_judged_plan_or_an_override_releases_it(self):
        self.graded("default", "overrides:\n  - {check: coverage, key: \"desired:done\", reason: \"재대조 예약\", until: \"2099-01-01\"}\n")
        r = cov.run_gate(str(self.project_dir), files=["service/order-api/refunds/Foo.kt"], since="2026-11-02", store=self.store, knowledge=([], []))
        self.assertEqual(r["grade_rc"], 0, r["grades"])
        self.assertTrue(any(g.startswith("pass") and "desired:done" in g for g in r["grades"]))
        # judged within the window: implementation.reviewed on or after since leaves the row out (DEC-2026-10-31-35)
        (self.project_dir / ".strata" / "gate-overrides.yaml").unlink()
        pl = self.vault / "projects/demo/planning/done.md"
        pl.write_text(pl.read_text().replace("  status: implemented\n", "  status: implemented\n  reviewed: 2026-11-02\n"), encoding="utf-8")
        self.store.rebuild([VaultScanner(self.vault)], kit_rev="t")
        r = cov.run_gate(str(self.project_dir), files=["service/order-api/refunds/Foo.kt"], since="2026-11-02", store=self.store, knowledge=([], []))
        self.assertEqual(r["grade_rc"], 0, r["grades"])

    def test_no_planning_link_no_rows(self):
        r = cov.run_gate(str(self.project_dir), files=["zzz/Nope.kt"], store=self.store, knowledge=([], []))
        self.assertEqual(r["desired_shape"], [])
        self.assertFalse(any("바라는 형상" in i for i in r["info"]))
