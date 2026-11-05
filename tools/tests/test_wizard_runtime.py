"""The wizard's runtime environment step (MB-strata-kit-2026-058): diagnose measures the python of each execution
path and its kit dependencies, recommend presents the options with a default and records the person's answer (and
the other interview answers) with reasons, generate writes one STRATA_PYTHON into snippet files — never home files —
and doctor reports per-path mismatches and missing dependencies."""
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KIT / "tools")); sys.path.insert(0, str(KIT))

import doctor  # noqa: E402
import runtime_env  # noqa: E402
import wizard  # noqa: E402

CORE_VERSION = yaml.safe_load((KIT / "core" / "constitution" / "constitution.yaml").read_text(encoding="utf-8"))["constitution"]["version"]


def fake_python(path: Path, modules: dict, version: str = "3.12.0"):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"version": version, "executable": str(path), "modules": modules})
    path.write_text(f"#!/bin/sh\necho '{payload}'\n")
    path.chmod(0o755)
    return str(path)


class RuntimeDetectTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.home, self.project, self.kit = self.root / "home", self.root / "proj", self.root / "kit"
        for d in (self.home, self.project, self.kit):
            d.mkdir()
        full = {m: True for m in runtime_env.REQUIRED + runtime_env.OPTIONAL}
        self.good = fake_python(self.root / "good" / "python3", full)
        self.bare = fake_python(self.root / "bare" / "python3", {"yaml": False})
        self.venv = fake_python(self.kit / ".venv" / "bin" / "python", full)
        (self.home / ".tool-versions").write_text("python 3.12.0\nuv 0.11.8\n")
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "settings.json").write_text(json.dumps({"env": {"STRATA_PYTHON": self.good}}))
        self.plist = self.home / "Library" / "LaunchAgents" / "com.t.strata-librarian.plist"
        self.plist.parent.mkdir(parents=True)
        with self.plist.open("wb") as fh:
            plistlib.dump({"EnvironmentVariables": {"STRATA_PYTHON": self.bare}}, fh)
        self.env = {"HOME": str(self.home), "USER": "t", "PATH": str(self.root / "good")}

    def tearDown(self):
        self.tmp.cleanup()

    def detect(self):
        return runtime_env.detect(self.project, self.kit, home=self.home, env=self.env, plist=self.plist)

    def test_paths_sources_and_missing_deps(self):
        rt = self.detect()
        p = rt["paths"]
        self.assertEqual(p["interactive_shell"]["python"], self.good)
        self.assertIn("settings.json", p["claude_hooks"]["source"])
        self.assertEqual(p["mcp"]["python"], self.venv)
        self.assertEqual((p["launchd"]["python"], p["launchd"]["missing"]), (self.bare, ["yaml"]))
        self.assertIn("~/.zshenv", p["non_interactive_sh"]["source"])
        self.assertEqual([v["python"] for v in rt["version_files"]], ["3.12.0"])
        f = runtime_env.findings(rt)
        self.assertTrue(any(l.startswith("launchd:") and "yaml" in l for l in f), f)
        self.assertTrue(any("python 이 다름" in l for l in f), f)

    def test_zshenv_export_is_read(self):
        (self.home / ".zshenv").write_text(f'export STRATA_PYTHON="{self.good}"\n')
        self.assertEqual(self.detect()["paths"]["non_interactive_sh"]["python"], self.good)

    def test_layers_advice_separates_language_runtimes_from_the_kit_env(self):
        # asdf already keeps the languages and uv: advise asdf for languages and uv, uv venv for the kit
        adv = runtime_env.layers_advice({"asdf": True, "uv": True, "brew": True},
                                        [{"file": "/h/.tool-versions", "python": "3.12.0", "uv": True}], "ko")
        by = {x["layer"]: x for x in adv["layers"]}
        self.assertEqual(by["languages"]["tool"], "asdf")
        self.assertEqual(by["uv"]["tool"], "asdf")
        self.assertIn("이미", by["uv"]["why"])
        self.assertEqual(by["kit"]["tool"], "uv-venv")
        self.assertTrue(adv["asdf_python_fits_when"])
        # no language manager: uv comes from its own installer, the kit still in a uv venv
        adv = runtime_env.layers_advice({"system": True}, [], "en")
        by = {x["layer"]: x for x in adv["layers"]}
        self.assertEqual(by["uv"]["tool"], "uv installer")
        self.assertEqual(by["kit"]["tool"], "uv-venv")
        self.assertIsNone(by.get("languages"))

    def test_python_for_choices_are_absolute_not_shims(self):
        rt = self.detect()
        self.assertEqual(runtime_env.python_for("uv-venv", self.kit, rt, self.home), str(self.kit / ".venv" / "bin" / "python"))
        self.assertEqual(runtime_env.python_for("asdf", self.kit, rt, self.home), str(self.home / ".asdf" / "installs" / "python" / "3.12.0" / "bin" / "python3"))
        with self.assertRaises(ValueError):
            runtime_env.python_for("pyenv", self.kit, rt, self.home)
        with self.assertRaises(ValueError):
            runtime_env.python_for("conda", self.kit, rt, self.home)

    def test_doctor_reports_runtime_as_machine_items(self):
        items = doctor.check_runtime(self.project, rt=self.detect())
        self.assertTrue(items and all(i.machine and i.check == "runtime" for i in items))
        self.assertTrue(any("launchd" in i.message for i in items))


class WizardRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / "demo"
        (self.project / ".strata" / "kit").mkdir(parents=True)
        self.env = {**os.environ, "STRATA_USER_CONFIG": str(self.root / "none.yaml")}
        self.env.pop("STRATA_VAULT", None)

    def tearDown(self):
        self.tmp.cleanup()

    def wiz(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(KIT / "tools" / "wizard.py"), *args], capture_output=True, text=True, env=self.env)
        if ok:
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def test_diagnose_lists_runtime_question_and_findings(self):
        d = wizard.diagnose(self.project, KIT)
        self.assertIn("runtime", [q["key"] for q in d["open_questions"]])
        self.assertIn("paths", d["runtime"])

    def test_recommend_without_answer_shows_options_and_default(self):
        r = self.wiz("recommend", str(self.project), "--profile", "core.generic", "--locale", "ko")
        self.assertIn("runtime", r.stdout)
        self.assertIn("uv-venv", r.stdout)
        self.assertIn("asdf", r.stdout)
        p = wizard.recommend(self.project, KIT, "core.generic", {}, "ko", "work")
        self.assertEqual(p["runtime"]["default"], "uv-venv")
        self.assertIsNone(p["runtime"]["choice"])
        self.assertEqual(set(p["runtime"]["options"]), set(runtime_env.OPTIONS))
        self.assertEqual([x["layer"] for x in p["runtime"]["layers"]][-1], "kit")
        self.assertIn("kit 실행 환경", r.stdout)

    def test_answers_are_stored_with_reasons_and_carried(self):
        self.wiz("recommend", str(self.project), "--profile", "core.generic", "--apply",
                 "--answer", "runtime=uv-venv", "--because", "runtime=재현 가능", "--answer", "team_size=3",
                 "--answer", "shared_envs=dev,stage,prod", "--because", "shared_envs=배포 런북")
        p = yaml.safe_load((self.project / ".strata" / "kit" / "proposal.yaml").read_text())
        self.assertEqual(p["answers"]["runtime"], {"value": "uv-venv", "reason": "재현 가능"})
        self.assertEqual(p["answers"]["team_size"]["value"], "3")
        self.assertEqual(p["answers"]["shared_envs"]["reason"], "배포 런북")
        self.assertEqual(os.path.expanduser(p["runtime"]["strata_python"]), str(KIT / ".venv" / "bin" / "python"))
        self.assertIn(".strata/kit/runtime/env.sh", p["write_paths"])
        # the next recommend keeps the answers it is not given again
        p2 = wizard.recommend(self.project, KIT, "core.generic", {}, "ko", "work")
        self.assertEqual(p2["answers"]["team_size"]["value"], "3")
        self.assertEqual(p2["runtime"]["choice"], "uv-venv")

    def test_unknown_answer_key_and_choice_are_refused(self):
        r = self.wiz("recommend", str(self.project), "--profile", "core.generic", "--answer", "colour=blue", ok=False)
        self.assertNotEqual(r.returncode, 0)
        r = self.wiz("recommend", str(self.project), "--profile", "core.generic", "--answer", "runtime=conda", ok=False)
        self.assertNotEqual(r.returncode, 0)

    def test_generate_writes_one_strata_python_into_snippets_only(self):
        py = "/opt/py/bin/python3"
        prop = wizard.recommend(self.project, KIT, "core.generic", {}, "ko", "personal",
                                interview={"runtime": {"value": "system", "reason": "x"}, "strata_python": {"value": py, "reason": "x"}})
        prop["approved"] = True
        (self.project / ".strata" / "kit" / "proposal.yaml").write_text(yaml.safe_dump(prop, allow_unicode=True))
        home_before = sorted(p.name for p in Path.home().iterdir())
        out = wizard.generate(self.project, KIT, apply=True)
        rdir = self.project / ".strata" / "kit" / "runtime"
        self.assertTrue(any("runtime/env.sh" in l for l in out), out)
        self.assertIn(f'export STRATA_PYTHON="{py}"', (rdir / "env.sh").read_text())
        self.assertEqual(json.loads((rdir / "claude-settings.json").read_text())["env"]["STRATA_PYTHON"], py)
        hook = json.loads((rdir / "claude-settings.json").read_text())["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        self.assertTrue(hook.startswith('"$STRATA_PYTHON" '), hook)
        self.assertEqual(json.loads((rdir / "mcp.json").read_text())["mcpServers"]["knowledge-base"]["command"], py)
        self.assertIn(f"<string>{py}</string>", (rdir / "launchd-environment.plist.xml").read_text())
        self.assertTrue((rdir / "README.ko.md").is_file())
        reg = yaml.safe_load((self.project / ".strata" / "kit" / "registry.yaml").read_text())
        self.assertEqual(reg["runtime"]["strata_python"], py)
        self.assertEqual(sorted(p.name for p in Path.home().iterdir()), home_before)


if __name__ == "__main__":
    unittest.main()
