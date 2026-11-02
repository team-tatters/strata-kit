"""kb export (MB-strata-kit-2026-044, DEC-2026-11-01-06): only the injection layer is copied — knowledge documents,
refined planning documents and decision notes — under their vault paths, with a manifest; planning sources, audit,
originals, sessions and every share.yaml never path stay out; each project with a code graph gets a module summary."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb import export as X  # noqa: E402
from kb.providers import VaultScanner  # noqa: E402
from kb.store import Edge, Node, ProviderOutput, SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def doc(title, typ="specification", extra=""):
    return f"---\ntitle: {title}\ntype: {typ}\ncreated: 2026-01-01\n{extra}---\n## 본문\n{title}\n"


class Code:
    name = "code"

    def collect(self):
        f = lambda rel, **kw: Node(f"code:p:paths:{rel}", "code", project="p", path=rel, payload={"kind": "file", **kw})
        nodes = [f("svc/billing/a.py", lines=10), f("svc/billing/b.py", lines=5), f("svc/auth/c.py", lines=7),
                 f("tests/test_a.py", lines=3, test=True),
                 Node("code:p:paths:svc/billing/", "code", project="p", path="svc/billing/", payload={"kind": "dir", "files": 2})]
        edges = [Edge("code:p:paths:svc/billing/a.py", "code:p:paths:svc/auth/c.py", "imports"),
                 Edge("code:p:paths:svc/billing/b.py", "code:p:paths:svc/auth/c.py", "imports"),
                 Edge("code:p:paths:svc/billing/a.py", "code:p:paths:svc/billing/b.py", "imports"),
                 Edge("doc:projects/p/knowledge-base/billing.md", "code:p:paths:svc/billing/", "covers")]
        nodes.append(Node("code:secret:paths:x/y/z.py", "code", project="secret", path="x/y/z.py", payload={"kind": "file", "lines": 1}))
        return ProviderOutput(nodes, edges, [])


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = self.vault = Path(self.tmp.name) / "vault"
        w(v / "_meta" / "taxonomy.yaml", "version: '2'\ncategories:\n  guides:\n    order: 1\n")
        w(v / "_meta" / "share.yaml", 'never:\n  - "projects/*/sessions/**"\n  - "projects/{secret,other}/**"\n'
                                      '  - "projects/*/planning/**/source/**"\n  - "projects/*/planning/**/audit/**"\n')
        p = v / "projects" / "p"
        w(p / "knowledge-base" / "billing.md", doc("billing"))
        w(p / "overview.md", doc("overview", "overview"))
        w(p / "decisions" / "DEC-2026-01-01-01.md", doc("dec", "decision"))
        w(p / "decisions" / "_generated-index.md", doc("index", "decision"))
        w(p / "sessions" / "session-2026-01-01-x.md", doc("s", "session"))
        w(p / "planning" / "flat.md", doc("flat", "planning"))
        w(p / "planning" / "refund" / "source" / "orig.md", doc("orig", "planning"))
        w(p / "planning" / "refund" / "audit" / "facts.md", doc("facts", "planning"))
        w(p / "planning" / "refund" / "prd.md", doc("prd", "planning", "planning_doc: prd\n"))
        w(v / "projects" / "secret" / "knowledge-base" / "x.md", doc("secret"))
        os.environ["STRATA_VAULT"] = str(v)
        self.store = SqliteStore()
        self.store.rebuild([VaultScanner(v), Code()], kit_rev="t")

    def tearDown(self):
        self.tmp.cleanup()

    def test_selection_is_the_injection_layer(self):
        got = {(d["role"], d["path"]) for d in X.select(self.store, self.vault)}
        self.assertEqual(got, {("knowledge", "projects/p/knowledge-base/billing.md"), ("knowledge", "projects/p/overview.md"),
                               ("decision", "projects/p/decisions/DEC-2026-01-01-01.md"),
                               ("planning", "projects/p/planning/refund/prd.md")})

    def test_export_writes_copies_manifest_and_code_graph(self):
        out = Path(self.tmp.name) / "out"
        m = X.export(self.store, self.vault, out, ["p"])
        self.assertTrue((out / "projects/p/planning/refund/prd.md").is_file())
        self.assertFalse((out / "projects/p/planning/refund/source").exists())
        self.assertFalse((out / "projects/p/sessions").exists())
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man["decision"], "DEC-2026-11-01-06")
        self.assertEqual(len(man["documents"]), 4)
        self.assertTrue(all(len(d["sha256"]) == 64 for d in man["documents"]))
        g = json.loads((out / "code-graph" / "p.json").read_text(encoding="utf-8"))
        mods = {x["module"]: x for x in g["modules"]}
        self.assertEqual(set(mods), {"svc/billing", "svc/auth", "tests"})
        self.assertEqual(mods["svc/billing"]["files"], 2)
        self.assertEqual(mods["svc/billing"]["depends_on"], [{"module": "svc/auth", "imports": 2}])   # same-module import not counted
        self.assertEqual(mods["svc/billing"]["owning_documents"], ["projects/p/knowledge-base/billing.md"])
        self.assertEqual(mods["tests"]["tests"], 1)
        md = (out / "code-graph" / "p.md").read_text(encoding="utf-8")
        self.assertIn("| svc/billing | 2 | 15 | 0 | svc/auth (2) | projects/p/knowledge-base/billing.md |", md)
        self.assertEqual(m["code_graphs"], ["code-graph/p.md"])
        everything = X.export(self.store, self.vault, Path(self.tmp.name) / "all")
        self.assertEqual(everything["code_graphs"], ["code-graph/p.md"])          # 'secret' is never: no code graph either

    def test_globs(self):
        r = X.glob_to_re("projects/*/planning/**/source/**")
        self.assertTrue(r.match("projects/p/planning/refund/source/a.md"))
        self.assertFalse(r.match("projects/p/planning/refund/prd.md"))
        self.assertEqual(X.expand_braces("projects/{a,b}/x"), ["projects/a/x", "projects/b/x"])


if __name__ == "__main__":
    unittest.main()
