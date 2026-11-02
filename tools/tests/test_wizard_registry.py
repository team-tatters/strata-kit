"""Header names every skill registry layer and whether it is there (MB-strata-kit-2026-001); the project layer is read
from .strata/kit/registry.yaml and from Tier P skills/registry.yaml (detached projects keep theirs in the vault)."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools"))

import wizard  # noqa: E402

ROUTES = "version: '0.1'\nroutes:\n- {intent: a, skill: qa.a}\n- {intent: b, skill: qa.b}\n"


class RegistryLayersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / "demo"
        (self.project / ".strata" / "kit").mkdir(parents=True)
        self.tier_root = Path(self.tmp.name) / "vault" / "projects" / "demo" / "strata"
        (self.tier_root / "skills").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_layers_with_detached_project_registry(self):
        (self.project / ".strata" / "kit" / "registry.yaml").write_text("version: '0.1'\nroutes: []\n")
        (self.tier_root / "skills" / "registry.yaml").write_text(ROUTES)
        tier = SimpleNamespace(root=self.tier_root, profile="detached")
        from unittest import mock
        with mock.patch.dict("os.environ", {"STRATA_USER_SKILLS": str(self.project / "no-user-layer")}):   # the user layer stays empty
            line = wizard.registry_line(self.project, KIT, "core.generic", tier)
        self.assertRegex(line, r"^skill registry: core ok\(\d+ routes\) · profile core\.generic absent · user absent · project ok\(")
        self.assertIn("2 routes", line)
        self.assertIn("strata/skills/registry.yaml", line)
        self.assertEqual(wizard.project_registries(self.project, tier),
                         [self.project / ".strata" / "kit" / "registry.yaml", self.tier_root / "skills" / "registry.yaml"])

    def test_project_layer_absent(self):
        line = wizard.registry_line(self.project, KIT, "core.generic", None)
        self.assertTrue(line.endswith("project absent"), line)


if __name__ == "__main__":
    unittest.main()
