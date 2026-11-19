"""User manifest validation, modular dispatch, execution and isolation."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ftorture.cli import execute
from ftorture.projects import PROJECTS
from ftorture.projects.custom import load
from ftorture.registry import Registry, load_registry
from ftorture.runtime import Context, Options, RunnerError

ROOT = Path(__file__).resolve().parent.parent


class CustomTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="custom tests ' ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "student project"
        self.directory.mkdir()
        self.manifests = self.root / "manifests"
        self.manifests.mkdir()
        self.script = self.manifests / "test.py"
        self.script.write_text("import os, sys\nprint(os.environ['FTORTURE_SEED'])\nraise SystemExit(int(sys.argv[1]))\n")
        self.data = {"version": 1, "key": "smoke", "name": "My smoke tests",
                     "tests": [{"name": "pass", "command": ["{python}", "{tests_dir}/test.py", "0"]}]}

    def project(self):
        path = self.manifests / "smoke.json"
        path.write_text(json.dumps(self.data))
        return load(path)

    def context(self, project, **kwargs):
        return Context(self.root, project.key, Options(self.directory, seed=123, **kwargs))

    def run_project(self, project, **kwargs):
        output = io.StringIO()
        with redirect_stdout(output):
            result = execute(self.context(project, **kwargs), project)
        return result, output.getvalue()

    def test_discovery_is_data_only_namespaced_and_registry_driven(self):
        project = self.project()
        registry = load_registry(self.manifests)
        self.assertEqual(registry.find("custom-smoke"), project)
        self.assertEqual(registry.projects[:3], PROJECTS)
        self.assertIsNone(registry.detect(self.directory))
        self.assertFalse((self.root / "build").exists())
        with self.assertRaisesRegex(RunnerError, "Duplicate"):
            Registry((project, project))

    def test_default_xdg_discovery(self):
        path = self.root / "config/ftorture/tests"
        path.mkdir(parents=True)
        (path / "smoke.json").write_text(json.dumps(self.data))
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config")}):
            self.assertIsNotNone(load_registry().find("custom-smoke"))

    def test_manifest_validation_rejects_unsafe_or_ambiguous_data(self):
        variants = [
            {"version": True}, {"key": "../escape"}, {"header": "../outside.h"},
            {"tests": []}, {"timeout": 0}, {"unknown": "typo"},
            {"tests": [{"name": "one", "command": "echo unsafe"}]},
            {"tests": [{"name": "one", "command": ["{directory.__class__}"]}]},
            {"tests": [{"name": "one", "command": ["{unknown}"]}]},
            {"tests": [{"name": "one", "command": ["echo"], "expected_exit": False}]},
            {"tests": [{"name": "one", "command": ["echo"], "speculative": "false"}]},
            {"tests": [self.data["tests"][0], self.data["tests"][0]]},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                path = self.manifests / "invalid.json"
                path.write_text(json.dumps({**self.data, **variant}))
                with self.assertRaises(RunnerError):
                    load(path)

    def test_pass_failure_expected_exit_and_plain_report_without_compiler(self):
        self.data["tests"].extend([
            {"name": "expected", "command": ["{python}", "{tests_dir}/test.py", "7"], "expected_exit": 7},
            {"name": "broken", "command": ["{python}", "{tests_dir}/test.py", "1"]}])
        project = self.project()
        with patch.dict(os.environ, {"CC": ""}):
            status, output = self.run_project(project, verbose=True)
        self.assertEqual(status, 1)
        self.assertIn("✔ [CUSTOM] pass", output)
        self.assertIn("✔ [CUSTOM] expected", output)
        self.assertIn("✘ [CUSTOM] broken", output)
        self.assertIn("123", output)
        report = (self.root / "ftorture.log").read_text()
        self.assertIn("2 OK · 1 KO", report)
        self.assertNotIn("\033", report)

    def test_filters_parts_and_speculative_verdicts(self):
        self.data["tests"].append({"name": "warning", "part": 2, "speculative": True,
                                  "command": ["{python}", "{tests_dir}/test.py", "1"]})
        project = self.project()
        self.assertEqual(self.run_project(project, part=1)[0], 0)
        self.assertEqual(self.run_project(project, functions="warning")[0], 0)
        self.assertEqual(self.run_project(project, functions="warning", speculative=True)[0], 1)
        with self.assertRaises(RunnerError):
            self.run_project(project, functions="missing")
        with self.assertRaises(RunnerError):
            self.run_project(project, part=3)

    def test_build_and_cleanup_even_on_build_error(self):
        helper = self.manifests / "helper.py"
        helper.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[1]).touch()\nraise SystemExit(int(sys.argv[2]))\n")
        self.data["build"] = [["{python}", "{tests_dir}/helper.py", "{build}/built", "1"]]
        self.data["cleanup"] = [["{python}", "{tests_dir}/helper.py", "{build}/cleaned", "0"]]
        project = self.project()
        with self.assertRaisesRegex(RunnerError, "build failed"):
            self.run_project(project)
        self.assertTrue((self.root / "build/custom-smoke/cleaned").exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_timeout_is_failure_and_cleanup_runs(self):
        sleeper = self.manifests / "sleep.py"
        sleeper.write_text("import time\ntime.sleep(30)\n")
        self.data["tests"] = [{"name": "slow", "command": ["{python}", "{tests_dir}/sleep.py"]}]
        self.data["timeout"] = 1
        project = self.project()
        status, output = self.run_project(project)
        self.assertEqual(status, 1)
        self.assertIn("T [CUSTOM] slow", output)

    def test_cli_listing_and_execution(self):
        self.project()
        args = [sys.executable, str(ROOT / "torture.py"), "--custom-tests-dir", str(self.manifests)]
        result = subprocess.run([*args, "--list-projects"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("custom-smoke", result.stdout)
        self.assertIn("[CUSTOM]", result.stdout)
        result = subprocess.run([*args, "custom-smoke", str(self.directory), "--no-color"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("✔ [CUSTOM] pass", result.stdout)
