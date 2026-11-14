"""Check this repository's release setup without running release operations."""

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

    def test_only_main_pushes_and_explicit_manual_operations_are_allowed(self):
        self.assertEqual(set(self.workflow["on"]), {"push", "workflow_dispatch"})
        self.assertEqual(self.workflow["on"]["push"], {"branches": ["main"]})
        inputs = self.workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"operation"})
        self.assertEqual(inputs["operation"]["type"], "choice")
        self.assertEqual(inputs["operation"]["default"], "manage-pr")
        self.assertEqual(inputs["operation"]["options"], ["manage-pr", "retry-publication"])
        self.assertEqual(self.job["if"], "github.ref == 'refs/heads/main'")

    def test_release_has_minimal_permissions_and_serialized_runs(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(self.workflow["jobs"]), {"release"})
        self.assertEqual(self.job["runs-on"], "ubuntu-latest")
        self.assertEqual(self.job["permissions"], {
            "contents": "write", "pull-requests": "write",
        })
        self.assertEqual(self.workflow["concurrency"], {
            "group": "changenote-action-release-main", "cancel-in-progress": "false",
        })

    def test_release_uses_the_checked_out_action_without_custom_publication(self):
        checkout, action = self.job["steps"]
        self.assertRegex(checkout["uses"], r"^actions/checkout@[0-9a-f]{40}$")
        self.assertEqual(checkout["with"], {
            "ref": "${{ github.sha }}", "fetch-depth": "0", "persist-credentials": "false",
        })
        self.assertEqual(action["uses"], "./")
        self.assertEqual(action["with"], {
            "base-branch": "main", "operation": "${{ inputs.operation || 'auto' }}",
        })
        metadata = read_yaml(ROOT / action["uses"] / "action.yml")
        self.assertTrue(set(action["with"]).issubset(metadata["inputs"]))
        self.assertTrue(all("run" not in step for step in self.job["steps"]))

    def test_remote_repository_workflow_dependencies_have_full_sha_pins(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            for job in read_yaml(path)["jobs"].values():
                for step in job.get("steps", []):
                    if "uses" in step and not step["uses"].startswith("./"):
                        with self.subTest(workflow=path.name, action=step["uses"]):
                            self.assertRegex(step["uses"], r"^[^@\s]+@[0-9a-f]{40}$")

    def test_action_uses_its_own_plain_text_version_source(self):
        config = json.loads((ROOT / ".changenote/config.json").read_text())
        self.assertEqual(config["packages"], {
            "action": {"path": ".", "version_file": "VERSION"},
        })
        self.assertEqual(config["$schema"],
                         "https://raw.githubusercontent.com/changenote/changenote/main/schema.json")
        self.assertRegex((ROOT / "VERSION").read_text(), r"^[0-9]+\.[0-9]+\.[0-9]+\n$")
        self.assertFalse((ROOT / "cli-source.env").exists())

    def test_status_is_read_only_and_first_release_is_v0_0_1(self):
        cli = shutil.which("changenote")
        self.assertIsNotNone(cli, "Install the trusted CLI before running repository release tests.")

        def snapshot():
            paths = {ROOT / "VERSION", ROOT / "CHANGELOG.md"}
            paths.update((ROOT / ".changenote").glob("*"))
            return {str(path): path.read_bytes() if path.is_file() else None for path in paths}

        before = snapshot()
        result = subprocess.run([cli, "status"], cwd=ROOT, capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(snapshot(), before)
        plan = json.loads(result.stdout)
        self.assertIsInstance(plan, list)
        current = (ROOT / "VERSION").read_text().strip()
        if current == "0.0.0":
            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0]["version"], "0.0.1")
            self.assertEqual(plan[0]["bump"], "patch")
            self.assertTrue(plan[0]["notes"])
        for release in plan:
            self.assertEqual(release["package"], "action")
            self.assertEqual(release["old_version"], current)
            self.assertEqual(release["tag"], "v" + release["version"])

    def test_ci_checks_the_plan_after_installing_the_trusted_cli(self):
        steps = read_yaml(ROOT / ".github/workflows/ci.yml")["jobs"]["actions"]["steps"]
        install = next(step for step in steps if step.get("name") == "Install changenote CLI")
        check = next(step for step in steps if step.get("name") == "Check Action release plan")
        self.assertEqual(check["run"], "changenote status")
        self.assertLess(steps.index(install), steps.index(check))


if __name__ == "__main__":
    unittest.main()
