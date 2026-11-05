"""covers.symbols same-name resolution (MB-strata-kit-2026-013 remainder): symbol nodes are keyed by simple name, so
one covers symbol can reach several defining files. The resolver narrows them in a fixed order — the document's own
covers.paths, then the file named after the symbol, then a top-level declaration — and reports ambiguity when more
than one file is left instead of silently picking one."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.code import _owners, symbol_files  # noqa: E402
from kb.gates import hygiene  # noqa: E402
from kb.providers.code_graph import CodeGraph  # noqa: E402
from kb.store import Edge, Node, SqliteStore  # noqa: E402

MODEL = "gw/security/models/UserGroup.kt"
CONSTS = "commons/constants/AppConsts.kt"
MSGS = "commons/constants/MessagePropertiesConsts.kt"


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SymbolFilesTest(unittest.TestCase):
    """A real UserGroup case: a data class in its own file and two nested constant objects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = Path(self.tmp.name) / "demo"
        w(r / MODEL, "package gw.security.models\n\ndata class UserGroup(val id: Long)\n")
        w(r / CONSTS, "package commons.constants\n\nobject AppConsts {\n    object UserGroup {\n        const val ADMIN = \"A\"\n    }\n}\n")
        w(r / MSGS, "package commons.constants\n\nobject MessagePropertiesConsts {\n    object UserGroup { const val X = 1 }\n}\n")
        w(r / "a" / "Item.kt", "package a\n\nclass Item\n")
        w(r / "b" / "Item.kt", "package b\n\nclass Item\n")
        subprocess.run(["git", "init", "-q"], cwd=r, check=True)
        subprocess.run(["git", "add", "-A"], cwd=r, check=True)
        out = CodeGraph([r]).collect()
        self.store = SqliteStore(":memory:")
        self.store.put_nodes(out.nodes)
        self.store.put_edges(out.edges)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _doc(self, name: str, symbols: list[str], paths: list[str] | None = None) -> str:
        did = f"doc:projects/demo/{name}.md"
        self.store.put_nodes([Node(id=did, kind="doc", project="demo", path=f"projects/demo/{name}.md", title=name,
                                   payload={"covers": {"symbols": symbols, **({"paths": paths} if paths else {})}})])
        self.store.put_edges([Edge(did, f"code:demo:symbols:{s}", "covers", "declared", "covers.symbols") for s in symbols])
        return did

    def test_graph_marks_nested_definitions(self):
        defs = {d["file"]: d.get("top") for d in self.store.get("code:demo:symbols:UserGroup").payload["defs"]}
        self.assertEqual(defs, {MODEL: True, CONSTS: False, MSGS: False})

    def test_file_named_after_the_symbol_wins_over_nested_constants(self):
        did = self._doc("token-claim", ["UserGroup"])
        r = symbol_files(self.store, "code:demo:symbols:UserGroup", did)
        self.assertEqual((r["files"], r["ambiguous"]), ([MODEL], False))

    def test_documents_own_covers_paths_narrow_first(self):
        did = self._doc("consts", ["UserGroup"], paths=["commons/constants/AppConsts"])
        r = symbol_files(self.store, "code:demo:symbols:UserGroup", did)
        self.assertEqual((r["files"], r["ambiguous"]), ([CONSTS], False))

    def test_two_equal_definitions_are_reported_ambiguous_not_picked(self):
        did = self._doc("item", ["Item"])
        r = symbol_files(self.store, "code:demo:symbols:Item", did)
        self.assertEqual((r["files"], r["ambiguous"]), (["a/Item.kt", "b/Item.kt"], True))
        self.assertEqual(symbol_files(self.store, "code:demo:symbols:Item", self._doc("item-a", ["Item"], ["a/"]))["files"], ["a/Item.kt"])

    def test_owners_of_a_nested_constant_file_exclude_the_model_document(self):
        self._doc("token-claim", ["UserGroup"])
        self.assertEqual(_owners(self.store, f"code:demo:paths:{CONSTS}"), [])
        self.assertEqual([o["doc"] for o in _owners(self.store, f"code:demo:paths:{MODEL}")], ["projects/demo/token-claim.md"])

    def test_hub_covers_judges_only_the_resolved_file(self):
        self._doc("token-claim", ["UserGroup"])
        users = [f"m{i}/U.kt" for i in range(4)]
        self.store.put_nodes([Node(id=f"code:demo:paths:{u}", kind="code", project="demo", path=u, title=u, payload={"kind": "file"}) for u in users])
        self.store.put_edges([Edge(f"code:demo:paths:{u}", f"code:demo:paths:{CONSTS}", "imports", "extracted", "import") for u in users])
        self.assertEqual([r for r in hygiene.hub_covers(self.store, min_in=3) if r["via"] == "symbols"], [])   # AppConsts.kt is the hub, not the doc's file

    def test_hub_covers_marks_ambiguous_symbols(self):
        self._doc("item", ["Item"])
        users = [f"m{i}/U.kt" for i in range(4)]
        self.store.put_nodes([Node(id=f"code:demo:paths:{u}", kind="code", project="demo", path=u, title=u, payload={"kind": "file"}) for u in users])
        self.store.put_edges([Edge(f"code:demo:paths:{u}", "code:demo:paths:a/Item.kt", "imports", "extracted", "import") for u in users])
        rows = [r for r in hygiene.hub_covers(self.store, min_in=3) if r["via"] == "symbols"]
        self.assertEqual([(r["pattern"], r["defined_in"], r.get("ambiguous")) for r in rows], [("Item", ["a/Item.kt"], ["a/Item.kt", "b/Item.kt"])])
        self.assertIn("정의 모호", hygiene.render({**_empty_report(), "hub_covers": rows}))


def _empty_report() -> dict:
    return {"vault": "v", "project": None, "history_status": {}, "projects": [], "state_docs_without_covers": [], "broken_references": {},
            "summary": {"documents": 0, "history_status_values": 0, "history_status_values_outside_taxonomy": 0, "projects_without_toc": 0,
                        "projects_without_toc_but_declaring_nodes": 0, "state_docs_without_covers": 0, "state_docs_without_covers_no_repo": {},
                        "broken": {}, "hub_covers": 1}}


if __name__ == "__main__":
    unittest.main()
