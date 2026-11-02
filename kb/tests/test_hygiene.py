"""hygiene report: status vocabulary vs taxonomy · toc gaps · covers gaps · broken reference groups."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.gates import hygiene  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class HygieneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        w(self.vault / "_meta" / "taxonomy.yaml",
          "version: '1.0'\ncategories:\n  domain: {order: 1}\ndocument_types:\n  specification: {}\n  session: {lifecycle_override: {statuses: [open, closed]}}\n  planning: {lifecycle_override: {statuses: [requested, realized]}}\n"
          "lifecycle:\n  statuses: {draft: {}, active: {}, archived: {}}\n")
        d = self.vault / "projects" / "demo"
        w(d / "_meta" / "toc.yaml", "version: '1.0'\nproject: demo\nnodes:\n  orders: {label: 주문}\n")
        w(d / "knowledge-base" / "domain" / "spec.md", "---\ntitle: spec\nid: kb-demo-spec\ntype: specification\ncreated: 2026-01-01\nnodes: [orders, nope]\n---\n## 본문\n[[missing-doc]] [text](gone.md) [[spec]]\n")
        w(d / "knowledge-base" / "domain" / "covered.md", "---\ntitle: c\nid: kb-demo-c\ntype: specification\ncreated: 2026-01-01\ncovers:\n  paths: [src/]\n---\n## x\n")
        w(d / "sessions" / "session-2026-01-02-a.md", "---\ntitle: a\nid: s-a\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-01-02\nstatus: closed\n"
                                                      "kb_updates: [\"[[spec]]\", \"[[nowhere]]\"]\norders: [2026.01.01-01]\ndecisions_made: [DEC-2026-01-01-01]\n---\n## 완료\n")
        w(d / "tasks" / "2026.01.02" / "01-x" / "design.md", "---\ntitle: design\nid: t-design\ntype: planning\nproject: demo\ncreated: 2026-01-02\nstatus: realized\n---\n## 요약\n")
        w(d / "planning" / "intake" / "story.md", "---\ntitle: story\ntype: planning\nproject: demo\ncreated: 2026-01-02\nstatus: requested\nsource: \"notion:abc\"\n---\n[[외부 정책 페이지]] [첨부](a.xlsx)\n")
        w(d / "sessions" / "session-2026-01-03-b.md", "---\ntitle: b\nid: s-b\ntype: session\nproject: demo\nmachine: m\ncreated: 2026-01-03\nstatus: awaiting_review\n---\n## 완료\n")
        n = self.vault / "projects" / "notoc"
        w(n / "knowledge-base" / "domain" / "g.md", "---\ntitle: g\nid: kb-notoc-g\ntype: specification\ncreated: 2026-01-01\nnodes: [thing]\n---\n## x\n")
        os.environ["STRATA_VAULT"] = str(self.vault)
        self.store = SqliteStore(":memory:")
        self.store.rebuild([VaultScanner(self.vault)])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_report_groups(self):
        r = hygiene.report(self.store, self.vault)
        sess = r["history_status"]["session"]
        self.assertEqual(sess["allowed_by_taxonomy"], ["closed", "open"])
        self.assertEqual({v["status"]: v["allowed"] for v in sess["values"]}, {"closed": True, "awaiting_review": False})
        self.assertEqual({v["status"]: v["proposed"] for v in sess["values"]}, {"closed": "closed", "awaiting_review": "awaiting"})
        self.assertEqual(r["summary"]["history_status_values_outside_taxonomy"], 1)
        plan = r["history_status"]["planning"]                                   # a planning doc in a task folder keeps its own vocabulary
        self.assertEqual({v["status"]: v["allowed"] for v in plan["values"]}, {"realized": True})
        self.assertNotIn("realized", {v["status"] for v in r["history_status"]["task"]["values"]})
        self.assertEqual(r["summary"]["origin_references"], 2)                        # the Notion export's links are references, not broken
        self.assertFalse(any("외부 정책" in t["to"] for t in r["broken_references"].get("wiki", {}).get("top_targets", [])))
        rows = {p["project"]: p for p in r["projects"]}
        self.assertTrue(rows["demo"]["toc"]); self.assertFalse(rows["notoc"]["toc"])
        self.assertEqual(rows["notoc"]["top_node_ids"], ["thing"])
        self.assertEqual([x["path"] for x in r["state_docs_without_covers"]], [])   # no project here has a code repo
        self.assertEqual(r["summary"]["state_docs_without_covers_no_repo"], {"demo": 1, "notoc": 1})
        b = r["summary"]["broken"]
        self.assertEqual(b["wiki"], 1)          # [[missing-doc]]
        self.assertEqual(b["md-link"], 1)       # gone.md
        self.assertEqual(b["frontmatter"], 1)   # [[nowhere]] in kb_updates
        self.assertEqual(b["node"], 2)          # nope (demo) + thing (notoc)
        self.assertEqual(b["order"], 1)
        self.assertEqual(b["decision"], 1)
        self.assertEqual(b["code"], 1)          # covered.md's code target waits for the code-graph provider — reported apart
        text = hygiene.render(r)
        self.assertIn("awaiting_review  → 제안 awaiting  ← taxonomy 밖", text)
        self.assertIn("- notoc: 문서 1, nodes 선언 문서 1, 노드 id 1종 ['thing']", text)

    def test_rewrite_status_dry_run_and_apply(self):
        r = hygiene.rewrite_status(self.store, self.vault)
        self.assertEqual([(x["old"], x["new"]) for x in r["rewritten"]], [("awaiting_review", "awaiting")])
        self.assertFalse((self.vault / "projects/demo/sessions/session-2026-01-03-b.md").read_text(encoding="utf-8").count("status: awaiting\n"))
        r = hygiene.rewrite_status(self.store, self.vault, apply=True)
        text = (self.vault / "projects/demo/sessions/session-2026-01-03-b.md").read_text(encoding="utf-8")
        self.assertIn("status: awaiting\n", text)
        self.assertEqual(hygiene.proposed_status('"handoff (context clear 직전)"'), "handed_off")
        self.assertEqual(hygiene.proposed_status("in-progress"), "in_progress")
        self.assertIsNone(hygiene.proposed_status("weird"))

    def test_covers_candidates_from_code_graph(self):
        from kb.store import Node
        self.store.put_nodes([Node(id="code:demo:symbols:RefundService", kind="code", project="demo", path="svc/RefundService.kt", title="RefundService",
                                   payload={"kind": "symbol", "files": ["svc/refunds/RefundService.kt"]})])
        w(self.vault / "projects/demo/knowledge-base/domain/spec.md",
          "---\ntitle: spec\nid: kb-demo-spec\ntype: specification\ncreated: 2026-01-01\nnodes: [orders]\n---\n## 본문\n`RefundService` 가 계산한다. UnknownThing 도.\n")
        self.store.rebuild([VaultScanner(self.vault)])
        self.store.put_nodes([Node(id="code:demo:symbols:RefundService", kind="code", project="demo", path="svc/RefundService.kt", title="RefundService",
                                   payload={"kind": "symbol", "files": ["svc/refunds/RefundService.kt"]})])
        c = hygiene.covers_candidates(self.store, self.vault, {"demo"})
        self.assertEqual([x["doc"] for x in c["demo"]], ["projects/demo/knowledge-base/domain/spec.md"])
        self.assertEqual(c["demo"][0]["symbols"], ["RefundService"]); self.assertEqual(c["demo"][0]["paths"], ["svc/refunds/"])
        self.assertNotIn("notoc", c)   # no repo for notoc
        files = hygiene.write_covers_inbox(self.vault, c)
        self.assertEqual(files, ["projects/demo/_meta/covers-candidates.yaml"])
        self.assertEqual(hygiene.apply_covers(self.vault), [])          # nothing approved yet
        inbox = self.vault / files[0]
        inbox.write_text(inbox.read_text(encoding="utf-8").replace("status: pending", "status: approved"), encoding="utf-8")
        applied = hygiene.apply_covers(self.vault)
        self.assertEqual([a["doc"] for a in applied], ["projects/demo/knowledge-base/domain/spec.md"])
        text = (self.vault / "projects/demo/knowledge-base/domain/spec.md").read_text(encoding="utf-8")
        self.assertIn("covers:\n  paths: [svc/refunds/]\n  symbols: [RefundService]\n---", text)
        self.assertIn("status: applied", inbox.read_text(encoding="utf-8"))
        self.assertEqual(hygiene.apply_covers(self.vault), [])          # idempotent

    def test_impact_candidates_merge_into_existing_covers_without_duplicates(self):
        """오더 2026.10.28-11 task-02: source: impact 후보는 covers 가 이미 있는 명세에도 빠진 패턴만 더한다."""
        import yaml
        covered = self.vault / "projects/demo/knowledge-base/domain/covered.md"
        inbox = self.vault / "projects/demo/_meta/covers-candidates.yaml"
        w(inbox, yaml.safe_dump({"project": "demo", "candidates": [
            {"doc": "projects/demo/knowledge-base/domain/covered.md", "status": "approved", "source": "impact", "paths": ["src/", "svc/a/"]},
            {"doc": "projects/demo/knowledge-base/domain/spec.md", "status": "approved", "source": "impact", "paths": ["svc/b/"]},
            {"doc": "projects/demo/knowledge-base/domain/covered.md", "status": "approved", "source": "impact", "paths": ["src/"]},
        ]}, allow_unicode=True, sort_keys=False))
        applied = hygiene.apply_covers(self.vault)
        self.assertEqual([(a["doc"].rsplit("/", 1)[1], a["paths"]) for a in applied], [("covered.md", 1), ("spec.md", 1)])
        text = covered.read_text(encoding="utf-8")
        self.assertIn("covers:\n  paths: [src/, svc/a/]\n---", text)
        self.assertIn("title: c\nid: kb-demo-c\ntype: specification\ncreated: 2026-01-01\n", text)   # 다른 키는 그대로
        self.assertIn("covers:\n  paths: [svc/b/]\n---", (self.vault / "projects/demo/knowledge-base/domain/spec.md").read_text(encoding="utf-8"))
        statuses = [c["status"] for c in yaml.safe_load(inbox.read_text(encoding="utf-8"))["candidates"]]
        self.assertEqual(statuses, ["applied", "applied", "applied"])        # 이미 있는 패턴뿐인 후보도 처리 끝
        before = covered.read_text(encoding="utf-8")
        inbox.write_text(inbox.read_text(encoding="utf-8").replace("status: applied", "status: approved"), encoding="utf-8")
        self.assertEqual(hygiene.apply_covers(self.vault), [])               # 다시 적용해도 문서 변경 0
        self.assertEqual(covered.read_text(encoding="utf-8"), before)

    def test_hygiene_inbox_rewrite_keeps_impact_entries(self):
        import yaml
        inbox = self.vault / "projects/demo/_meta/covers-candidates.yaml"
        w(inbox, yaml.safe_dump({"project": "demo", "candidates": [
            {"doc": "projects/demo/knowledge-base/domain/covered.md", "status": "pending", "source": "impact", "paths": ["svc/a/"]}]}))
        hygiene.write_covers_inbox(self.vault, {"demo": [{"doc": "projects/demo/knowledge-base/domain/spec.md", "status": "pending", "symbols": ["X"], "paths": ["svc/x/"]}]})
        rows = yaml.safe_load(inbox.read_text(encoding="utf-8"))["candidates"]
        self.assertEqual([(r["doc"].rsplit("/", 1)[1], r.get("source", "hygiene")) for r in rows], [("spec.md", "hygiene"), ("covered.md", "impact")])

    def test_project_filter(self):
        r = hygiene.report(self.store, self.vault, project="notoc")
        self.assertEqual(r["summary"]["documents"], 1)
        self.assertEqual(r["summary"]["broken"], {"node": 1})


if __name__ == "__main__":
    unittest.main()


class HubCoversTest(unittest.TestCase):
    """MB-strata-kit-2026-013: a document whose covers name a shared hub (imported from many other modules) owns nothing
    in particular — every importer looks like its code. Hygiene lists such covers."""

    def setUp(self):
        from kb.store import Edge, Node
        self.store = SqliteStore(":memory:")
        types_dir, guard = "components/commons/types/", "service/app/security/Guard.kt"
        nodes = [Node(id="doc:projects/demo/gap.md", kind="doc", project="demo", path="projects/demo/gap.md", title="gap"),
                 Node(id="doc:projects/demo/app.md", kind="doc", project="demo", path="projects/demo/app.md", title="app"),
                 Node(id=f"code:demo:paths:{types_dir}", kind="code", project="demo", path=types_dir, title="types", payload={"kind": "dir"}),
                 Node(id=f"code:demo:paths:{types_dir}T.kt", kind="code", project="demo", path=f"{types_dir}T.kt", title="T", payload={"kind": "file"}),
                 Node(id="code:demo:paths:service/app/security/", kind="code", project="demo", path="service/app/security/", title="s", payload={"kind": "dir"}),
                 Node(id=f"code:demo:paths:{guard}", kind="code", project="demo", path=guard, title="G", payload={"kind": "file"})]
        users = [f"service/m{i}/U.kt" for i in range(3)] + [f"service/app/x{i}/U.kt" for i in range(3)]
        nodes += [Node(id=f"code:demo:paths:{u}", kind="code", project="demo", path=u, title=u, payload={"kind": "file"}) for u in users]
        self.store.put_nodes(nodes)
        imp = lambda s, d: Edge(f"code:demo:paths:{s}", f"code:demo:paths:{d}", "imports", "extracted", "import")
        self.store.put_edges([
            Edge("doc:projects/demo/gap.md", f"code:demo:paths:{types_dir}", "covers", "declared", "covers.paths"),
            Edge("doc:projects/demo/app.md", "code:demo:paths:service/app/security/", "covers", "declared", "covers.paths"),
            *[imp(u, f"{types_dir}T.kt") for u in users],          # 6 importers, 6 from other modules
            *[imp(u, guard) for u in users[3:]],                    # 3 importers, all in the same module
        ])

    def tearDown(self):
        self.store.close()

    def test_cross_module_importers_make_a_hub(self):
        rows = hygiene.hub_covers(self.store, min_in=5)
        self.assertEqual([(r["doc"], r["pattern"], r["importers_other_modules"]) for r in rows],
                         [("projects/demo/gap.md", "components/commons/types/", 6)])
        self.assertEqual(hygiene.hub_covers(self.store, min_in=5)[0]["shared_by"], 1)
        self.assertEqual(hygiene.hub_covers(self.store, min_in=7), [])

    def test_symbol_defined_in_a_hub_file_is_a_hub(self):
        """MB-strata-kit-2026-013 extension: a covers symbol defined in a hub file (GlobalTypes in the shared types
        package) is as much a hub as the file's path; a symbol whose importers sit in its own module is not."""
        from kb.store import Edge, Node
        types_file, guard = "code:demo:paths:components/commons/types/T.kt", "code:demo:paths:service/app/security/Guard.kt"
        self.store.put_nodes([Node(id="code:demo:symbols:AppType", kind="code", project="demo", path="components/commons/types/T.kt", title="AppType", payload={"kind": "symbol"}),
                              Node(id="code:demo:symbols:Guard", kind="code", project="demo", path="service/app/security/Guard.kt", title="Guard", payload={"kind": "symbol"}),
                              Node(id="doc:projects/demo/rbac.md", kind="doc", project="demo", path="projects/demo/rbac.md", title="rbac")])
        self.store.put_edges([Edge("code:demo:symbols:AppType", types_file, "member_of", "extracted", "def"),
                              Edge("code:demo:symbols:Guard", guard, "member_of", "extracted", "def"),
                              Edge("doc:projects/demo/rbac.md", "code:demo:symbols:AppType", "covers", "declared", "covers.symbols"),
                              Edge("doc:projects/demo/app.md", "code:demo:symbols:Guard", "covers", "declared", "covers.symbols")])
        rows = hygiene.hub_covers(self.store, min_in=5)
        self.assertEqual([(r["doc"], r["via"], r["pattern"], r["importers_other_modules"]) for r in rows],
                         [("projects/demo/gap.md", "paths", "components/commons/types/", 6),
                          ("projects/demo/rbac.md", "symbols", "AppType", 6)])
        self.assertEqual(rows[1]["defined_in"], ["components/commons/types/T.kt"])

    def test_same_name_symbol_files_are_not_pooled(self):
        """Symbol nodes are keyed by simple name: two unrelated files defining `Item` must not add up into one hub."""
        from kb.store import Edge, Node
        a, b = "service/m0/Item.kt", "service/m1/Item.kt"
        self.store.put_nodes([Node(id=f"code:demo:paths:{f}", kind="code", project="demo", path=f, title="Item", payload={"kind": "file"}) for f in (a, b)]
                             + [Node(id="code:demo:symbols:Item", kind="code", project="demo", path=a, title="Item", payload={"kind": "symbol"})])
        imp = lambda s, d: Edge(f"code:demo:paths:{s}", f"code:demo:paths:{d}", "imports", "extracted", "import")
        self.store.put_edges([Edge("code:demo:symbols:Item", f"code:demo:paths:{f}", "member_of", "extracted", "def") for f in (a, b)]
                             + [imp(f"service/app/x{i}/U.kt", a) for i in range(3)]      # 3 distinct importers of a
                             + [imp(f"service/m2/U{i}.kt", b) for i in range(3)]         # 3 other distinct importers of b
                             + [Edge("doc:projects/demo/app.md", "code:demo:symbols:Item", "covers", "declared", "covers.symbols")])
        self.assertEqual([r for r in hygiene.hub_covers(self.store, min_in=5) if r["via"] == "symbols"], [])   # pooled would be 6
        rows = [r for r in hygiene.hub_covers(self.store, min_in=3) if r["via"] == "symbols"]
        self.assertEqual([(r["pattern"], r["defined_in"], r["importers_other_modules"]) for r in rows], [("Item", [a, b], 3)])
