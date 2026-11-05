"""Layer and naming hooks on a detached project (order 2026.10.29-02 task-04): the layer map lives in the vault Tier P,
and a PreToolUse call checks the content about to be written and blocks it (exit 2) before the file changes."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KB = Path(__file__).resolve().parents[1]

MAP = """version: "1.0"
project: "demo"
project_type: "backend"
mappings:
  - path: "svc/l2/"
    layer: "L2_DataLayer"
  - path: "svc/l3/"
    layer: "L3_Composite"
"""


class DetachedHooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.repo, vault_proj = root / "demo", root / "vault" / "projects" / "demo"
        (self.repo / ".strata" / "local").mkdir(parents=True)
        (self.repo / "CLAUDE.md").write_text("# demo\n")
        (vault_proj / "strata").mkdir(parents=True)
        (vault_proj / "strata" / "layer-map.yaml").write_text(MAP)
        (self.repo / ".strata" / "local" / "vault-link.yaml").write_text(f"profile: detached\nvault_project_path: {vault_proj}\n")
        (self.repo / "svc" / "l2").mkdir(parents=True)
        (self.repo / "svc" / "l3").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, cmd: str, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(["python3", str(KB), cmd], input=json.dumps(payload), cwd=self.repo,
                              capture_output=True, text=True)

    def test_post_write_finds_the_vault_layer_map(self):
        f = self.repo / "svc" / "l2" / "OrderQueryService.kt"
        f.write_text("package x\nimport org.jooq.DSLContext\nclass OrderQueryService(val dsl: DSLContext)\n")
        r = self.hook("check-layer", {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(f)}})
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("DSLContext", r.stderr)

    def test_pre_write_blocks_before_the_file_exists(self):
        f = self.repo / "svc" / "l2" / "OrderQueryService.kt"
        r = self.hook("check-layer", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                                      "tool_input": {"file_path": str(f), "content": "package x\nimport org.jooq.DSLContext\n"}})
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("쓰기 전 차단", r.stderr)
        self.assertFalse(f.exists())

    def test_pre_edit_checks_the_edited_result(self):
        f = self.repo / "svc" / "l2" / "OrderRepository.kt"
        f.write_text("package x\ninterface OrderRepository {\n    fun findAll(): List<Int>\n}\n")
        edit = {"file_path": str(f), "old_string": "    fun findAll", "new_string": "    @Query(\"select 1\")\n    fun findAll"}
        r = self.hook("check-layer", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": edit})
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("@Query", f.read_text())                       # the file on disk is untouched
        clean = {"file_path": str(f), "old_string": "findAll", "new_string": "findEvery"}
        self.assertEqual(self.hook("check-layer", {"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": clean}).returncode, 0)

    def test_naming_warns_on_detached_layer(self):
        f = self.repo / "svc" / "l3" / "OrderFooBar.kt"
        r = self.hook("validate-naming", {"tool_input": {"file_path": str(f)}})
        self.assertIn("L3_Composite", r.stdout)
        ok = self.hook("validate-naming", {"tool_input": {"file_path": str(self.repo / "svc" / "l3" / "OrderCommandCompositeService.kt")}})
        self.assertNotIn("네이밍 컨벤션 경고", ok.stdout)


    def test_harness_files_are_not_named_like_code(self):
        # a command file's name is the command (.claude/commands/handoff.md) — not a code file (a backend project, 2026-11-02)
        for rel in (".claude/commands/handoff.md", ".claude/agents/reviewer.md", ".codex/prompts/wrap-up.md", ".strata/kit/notes.ko.md"):
            r = self.hook("validate-naming", {"tool_input": {"file_path": str(self.repo / rel)}})
            self.assertNotIn("네이밍 컨벤션 경고", r.stdout, rel)
        bad = self.hook("validate-naming", {"tool_input": {"file_path": str(self.repo / "svc" / "l3" / "OrderFooBar.kt")}})
        self.assertIn("네이밍 컨벤션 경고", bad.stdout)                          # code files are still checked

WEB_MAP = """variant: web
feature_root: "/modules/"
zones:
  target: ["apps/a/"]
  legacy: ["apps/old/"]
mappings:
  - { path: "/modules/", layer: "Feature_Block" }
  - { path: "src/ui/semantic/", layer: "Semantic_Component" }
exceptions:
  - { id: "EX-1", decision: "DEC-1", from_path: "apps/a/src/ui/semantic/Waived", to_layer: "DataState", status: "active" }
  - { id: "EX-2", decision: "DEC-2", from_path: "apps/a/src/ui/semantic/Retired", to_layer: "DataState", status: "retired" }
"""
BAD = 'import { useOrderQuery } from "src/data-state/order"\nexport const Card = () => null\n'


class ZonesExceptionsTest(unittest.TestCase):
    """planning/hook-zones-exceptions (DEC-2026-10-31-20·21): the edit hooks read layer-map zones, exceptions and
    feature_root as CI does, warn on HTTP-verb hook names from the naming rules, and speak in the event they were called on."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name).resolve() / "web"
        (self.repo / ".strata").mkdir(parents=True)
        (self.repo / "CLAUDE.md").write_text("# web\n")
        (self.repo / ".strata" / "layer-map.yaml").write_text(WEB_MAP)
        self.env = {k: v for k, v in os.environ.items() if k != "STRATA_PROJECT_TYPE"}   # stack comes from variant: web

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, cmd, payload):
        return subprocess.run(["python3", str(KB), cmd], input=json.dumps(payload), cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def write(self, rel, content, event="PreToolUse", cmd="check-layer"):
        return self.hook(cmd, {"hook_event_name": event, "tool_name": "Write",
                               "tool_input": {"file_path": str(self.repo / rel), "content": content}})

    def test_legacy_zone_is_not_direction_checked(self):
        for event in ("PreToolUse", "PostToolUse"):
            if event == "PostToolUse":
                for app in ("old", "a", "b"):
                    f = self.repo / "apps" / app / "src/ui/semantic/Card.tsx"; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(BAD)
            legacy = self.write("apps/old/src/ui/semantic/Card.tsx", BAD, event)
            self.assertEqual(legacy.returncode, 0, legacy.stderr)
            self.assertEqual(legacy.stdout, "")                                   # no warning either (DEC-2026-10-31-20)
            for app in ("a", "b"):                                                # target zone and no zone: blocked as before
                r = self.write(f"apps/{app}/src/ui/semantic/Card.tsx", BAD, event)
                self.assertEqual(r.returncode, 2, (app, event, r.stderr))

    def test_exception_waives_only_its_layer_and_retired_does_not(self):
        both = BAD + 'import { OrderSection } from "src/features/order/OrderSection"\n'
        r = self.write("apps/a/src/ui/semantic/WaivedCard.tsx", both)
        self.assertEqual(r.returncode, 2, r.stderr)                               # Feature_Block is still banned
        blocked = [line for line in r.stderr.splitlines() if "참조 불가" in line]
        self.assertEqual(len(blocked), 1)
        self.assertIn("Feature_Block 참조 불가", blocked[0])                       # the DataState import was waived
        self.assertIn("EX-1 → DataState", r.stderr)
        ok = self.write("apps/a/src/ui/semantic/WaivedCard.tsx", BAD)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        ctx = json.loads(ok.stdout)["hookSpecificOutput"]
        self.assertEqual(ctx["hookEventName"], "PreToolUse")
        self.assertIn("EX-1(DEC-1)", ctx["additionalContext"])
        self.assertEqual(self.write("apps/a/src/ui/semantic/RetiredCard.tsx", BAD).returncode, 2)

    def test_feature_root_sets_the_domain(self):
        other = 'import { OrderSection } from "src/features/orders/OrderSection"\n'
        same = 'import { BillPanel } from "src/features/billing/BillPanel"\n'
        r = self.write("apps/a/modules/billing/BillSection.tsx", other)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("billing → orders", r.stderr)
        self.assertEqual(self.write("apps/a/modules/billing/BillSection.tsx", same).returncode, 0)

    def test_domain_slice_sets_the_domain_without_feature_root(self):
        # DEC-2026-11-01-19: no feature_root — the root comes from layer-rules Feature_Block.domain_slice (src/features/)
        (self.repo / ".strata" / "layer-map.yaml").write_text('variant: web\nmappings:\n  - { path: "src/features/", layer: "Feature_Block" }\n')
        for rel in ("src/features/orders/OrderSection.tsx", "src/features/billing/BillPanel.tsx"):
            f = self.repo / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text("export const X = 1\n")
        r = self.write("src/features/billing/BillSection.tsx", 'import { OrderSection } from "../orders/OrderSection"\n')
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("billing → orders", r.stderr)
        self.assertEqual(self.write("src/features/billing/BillSection.tsx", 'import { BillPanel } from "./BillPanel"\n').returncode, 0)

    def test_forbidden_component_suffix_warns_on_new_definitions(self):
        # naming-convention Feature_Block.forbidden_suffixes, read from the rule file (DEC-2026-11-01-19)
        for text in ("export function OrderBlock() {}\n", "export const OrderContainer = () => null\n",
                     "const OrderSection = () => null\nexport { OrderSection as OrderPartial }\n"):
            r = self.naming("apps/a/modules/order/Order.tsx", {"content": text})
            self.assertEqual(r.returncode, 0)
            self.assertIn("금지 접미", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"], text)
        self.assertNotIn("금지 접미", self.naming("apps/a/modules/order/OrderSection.tsx", {"content": "export const OrderSection = () => null\n"}).stdout)
        f = self.repo / "apps/a/modules/order/Old.tsx"; f.parent.mkdir(parents=True, exist_ok=True); f.write_text("export const OldContainer = () => null\n")
        self.assertNotIn("금지 접미", self.naming("apps/a/modules/order/Old.tsx", {"content": "export const OldContainer = () => null\nconst y = 2\n"}).stdout)

    def naming(self, rel, tool_input, tool="Write", event="PreToolUse"):
        return self.hook("validate-naming", {"hook_event_name": event, "tool_name": tool,
                                             "tool_input": {"file_path": str(self.repo / rel), **tool_input}})

    def test_forbidden_hook_prefix_warns_through_additional_context(self):
        import yaml
        prefixes = yaml.safe_load((KB.parent / "core/rules/naming-convention.yaml").read_text(encoding="utf-8"))["frontend"]["DataState"]["forbidden_hook_prefixes"]
        self.assertEqual(len(prefixes), 6)
        for p in prefixes:
            r = self.naming("apps/a/hooks/user.ts", {"content": f"export function {p}User() {{}}\n"})
            self.assertEqual(r.returncode, 0)
            ctx = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(ctx["hookEventName"], "PreToolUse")
            self.assertIn(f"'{p}'", ctx["additionalContext"])
            self.assertIn("use{Entity}Query", ctx["additionalContext"])
        post = self.naming("apps/a/hooks/user.ts", {"content": "export const useGetUser = () => null\n"}, event="PostToolUse")
        self.assertEqual(json.loads(post.stdout)["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertEqual(self.naming("apps/a/hooks/user.ts", {"content": "export function useLoadUser() {}\n"}).stdout, "")
        self.assertEqual(self.naming("apps/a/hooks/user.ts", {"content": "export function useGetter() {}\n"}).stdout, "")

    def test_only_new_definitions_in_frontend_files_warn(self):
        f = self.repo / "apps/a/hooks/user.ts"; f.parent.mkdir(parents=True); f.write_text("export function useGetUser() {}\n")
        self.assertEqual(self.naming("apps/a/hooks/user.ts", {"content": "export function useGetUser() {}\nconst x = 1\n"}).stdout, "")
        call = {"old_string": "", "new_string": "const u = useGetUser()\n"}
        self.assertEqual(self.naming("apps/a/hooks/user.ts", call, tool="Edit").stdout, "")
        added = {"old_string": "export function useGetUser() {}", "new_string": "export function useGetUser() {}\nexport function usePostUser() {}"}
        self.assertIn("usePostUser", self.naming("apps/a/hooks/user.ts", added, tool="Edit").stdout)
        self.assertEqual(self.naming("svc/UserService.kt", {"content": "fun useGetUser() {}\n"}).stdout, "")


MONO_MAP = """variant: web
feature_root: "/features/"
mappings:
  - { path: "shared/data-access/", layer: "DataState" }
  - { path: "/hooks/api/", layer: "DataState" }
  - { path: "Section.tsx", layer: "Feature_Block" }
  - { path: "/ui/", layer: "Semantic_Component" }
  - { path: "/app/", layer: "Route_Surface" }
"""


class ResolvedImportsTest(unittest.TestCase):
    """MB-strata-kit-2026-041: imports are resolved to paths (relative, tsconfig paths, workspace packages) and the
    layer-map names their layer, as dependency-cruiser does — an alias no longer slips past — and an edit is blocked
    only for violations it adds, so an unrelated edit to a file with old violations goes through."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.repo = Path(self.tmp.name).resolve() / "mono"
        (r / ".strata").mkdir(parents=True)
        (r / "CLAUDE.md").write_text("# mono\n")
        (r / ".strata" / "layer-map.yaml").write_text(MONO_MAP)
        files = {
            "apps/catalog/tsconfig.json": '{\n  // comment\n  "compilerOptions": { "baseUrl": ".", "paths": { "@/*": ["./src/*"], "src/*": ["src/*"], }, },\n}\n',
            "apps/catalog/src/shared/hooks/api/useOrders.ts": "export const useOrdersQuery = () => null\n",
            "apps/catalog/src/features/order/ui/OrderCard.tsx": "export const OrderCard = () => null\n",
            "apps/catalog/src/app/globals.css": "body {}\n",
            "shared/data-access/package.json": '{"name": "@shared/data-access"}\n',
            "shared/data-access/src/index.ts": "export const client = 1\n",
        }
        for rel, text in files.items():
            (r / rel).parent.mkdir(parents=True, exist_ok=True); (r / rel).write_text(text)
        subprocess.run(["git", "-C", str(r), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
        self.env = {k: v for k, v in os.environ.items() if k != "STRATA_PROJECT_TYPE"}
        self.card = r / "apps/catalog/src/features/order/ui/OrderCard.tsx"

    def tearDown(self):
        self.tmp.cleanup()

    def pre(self, path, content=None, edit=None):
        ti = {"file_path": str(path), **({"content": content} if content is not None else edit)}
        return subprocess.run(["python3", str(KB), "check-layer"], cwd=self.repo, env=self.env, capture_output=True, text=True,
                              input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write" if content is not None else "Edit", "tool_input": ti}))

    def test_every_import_shape_resolves_to_its_layer(self):
        for imp in ("@/shared/hooks/api/useOrders", "src/shared/hooks/api/useOrders", "../../../shared/hooks/api/useOrders", "@shared/data-access"):
            r = self.pre(self.card, f'import {{\n  x,\n}} from "{imp}"\nexport const OrderCard = () => null\n')
            self.assertEqual(r.returncode, 2, (imp, r.stderr))
            self.assertIn("Semantic_Component에서 DataState 참조 불가", r.stderr)
        css = self.pre(self.card, 'import "../../../app/globals.css"\nexport const OrderCard = () => null\n')
        self.assertEqual(css.returncode, 0, css.stderr)                            # a stylesheet is not a layer
        ok = self.pre(self.card, 'import { useState } from "react"\nexport const OrderCard = () => null\n')
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_only_violations_the_edit_adds_block(self):
        self.card.write_text('import { useOrdersQuery } from "@/shared/hooks/api/useOrders"\nexport const OrderCard = () => null\n')
        unrelated = self.pre(self.card, edit={"old_string": "() => null", "new_string": "() => 1"})
        self.assertEqual(unrelated.returncode, 0, unrelated.stderr)                # the old violation does not block
        self.assertIn("원래 있던 위반 1건", json.loads(unrelated.stdout)["hookSpecificOutput"]["additionalContext"])
        added = self.pre(self.card, edit={"old_string": "export const", "new_string": 'import { client } from "@shared/data-access"\nexport const'})
        self.assertEqual(added.returncode, 2, added.stderr)
        self.assertIn("shared/data-access", added.stderr)
        self.assertNotIn("useOrders", added.stderr.split("❌")[1].split("예외")[0].split("import:")[-1])


REPO_MAP = """version: "2.0"
project: "demo"
layers:
  component_L1: { level: 1, can_reference: [] }
  inherit_LM1: { level: 1.5, can_reference: [component_L1] }
  data_L2: { level: 2, can_reference: [component_L1, inherit_LM1] }
  coordinate_LM2: { level: 2.5, can_reference: [data_L2, component_L1, inherit_LM1] }
  composite_L3: { level: 3, can_reference: [data_L2, coordinate_LM2, component_L1] }
  controller_L4: { level: 4, can_reference: [composite_L3, component_L1] }
excluded:
  - "svc/old/"
mappings:
  - path: "svc/l2/"
    layer: "data_L2"
  - path: "svc/l3/"
    layer: "composite_L3"
  - path: "svc/infra/"
    layer: "infra"
exceptions:
  - { id: "EX-1", decision: "DEC-1", from_path: "svc/l3/", to_layer: "inherit_LM1" }
"""


class RepoArchunitLayerMapTest(unittest.TestCase):
    """MB-strata-kit-2026-018: a repo that keeps its layer map at archunit/layer-map.yaml (CI reads it there) with its own
    layer names (identifier + level: data_L2 ...). The hooks read it before the vault Tier P copy and map each name to
    the kit layer of the same level, so the kit rules apply; excluded paths are the legacy zone."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.repo, vault_proj = root / "demo", root / "vault" / "projects" / "demo"
        (self.repo / ".strata" / "local").mkdir(parents=True)
        (self.repo / "CLAUDE.md").write_text("# demo\n")
        (self.repo / "archunit").mkdir()
        (self.repo / "archunit" / "layer-map.yaml").write_text(REPO_MAP)
        (vault_proj / "strata").mkdir(parents=True)
        (vault_proj / "strata" / "layer-map.yaml").write_text('mappings:\n  - { path: "svc/", layer: "_old_copy" }\n')   # the old vault copy
        (self.repo / ".strata" / "local" / "vault-link.yaml").write_text(f"profile: detached\nvault_project_path: {vault_proj}\n")
        self.env = {k: v for k, v in os.environ.items() if k != "STRATA_PROJECT_TYPE"}

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, cmd, payload):
        return subprocess.run(["python3", str(KB), cmd], input=json.dumps(payload), cwd=self.repo, env=self.env,
                              capture_output=True, text=True)

    def test_repo_map_wins_over_the_vault_copy_and_names_map_to_kit_layers(self):
        r = self.hook("check-layer", {"hook_event_name": "PreToolUse", "tool_name": "Write",
                                      "tool_input": {"file_path": str(self.repo / "svc/l2/OrderQueryService.kt"),
                                                     "content": "package x\nimport org.jooq.DSLContext\nclass OrderQueryService\n"}})
        self.assertEqual(r.returncode, 2, r.stderr + r.stdout)
        self.assertIn("현재 레이어: L2_DataLayer", r.stderr)
        n = self.hook("validate-naming", {"tool_input": {"file_path": str(self.repo / "svc/l3/OrderFooBar.kt")}})
        self.assertIn("L3_Composite", n.stdout)

    def test_translation_of_names_zones_and_exceptions(self):
        import sys
        sys.path.insert(0, str(KB.parent))
        from kb.legacy import check_layer_violation as C
        m = C.load_project_layer_map(str(self.repo))
        self.assertEqual([x["layer"] for x in m["mappings"]], ["L2_DataLayer", "L3_Composite", "infra"])   # undeclared names stay unchecked
        self.assertEqual(m["zones"]["legacy"], ["svc/old/"])
        self.assertEqual(m["exceptions"][0]["to_layer"], "LM1_Inherite")
        self.assertEqual(m.get("_problems"), [])
        self.assertEqual(C._layer_map_path(str(self.repo)), str(self.repo / "archunit" / "layer-map.yaml"))

    def test_drift_from_kit_rules_is_reported(self):
        (self.repo / "archunit" / "layer-map.yaml").write_text(REPO_MAP.replace(
            "composite_L3: { level: 3, can_reference: [data_L2, coordinate_LM2, component_L1] }",
            "composite_L3: { level: 3, can_reference: [data_L2, coordinate_LM2, component_L1, inherit_LM1] }").replace(
            "controller_L4: { level: 4,", "controller_L4: { level: 7,"))
        import sys
        sys.path.insert(0, str(KB.parent))
        from kb.legacy import check_layer_violation as C
        problems = C.load_project_layer_map(str(self.repo))["_problems"]
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("composite_L3" in p and "L3_Composite" in p for p in problems))
        self.assertTrue(any("controller_L4" in p for p in problems))
        f = self.repo / "svc/l3/OrderCommandCompositeService.kt"
        f.parent.mkdir(parents=True); f.write_text("package x\nclass OrderCommandCompositeService\n")
        r = self.hook("check-layer", {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": str(f)}})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("composite_L3", r.stdout)                                   # the agent is told, the edit is not blocked


if __name__ == "__main__":
    unittest.main()
