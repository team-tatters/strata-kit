"""next-web CI templates (MB-strata-kit-2026-035): failing fixtures for the defects a cross-vendor review found, run on
the real dependency-cruiser and node. The layer template: transport (`*.service`) imported by anything but a DataState
adapter, one exception unlocking every banned target, targets outside every mapping, `frontend_variant` ignored. The
diff checker: a query key split over lines or built in a variable, and an expired exception marker on an unchanged line.

dependency-cruiser comes from STRATA_DEPCRUISE_MODULES (a node_modules directory) or a web project's; without it the
layer cases are skipped, the diff cases still run."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
ENF = KIT / "profiles" / "frontend.next-web" / "enforcement"
def _modules() -> Path:
    """STRATA_DEPCRUISE_MODULES, else the first node_modules with dependency-cruiser under ~/workspace/projects/*."""
    env = os.environ.get("STRATA_DEPCRUISE_MODULES")
    if env:
        return Path(env)
    found = sorted(Path.home().glob("workspace/projects/*/node_modules/dependency-cruiser/bin/dependency-cruise.mjs"))
    return found[0].parents[2] if found else Path.home() / "workspace/projects/web/node_modules"


MODULES = _modules()
CRUISE = MODULES / "dependency-cruiser" / "bin" / "dependency-cruise.mjs"
NODE = shutil.which("node")

LAYER_MAP = {
    "frontend_variant": "web",
    "mappings": [
        {"path": "src/foundation/", "layer": "Foundation"},
        {"path": "src/data-state/", "layer": "DataState"},
        {"path": "src/ui/semantic/", "layer": "Semantic_Component"},
        {"path": "src/features/", "layer": "Feature_Block"},
    ],
    "exceptions": [{"id": "EX-1", "decision": "DEC-1", "from_path": "src/ui/semantic/Card", "to_layer": "DataState", "status": "active"}],
}
FILES = {
    "src/foundation/util.ts": "export const one = 1\n",
    "src/data-state/order.service.ts": "export const getOrders = () => fetch('/orders')\n",
    "src/data-state/useOrderQuery.ts": "import { getOrders } from './order.service'\nexport const useOrderQuery = () => getOrders()\n",
    "src/features/order/OrderSection.tsx": "import { getOrders } from '../../data-state/order.service'\nexport const OrderSection = () => getOrders()\n",
    "src/features/order/OrderPanel.tsx": "import { useOrderQuery } from '../../data-state/useOrderQuery'\nexport const OrderPanel = () => useOrderQuery()\n",
    "src/ui/semantic/Card.tsx": "import { useOrderQuery } from '../../data-state/useOrderQuery'\nimport { OrderPanel } from '../../features/order/OrderPanel'\nexport const Card = () => [useOrderQuery(), OrderPanel]\n",
    "src/ui/semantic/Loose.tsx": "import { help } from '../../misc/helper'\nexport const Loose = () => help()\n",
    "src/misc/helper.ts": "export const help = () => 1\n",
}


@unittest.skipUnless(NODE and CRUISE.is_file(), "dependency-cruiser not available")
class LayerTemplateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.dir = Path(self.tmp.name)
        for rel, text in FILES.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True); (d / rel).write_text(text)
        rules = yaml.safe_load((KIT / "core/rules/layer-rules.yaml").read_text(encoding="utf-8"))
        (d / "rules.json").write_text(json.dumps(rules))
        (d / "layer-map.json").write_text(json.dumps(LAYER_MAP))
        shutil.copy(ENF / "depcruise-layers.core.cjs.template", d / "core.cjs")
        (d / "cfg.cjs").write_text("module.exports = require('./core.cjs')(require('./rules.json'), require('./layer-map.json'), "
                                   "{ doNotFollow: { path: ['node_modules'] } });\n")

    def tearDown(self):
        self.tmp.cleanup()

    def cruise(self):
        r = subprocess.run([NODE, str(CRUISE), "--config", "cfg.cjs", "--output-type", "json", "src"], cwd=self.dir,
                           capture_output=True, text=True, env={**os.environ, "NODE_PATH": str(MODULES)})
        out = json.loads(r.stdout)
        return {(v["from"], v["to"], v["rule"]["name"], v["rule"]["severity"]) for v in out["summary"]["violations"]}

    def write(self, rel, text):
        (self.dir / rel).parent.mkdir(parents=True, exist_ok=True); (self.dir / rel).write_text(text)

    def by_pair(self):
        return {(f, t): (n, s) for f, t, n, s in self.cruise()}

    def test_transport_is_for_adapters_only(self):
        v = self.by_pair()
        self.assertIn(("src/features/order/OrderSection.tsx", "src/data-state/order.service.ts"), v)
        self.assertNotIn(("src/data-state/useOrderQuery.ts", "src/data-state/order.service.ts"), v)

    def test_an_exception_waives_only_its_target_layer(self):
        v = self.by_pair()
        self.assertNotIn(("src/ui/semantic/Card.tsx", "src/data-state/useOrderQuery.ts"), v)   # EX-1 → DataState
        self.assertIn(("src/ui/semantic/Card.tsx", "src/features/order/OrderPanel.tsx"), v)   # Feature_Block stays banned

    def test_a_target_outside_every_mapping_is_reported(self):
        name, severity = self.by_pair()[("src/ui/semantic/Loose.tsx", "src/misc/helper.ts")]
        self.assertEqual(severity, "warn")

    def test_feature_domains_are_isolated_without_feature_root(self):
        # DEC-2026-11-01-19: no feature_root in the layer-map — the domain comes from layer-rules Feature_Block.domain_slice
        self.write("src/features/billing/BillingSection.tsx", "export const BillingSection = () => 1\n")
        self.write("src/features/order/OrderSummary.tsx",
                   "import { BillingSection } from '../billing/BillingSection'\nimport { OrderPanel } from './OrderPanel'\n"
                   "export const OrderSummary = () => [BillingSection, OrderPanel]\n")
        v = self.by_pair()
        self.assertEqual(v.get(("src/features/order/OrderSummary.tsx", "src/features/billing/BillingSection.tsx")),
                         ("layer:Feature_Block-isolation", "error"))
        self.assertNotIn(("src/features/order/OrderSummary.tsx", "src/features/order/OrderPanel.tsx"), v)   # same domain

    def test_a_directory_mapped_feature_block_is_isolated_under_feature_root(self):
        # feature_root equal to the Feature_Block mapping: the root appears once in the path (codex review 2026-11-01)
        lm = {**LAYER_MAP, "feature_root": "src/features/"}
        (self.dir / "layer-map.json").write_text(json.dumps(lm))
        self.write("src/features/billing/Billing.tsx", "export const Billing = () => 1\n")
        self.write("src/features/order/Order.tsx", "import { Billing } from '../billing/Billing'\nexport const Order = () => Billing\n")
        v = self.by_pair()
        self.assertEqual(v.get(("src/features/order/Order.tsx", "src/features/billing/Billing.tsx")),
                         ("layer:Feature_Block-isolation", "error"))

    def test_a_route_page_assembles_sections_of_two_domains(self):
        # {Route}Page is Route_Surface wherever it sits; its mapping comes before the Feature_Block one
        lm = {**LAYER_MAP, "mappings": [{"path": "Page.tsx", "layer": "Route_Surface"}] + LAYER_MAP["mappings"]}
        (self.dir / "layer-map.json").write_text(json.dumps(lm))
        self.write("src/features/billing/BillingSection.tsx", "export const BillingSection = () => 1\n")
        self.write("src/features/order/CheckoutPage.tsx",
                   "import { BillingSection } from '../billing/BillingSection'\nimport { OrderPanel } from './OrderPanel'\n"
                   "export const CheckoutPage = () => [BillingSection, OrderPanel]\n")
        v = self.by_pair()
        self.assertNotIn(("src/features/order/CheckoutPage.tsx", "src/features/billing/BillingSection.tsx"), v)

    def test_frontend_variant_is_read(self):
        lm = {**LAYER_MAP, "frontend_variant": "nope"}
        (self.dir / "layer-map.json").write_text(json.dumps(lm))
        r = subprocess.run([NODE, "-e", "require('./cfg.cjs')"], cwd=self.dir, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("variants.nope", r.stderr)


@unittest.skipUnless(NODE, "node not available")
class DiffRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.dir = Path(self.tmp.name)
        shutil.copy(ENF / "check-diff-rules.cjs.template", d / "check.cjs")
        shutil.copy(ENF / "diff-rules.json.template", d / "diff-rules.json")
        git = lambda *a: subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)
        self.git = git
        git("init", "-q")
        (d / "src").mkdir()
        (d / "src/ok.ts").write_text("export const x = 1\n")
        git("add", "-A"); git("commit", "-q", "-m", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, rel, text):
        (self.dir / rel).write_text(text)
        r = subprocess.run([NODE, "check.cjs", "--file", rel], cwd=self.dir, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def test_query_key_over_lines_and_in_a_variable(self):
        rc, out = self.check("src/useA.ts", "export const useA = () => useQuery({\n  queryKey:\n    ['orders', id],\n})\n")
        self.assertEqual(rc, 1, out); self.assertIn("no-inline-query-key", out)
        rc, out = self.check("src/useB.ts", "const ordersKey = ['orders', id]\nexport const useB = () => useQuery({ queryKey: ordersKey })\n")
        self.assertEqual(rc, 1, out); self.assertIn("no-inline-query-key", out)
        rc, out = self.check("src/useC.ts", "export const useC = () => useQuery({ queryKey: orderKeys.detail(id) })\n")
        self.assertEqual(rc, 0, out)

    def test_forbidden_component_suffix_in_every_declaration_form(self):
        # DEC-2026-11-01-19: .jsx too, an export alias, var, and a name on the line after the keyword
        for rel, text in (("src/A.tsx", "export function OrderBlock() {}\n"),
                          ("src/B.jsx", "export const OrderContainer = () => null\n"),
                          ("src/C.tsx", "const OrderSection = () => null\nexport { OrderSection as OrderBlock }\n"),
                          ("src/D.tsx", "var OrderPartial = () => null\n"),
                          ("src/E.tsx", "export const\n  OrderBlock = () => null\n")):
            rc, out = self.check(rel, text)
            self.assertEqual(rc, 1, f"{rel}: {out}"); self.assertIn("no-forbidden-component-suffix", out)
        rc, out = self.check("src/F.tsx", "export const OrderSection = () => <OrderBlockquote />\n")
        self.assertEqual(rc, 0, out)

    def test_an_expired_marker_on_an_unchanged_line_is_found(self):
        (self.dir / "src/old.css").write_text("/* @strata:token-exception 이관 대기 until 2000-01-01 */\n.a { color: var(--x); }\n")
        self.git("add", "-A"); self.git("commit", "-q", "-m", "marker")
        rc, out = self.check("src/ok.ts", "export const x = 2\n")          # the change is elsewhere; old.css is untouched
        self.assertEqual(rc, 1, out)
        self.assertIn("src/old.css:1", out)
        self.assertIn("token-exception-expiry", out)


if __name__ == "__main__":
    unittest.main()
