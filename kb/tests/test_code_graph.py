"""Code graph provider: dirs · files · symbols, imports in Kotlin/TS/Python, tests edges, covers targets resolved."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kb.providers.code_graph import CodeGraph, is_test_path  # noqa: E402
from kb.store import Edge, Node, SqliteStore  # noqa: E402


def w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CodeGraphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "demo"
        r = self.repo
        w(r / "svc" / "src" / "main" / "kotlin" / "io" / "x" / "refunds" / "RefundService.kt",
          "package io.x.refunds\n\nimport io.x.auth.AuthChecker\nimport io.x.model.*\nimport org.springframework.stereotype.Service\n\n@Service\nclass RefundService(val a: AuthChecker)\n\ninternal data class Row(val v: Int)\n")
        w(r / "svc" / "src" / "main" / "kotlin" / "io" / "x" / "auth" / "AuthChecker.kt", "package io.x.auth\n\ninterface AuthChecker\nobject AuthCheckers\n")
        w(r / "svc" / "src" / "main" / "kotlin" / "io" / "x" / "auth" / "AuthFilter.kt", "package io.x.auth\n\nclass AuthFilter(val c: AuthChecker)\n")
        w(r / "svc" / "src" / "main" / "kotlin" / "io" / "x" / "model" / "Types.kt", "package io.x.model\n\nenum class Kind { A }\n")
        # a second module defines the same FQN: imports resolve to the module they come from
        w(r / "svc2" / "src" / "main" / "kotlin" / "io" / "x" / "auth" / "AuthChecker.kt", "package io.x.auth\n\nclass AuthChecker\n")
        w(r / "svc2" / "src" / "main" / "kotlin" / "io" / "x" / "web" / "Ctl.kt", "package io.x.web\n\nimport io.x.auth.AuthChecker\n\nclass Ctl(val a: AuthChecker)\n")
        w(r / "svc" / "src" / "test" / "kotlin" / "io" / "x" / "refunds" / "RefundServiceTest.kt",
          "package io.x.refunds\n\nimport io.x.refunds.RefundService\n\nclass RefundServiceTest\n")
        w(r / "web" / "package.json", '{"name": "web"}\n')
        w(r / "web" / "src" / "app" / "page.tsx", "import { Button } from '@shared/ui'\nimport { fmt } from '@shared/ui/fmt'\nimport { x } from './x'\nimport y from 'src/lib/y'\nimport React from 'react'\nexport default function Page() {}\n")
        w(r / "web" / "src" / "app" / "x.ts", "export const x = 1\n")
        w(r / "web" / "src" / "lib" / "y.ts", "export class Y {}\nconst localHelper = () => 1\n  const notTopLevel = 2\n")
        w(r / "web" / "src" / "__tests__" / "page.test.tsx", "import Page from '../app/page'\n")
        w(r / "packages" / "ui" / "package.json", '{"name": "@shared/ui"}\n')
        w(r / "packages" / "ui" / "src" / "index.ts", "export interface Button {}\n")
        w(r / "packages" / "ui" / "src" / "fmt.ts", "export function fmt() {}\n")
        w(r / "tools" / "a.py", "import tools.b\nfrom tools.c import helper\n\nclass A:\n    pass\n\ndef run():\n    pass\n")
        w(r / "tools" / "b.py", "X = 1\n")
        w(r / "tools" / "c.py", "def helper():\n    pass\n")
        w(r / "tools" / "test_a.py", "from tools.a import A\n")
        w(r / "node_modules" / "left-pad" / "index.js", "module.exports = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=r, check=True)
        subprocess.run(["git", "add", "-A"], cwd=r, check=True)
        self.out = CodeGraph([r]).collect()
        self.nodes = {n.id: n for n in self.out.nodes}
        self.edges = {(e.src, e.dst, e.kind, e.confidence) for e in self.out.edges}

    def tearDown(self):
        self.tmp.cleanup()

    def test_nodes_dirs_files_symbols(self):
        self.assertIn("code:demo:paths:svc/src/main/kotlin/io/x/refunds/", self.nodes)
        self.assertIn("code:demo:paths:svc/src/main/kotlin/io/x/refunds/RefundService.kt", self.nodes)
        self.assertEqual(self.nodes["code:demo:paths:svc/src/main/kotlin/io/x/refunds/"].payload, {"kind": "dir", "files": 1})
        sym = self.nodes["code:demo:symbols:AuthChecker"]
        self.assertEqual(sym.payload["files"][0], "svc/src/main/kotlin/io/x/auth/AuthChecker.kt")
        self.assertEqual(sym.payload["defs"][0]["type"], "interface")
        self.assertIn("code:demo:symbols:Kind", self.nodes)          # enum class
        self.assertIn("code:demo:symbols:Row", self.nodes)           # internal data class
        self.assertIn("code:demo:symbols:Page", self.nodes)          # export default function
        self.assertIn("code:demo:symbols:Y", self.nodes)
        self.assertIn("code:demo:symbols:localHelper", self.nodes)      # module-scope const without export (playwright config style)
        self.assertNotIn("code:demo:symbols:notTopLevel", self.nodes)
        self.assertIn("code:demo:symbols:A", self.nodes)
        self.assertIn("code:demo:symbols:run", self.nodes)
        self.assertNotIn("code:demo:paths:node_modules/left-pad/index.js", self.nodes)
        self.assertTrue(self.nodes["code:demo:paths:tools/test_a.py"].payload["test"])
        self.assertFalse(self.nodes["code:demo:paths:tools/a.py"].payload["test"])

    def test_edges(self):
        svc = "code:demo:paths:svc/src/main/kotlin/io/x/refunds/RefundService.kt"
        self.assertIn((svc, "code:demo:paths:svc/src/main/kotlin/io/x/auth/AuthChecker.kt", "imports", "extracted"), self.edges)
        self.assertIn((svc, "code:demo:paths:svc/src/main/kotlin/io/x/model/", "imports", "inferred"), self.edges)   # wildcard → package dir
        self.assertNotIn(("code:demo:symbols:Service", svc, "member_of", "extracted"), self.edges)                    # external import is not a symbol
        self.assertIn(("code:demo:symbols:AuthChecker", "code:demo:paths:svc/src/main/kotlin/io/x/auth/AuthChecker.kt", "member_of", "extracted"), self.edges)
        self.assertIn((svc, "code:demo:paths:svc/src/main/kotlin/io/x/refunds/", "member_of", "extracted"), self.edges)
        self.assertIn(("code:demo:paths:svc/src/main/kotlin/io/x/refunds/", "code:demo:paths:svc/src/main/kotlin/io/x/", "member_of", "extracted"), self.edges)
        self.assertIn(("code:demo:paths:svc/src/main/kotlin/io/x/auth/AuthFilter.kt", "code:demo:paths:svc/src/main/kotlin/io/x/auth/AuthChecker.kt", "imports", "inferred"), self.edges)   # same package, no import line
        self.assertIn(("code:demo:paths:svc2/src/main/kotlin/io/x/web/Ctl.kt", "code:demo:paths:svc2/src/main/kotlin/io/x/auth/AuthChecker.kt", "imports", "extracted"), self.edges)   # same module wins
        self.assertNotIn(("code:demo:paths:svc2/src/main/kotlin/io/x/web/Ctl.kt", "code:demo:paths:svc/src/main/kotlin/io/x/auth/AuthChecker.kt", "imports", "extracted"), self.edges)
        self.assertEqual(self.nodes["code:demo:symbols:AuthChecker"].payload["files"], ["svc/src/main/kotlin/io/x/auth/AuthChecker.kt", "svc2/src/main/kotlin/io/x/auth/AuthChecker.kt"])
        t = "code:demo:paths:svc/src/test/kotlin/io/x/refunds/RefundServiceTest.kt"
        self.assertIn((t, svc, "imports", "extracted"), self.edges)
        self.assertIn((t, svc, "tests", "inferred"), self.edges)
        page = "code:demo:paths:web/src/app/page.tsx"
        self.assertIn((page, "code:demo:paths:packages/ui/src/index.ts", "imports", "extracted"), self.edges)   # @shared/ui → package index
        self.assertIn((page, "code:demo:paths:packages/ui/src/fmt.ts", "imports", "extracted"), self.edges)     # @shared/ui/fmt
        self.assertIn((page, "code:demo:paths:web/src/app/x.ts", "imports", "extracted"), self.edges)           # relative
        self.assertIn((page, "code:demo:paths:web/src/lib/y.ts", "imports", "extracted"), self.edges)           # src/* alias of the app
        self.assertFalse(any(dst.endswith("react") for _, dst, _, _ in self.edges))                               # external package: no edge
        self.assertIn(("code:demo:paths:web/src/__tests__/page.test.tsx", page, "tests", "inferred"), self.edges)
        a = "code:demo:paths:tools/a.py"
        self.assertIn((a, "code:demo:paths:tools/b.py", "imports", "extracted"), self.edges)
        self.assertIn((a, "code:demo:paths:tools/c.py", "imports", "extracted"), self.edges)
        self.assertIn(("code:demo:paths:tools/test_a.py", a, "tests", "inferred"), self.edges)

    def test_store_resolves_covers_targets(self):
        store = SqliteStore(":memory:")
        store.put_nodes(self.out.nodes); store.put_edges(self.out.edges)
        store.put_nodes([Node(id="doc:x", kind="doc", project="demo", path="x.md", title="x")])
        store.put_edges([Edge("doc:x", "code:demo:paths:svc/src/main/kotlin/io/x/refunds/", "covers", "declared", "covers.paths"),
                         Edge("doc:x", "code:demo:symbols:AuthChecker", "covers", "declared", "covers.symbols"),
                         Edge("doc:x", "code:demo:symbols:Gone", "covers", "declared", "covers.symbols")])
        dangling = {e.dst for e in store.dangling_edges() if e.src == "doc:x"}
        self.assertEqual(dangling, {"code:demo:symbols:Gone"})
        store.close()

    def test_owner_votes_rank_neighbour_owners_without_the_files_own_covers(self):
        from kb.code import owner_votes
        store = SqliteStore(":memory:")
        store.put_nodes(self.out.nodes); store.put_edges(self.out.edges)
        store.put_nodes([Node(id="doc:a.md", kind="doc", project="demo", path="a.md", title="a"),
                         Node(id="doc:b.md", kind="doc", project="demo", path="b.md", title="b")])
        store.put_edges([Edge("doc:a.md", "code:demo:paths:svc/src/main/kotlin/io/x/refunds/", "covers", "declared", "covers.paths"),
                         Edge("doc:b.md", "code:demo:paths:svc/src/main/kotlin/io/x/auth/", "covers", "declared", "covers.paths")])
        v = owner_votes(store, "demo", ["code:demo:paths:svc/src/main/kotlin/io/x/refunds/RefundService.kt"])
        self.assertEqual(v["truth"], ["a.md"])            # the human-written owner
        self.assertEqual(v["ranked"], ["b.md"])           # the neighbour (AuthChecker.kt) votes for its owner; a.md is not consulted
        self.assertEqual(v["neighbours"], 2)              # AuthChecker.kt (import out) and the test file (import in)
        store.close()

    def test_is_test_path(self):
        for p in ("a/src/test/kotlin/X.kt", "a/XTest.kt", "web/src/__tests__/p.tsx", "web/p.test.tsx", "tools/test_a.py", "tools/a_test.py"):
            self.assertTrue(is_test_path(p), p)
        for p in ("a/src/main/kotlin/X.kt", "web/src/app/page.tsx", "tools/a.py", "tools/testing_utils.py"):
            self.assertFalse(is_test_path(p), p)


if __name__ == "__main__":
    unittest.main()
