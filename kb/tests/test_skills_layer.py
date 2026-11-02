"""The user skill layer (planning/user-skill-layer acceptance 1~5, DEC-2026-10-31-36): packs and local skills coexist
in one layer that only adds; a core skill is replaced only when a local skill says so; entries without a stage, a
kind or a SKILL.md are refused with the reason; install and link change nothing until --apply, keep what they replace,
and never touch files the layer did not make."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT)); sys.path.insert(0, str(KIT / "tools"))

from kb import skills_layer as sl  # noqa: E402


def skill(d: Path, name: str, desc="x"):
    (d / name).mkdir(parents=True, exist_ok=True)
    (d / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n# {name}\n")


def registry(d: Path, routes: str):
    d.mkdir(parents=True, exist_ok=True)
    (d / "registry.yaml").write_text("routes:\n" + routes)


class SkillsLayerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        r = self.root = Path(self.tmp.name).resolve() / "user"
        pack = r / "packs" / "ideation"
        registry(pack, "- {skill: ideation.seed, intent: grow, stage: ideation, kind: procedure}\n")
        skill(pack, "ideation.seed")
        local = r / "local"
        registry(local, "- {skill: my.notes, stage: retro, kind: procedure}\n"
                        "- {skill: strata.verify, stage: verify, kind: procedure, overrides: strata.verify}\n"
                        "- {skill: strata.handoff, stage: retro, kind: procedure}\n"
                        "- {skill: ideation.seed, stage: ideation, kind: procedure}\n"
                        "- {skill: no.stage, kind: procedure}\n"
                        "- {skill: no.file, stage: build, kind: check}\n")
        for n in ("my.notes", "strata.verify", "strata.handoff", "ideation.seed", "no.stage"):
            skill(local, n)
        self.core = KIT / "skills" / "registry.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_adds_except_an_explicit_core_override(self):
        r = sl.layer_status(self.core, None, [], self.root)
        self.assertEqual(sorted(e.skill for e in r["accepted"]), ["ideation.seed", "my.notes", "strata.verify"])
        self.assertEqual([e.skill for e in r["overrides"]], ["strata.verify"])
        refused = {(e.skill, e.origin): why for e, why in r["refused"]}
        self.assertIn("core 층에 같은 이름", refused[("strata.handoff", "local")])
        self.assertIn("overrides: strata.handoff", refused[("strata.handoff", "local")])
        self.assertIn("pack:ideation 층에 같은 이름", refused[("ideation.seed", "local")])   # a pack wins over local
        self.assertIn("stage 없음", refused[("no.stage", "local")])
        self.assertIn("SKILL.md 없음", refused[("no.file", "local")])
        text = sl.status_text(r)
        self.assertIn("packs ideation", text); self.assertIn("overrides: strata.verify", text); self.assertIn("refused 4", text)
        self.assertEqual(sl.status_text(sl.layer_status(self.core, None, [], Path(self.tmp.name) / "none")), "user absent")

    def test_a_pack_cannot_replace_a_core_skill(self):
        registry(self.root / "packs" / "bad", "- {skill: strata.spec, stage: spec, kind: procedure, overrides: strata.spec}\n")
        skill(self.root / "packs" / "bad", "strata.spec")
        r = sl.layer_status(self.core, None, [], self.root)
        self.assertIn("strata.spec", [e.skill for e, _ in r["refused"]])

    def digest(self, d: Path):
        return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}

    def test_install_previews_then_copies_and_keeps_what_it_replaces(self):
        kit = Path(self.tmp.name) / "kit"
        registry(kit / "skills" / "packs" / "ideation", "- {skill: ideation.seed, stage: ideation, kind: procedure}\n")
        skill(kit / "skills" / "packs" / "ideation", "ideation.seed", desc="new")
        before = self.digest(self.root)
        with mock.patch.object(sl, "KIT", kit):
            lines = sl.install("ideation", apply=False, root=self.root)
            self.assertEqual(self.digest(self.root), before)                  # preview writes nothing
            self.assertTrue(any("update registry.yaml" in l for l in lines))
            sl.install("ideation", apply=True, root=self.root, today="2026-10-31")
        self.assertIn("description: new", (self.root / "packs/ideation/ideation.seed/SKILL.md").read_text())
        self.assertIn("description: x", (self.root / ".archive/2026-10-31/packs/ideation/ideation.seed/SKILL.md").read_text())
        local_before = {k: v for k, v in before.items() if k.startswith("local/")}
        self.assertEqual({k: v for k, v in self.digest(self.root).items() if k.startswith("local/")}, local_before)   # local untouched
        with mock.patch.object(sl, "KIT", kit), self.assertRaises(ValueError):
            sl.install("nope", root=self.root)

    def test_link_previews_skips_foreign_files_and_never_links_refused(self):
        target = Path(self.tmp.name) / "claude-skills"
        (target / "my.notes").mkdir(parents=True)                             # someone else's folder of the same name
        lines = sl.link("claude", apply=False, root=self.root, target=target)
        self.assertFalse((target / "ideation.seed").exists())                 # preview
        sl.link("claude", apply=True, root=self.root, target=target)
        self.assertTrue((target / "ideation.seed").is_symlink())
        self.assertTrue((target / "strata.verify").is_symlink())
        self.assertFalse((target / "my.notes").is_symlink())                  # left alone
        self.assertFalse((target / "no.stage").exists())                      # refused entries are not linked
        self.assertTrue(any("건너뜀 my.notes" in l for l in lines))
        self.assertIn("same ideation.seed", "\n".join(sl.link("claude", apply=False, root=self.root, target=target)))

    def test_header_shows_the_user_layer(self):
        import wizard
        with mock.patch.dict(os.environ, {"STRATA_USER_SKILLS": str(self.root)}):
            line = wizard.registry_line(KIT, KIT, "core.generic", None)
        self.assertIn("user ok(packs ideation · local 6 · overrides: strata.verify · refused 4", line)
        self.assertLess(line.index("user ok"), line.index("project"))


class CoreNextTest(unittest.TestCase):
    """docs/methodology/work-flow (DEC-2026-11-01-03): every core next: candidate names a skill the kit has (core or a
    kit pack), carries a reason in en and ko, and an area's on_proposes text has both too."""
    def test_core_next_targets_exist(self):
        import yaml
        core = yaml.safe_load((KIT / "skills" / "registry.yaml").read_text(encoding="utf-8"))["routes"]
        known = {r["skill"] for r in core}
        for reg in (KIT / "skills" / "packs").glob("*/registry.yaml"):
            known |= {r["skill"] for r in yaml.safe_load(reg.read_text(encoding="utf-8"))["routes"]}
        side = yaml.safe_load((KIT / "skills" / "next.yaml").read_text(encoding="utf-8"))["next"]
        self.assertFalse([r["skill"] for r in core if r.get("next")], "core next: lives in next.yaml (DEC-2026-11-01-15)")
        self.assertLessEqual(set(side), {r["skill"] for r in core}, "next.yaml keys are core skills")
        n = 0
        for skill, cands in side.items():
            for c in cands:
                n += 1
                self.assertIn(c["skill"], known, f"{skill} → {c['skill']}")
                self.assertTrue({"en", "ko"} <= set(c["why"]), f"{skill} → {c['skill']} why")
                if "on_proposes" in c:
                    self.assertTrue(c.get("area"), f"{skill} → {c['skill']} on_proposes without area")
                    self.assertTrue({"en", "ko"} <= set(c["on_proposes"]))
        self.assertGreaterEqual(n, 20)

    def test_next_file_beside_registry_is_read_and_later_layers_win(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a", Path(d) / "b"
            a.mkdir(); b.mkdir()
            (a / "registry.yaml").write_text("routes:\n- skill: s.one\n  triggers: {en: [x]}\n", encoding="utf-8")
            (a / "next.yaml").write_text("next:\n  s.one:\n  - {skill: s.two, why: {en: e, ko: k}}\n", encoding="utf-8")
            out = sl.next_candidates("s.one", [a / "registry.yaml"])
            self.assertIn("s.two — k", out[1])
            (b / "registry.yaml").write_text("routes: []\n", encoding="utf-8")
            (b / "next.yaml").write_text("next:\n  s.one:\n  - {skill: s.three, why: {en: e3, ko: k3}}\n", encoding="utf-8")
            out = sl.next_candidates("s.one", [a / "registry.yaml", b / "registry.yaml"])
            self.assertIn("s.three — k3", out[1]); self.assertNotIn("s.two", "".join(out))


if __name__ == "__main__":
    unittest.main()
