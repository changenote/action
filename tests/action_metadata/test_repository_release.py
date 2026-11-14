"""Repository release policy without hosted release operations."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def read_yaml(path):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class RepositoryRelease(unittest.TestCase):
    def setUp(self):
        self.workflow = read_yaml(ROOT / ".github/workflows/release.yml")
        self.job = self.workflow["jobs"]["release"]

    def test_only_main_pushes_and_explicit_manual_choices_are_allowed(self):
        self.assertEqual(set(self.workflow["on"]), {"push", "workflow_dispatch"})
        self.assertEqual(self.workflow["on"]["push"], {"branches": ["main"]})
        choice = self.workflow["on"]["workflow_dispatch"]["inputs"]["operation"]
        self.assertEqual(choice["default"], "manage-pr")
        self.assertEqual(choice["options"], ["manage-pr", "retry-publication"])
        self.assertEqual(self.job["if"], "github.ref == 'refs/heads/main'")

    def test_permissions_and_serialized_runs_are_preserved(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(self.workflow["jobs"]), {"release"})
        self.assertEqual(self.job["permissions"], {"contents": "write", "pull-requests": "write"})
        self.assertEqual(self.workflow["concurrency"], {
            "group": "changenote-action-release-main", "cancel-in-progress": "false",
        })

    def test_local_actions_use_exact_event_checkout_and_known_inputs(self):
        checkout = self.job["steps"][0]
        self.assertRegex(checkout["uses"], r"^actions/checkout@[0-9a-f]{40}$")
        self.assertEqual(checkout["with"], {
            "ref": "${{ github.sha }}", "fetch-depth": "0", "persist-credentials": "false",
        })
        actions = {step["uses"]: step for step in self.job["steps"][1:]}
        self.assertEqual(set(actions), {"./", "./setup", "./prepare", "./manage-pr", "./inspect", "./publish"})
        for name, step in actions.items():
            metadata = read_yaml(ROOT / name / "action.yml")
            self.assertTrue(set(step.get("with", {})).issubset(metadata["inputs"]))
            self.assertNotIn("run", step)
        self.assertEqual(actions["./"]["with"], {"base-branch": "main", "operation": "auto"})
        self.assertEqual(actions["./"]["if"], "github.event_name == 'push'")
        for name in ("setup", "prepare", "manage-pr", "inspect", "publish"):
            self.assertIn("github.event_name == 'workflow_dispatch'", actions["./" + name]["if"])
        self.assertIn("inputs.operation == 'manage-pr'", actions["./manage-pr"]["if"])
        self.assertIn("inputs.operation == 'retry-publication'", actions["./publish"]["if"])
        self.assertIn("steps.inspect.outputs.release-commit != ''", actions["./publish"]["if"])
        self.assertEqual(actions["./publish"]["with"]["expected-release-commit"],
                         "${{ steps.inspect.outputs.release-commit }}")
        self.assertEqual(actions["./prepare"]["with"]["operation"],
                         "${{ inputs.operation == 'manage-pr' && 'manage-pr' || 'inspect' }}")

    def test_remote_dependencies_have_full_sha_pins(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            for job in read_yaml(path)["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" in step and not step["uses"].startswith("./"):
                        self.assertRegex(step["uses"], r"^[^@\s]+@[0-9a-f]{40}$")

    def test_action_has_an_independent_plain_text_version_source(self):
        config = json.loads((ROOT / ".changenote/config.json").read_text())
        self.assertEqual(config["packages"], {"action": {"path": ".", "version_file": "VERSION"}})
        self.assertEqual(config["$schema"], "https://raw.githubusercontent.com/changenote/changenote/main/schema.json")
        self.assertRegex((ROOT / "VERSION").read_text(), r"^[0-9]+\.[0-9]+\.[0-9]+\n$")
        self.assertFalse((ROOT / "cli-source.env").exists())

    def test_status_is_readonly_and_uses_the_action_version(self):
        cli = shutil.which("changenote")
        self.assertIsNotNone(cli)
        paths = [ROOT / "VERSION", ROOT / "CHANGELOG.md", *list((ROOT / ".changenote").glob("*"))]
        before = {str(p): p.read_bytes() for p in paths if p.is_file()}
        result = subprocess.run([cli, "status"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({str(p): p.read_bytes() for p in paths if p.is_file()}, before)
        for release in json.loads(result.stdout):
            self.assertEqual(release["package"], "action")
            self.assertEqual(release["old_version"], (ROOT / "VERSION").read_text().strip())
            self.assertEqual(release["tag"], "v" + release["version"])

    def test_ci_checks_the_plan_after_installing_the_cli(self):
        steps = read_yaml(ROOT / ".github/workflows/ci.yml")["jobs"]["actions"]["steps"]
        install = next(step for step in steps if step.get("name") == "Install changenote CLI")
        check = next(step for step in steps if step.get("name") == "Check Action release plan")
        self.assertEqual(check["run"], "changenote status")
        self.assertLess(steps.index(install), steps.index(check))


if __name__ == "__main__":
    unittest.main()
