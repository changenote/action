"""Public metadata, CLI ordering, and operation commands in a consumer fixture."""

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/actions"))
import test_actions  # noqa: E402


def read_yaml(path):
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class Metadata(unittest.TestCase):
    def test_ci_uses_pinned_actions_and_installs_the_trusted_cli(self):
        workflow = read_yaml(ROOT / ".github/workflows/ci.yml")
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"actions"})
        steps = workflow["jobs"]["actions"]["steps"]
        for step in steps:
            if "uses" in step:
                self.assertRegex(step["uses"], r"^[^@]+@[0-9a-f]{40}$")
                if step["uses"].startswith("actions/checkout@"):
                    self.assertEqual(step["with"]["persist-credentials"], "false")
        install = next(step for step in steps if step.get("name") == "Install changenote CLI")
        self.assertEqual(install["env"], {"INPUT_VERSION": "latest"})
        self.assertEqual(install["run"], "bash scripts/action/install-cli.sh")
        for suite in ("actions", "action_metadata"):
            test = next(step for step in steps if f"-s tests/{suite} -v" in step.get("run", ""))
            self.assertLess(steps.index(install), steps.index(test))
        self.assertNotIn("cargo build", str(steps))
        self.assertNotIn("-ignore", str(steps))

    def test_dependabot_only_tracks_actions_with_a_cooldown(self):
        updates = read_yaml(ROOT / ".github/dependabot.yml")["updates"]
        self.assertEqual([update["package-ecosystem"] for update in updates], ["github-actions"])
        self.assertEqual(updates[0]["directory"], "/")
        self.assertEqual(updates[0]["schedule"]["interval"], "weekly")
        self.assertEqual(updates[0]["cooldown"]["default-days"], "7")

    def test_all_public_actions_install_or_validate_the_cli_before_use(self):
        for name, operation in (("", "version"), ("setup", "install"), ("prepare", "warm"),
                                ("check", "check"), ("manage-pr", "version"),
                                ("inspect", "inspect"), ("publish", "publish")):
            with self.subTest(action=name):
                path = ROOT / name / "action.yml"
                metadata = read_yaml(path)
                self.assertEqual(metadata["runs"]["using"], "composite")
                self.assertEqual(metadata["inputs"]["version"]["default"], "latest")
                steps = metadata["runs"]["steps"]
                install = next(step for step in steps if step.get("name") == "Install changenote CLI")
                self.assertEqual(install["env"]["INPUT_VERSION"], "${{ inputs.version }}")
                self.assertNotIn("GH_TOKEN", install["env"])
                self.assertNotIn("GITHUB_TOKEN", install["env"])
                prefix = "../" if name else ""
                self.assertEqual(install["run"], f'bash "$ACTION_PATH/{prefix}scripts/action/install-cli.sh"')
                uv = next(step for step in steps if step.get("uses", "").startswith("astral-sh/setup-uv@"))
                self.assertLess(steps.index(uv), steps.index(install))
                run = next(step for step in steps if step.get("id") == operation)
                self.assertLessEqual(steps.index(install), steps.index(run))
                if name in ("check", "manage-pr", "inspect", "publish"):
                    self.assertEqual(uv["if"], "inputs.cli-path == ''")
                    self.assertFalse(any(s.get("uses", "").startswith("dtolnay/") for s in steps))

    def test_outputs_and_operation_paths_from_a_consumer_checkout(self):
        fixture = test_actions.Actions("test_no_batch")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for name, step, expected in (
            ("", "version", {"has-notes", "pr-number", "pr-operation", "release-commit", "releases",
                             "published", "published-packages", "publication-plan", "publication-needed", "ready"}),
            ("manage-pr", "version", {"has-notes", "pr-number", "pr-operation"}),
            ("inspect", "inspect", {"release-commit", "releases", "ready", "publication-plan", "publication-needed"}),
            ("publish", "publish", {"release-commit", "releases", "published", "published-packages"}),
        ):
            with self.subTest(action=name):
                metadata = read_yaml(ROOT / name / "action.yml")
                self.assertEqual(set(metadata["outputs"]), expected)
                self.assertEqual(metadata["inputs"]["github-token"]["default"], "${{ github.token }}")
                self.assertEqual(metadata["inputs"]["base-branch"]["default"], "")
                if name == "publish":
                    self.assertEqual(metadata["inputs"]["expected-release-commit"]["default"], "")
                run = next(item for item in metadata["runs"]["steps"] if item.get("id") == step)
                self.assertNotIn("${{", run["run"])
                self.assertEqual(run["env"]["ACTION_PATH"], "${{ github.action_path }}")
                token = "GH_TOKEN" if name else "INPUT_GITHUB_TOKEN"
                self.assertEqual(run["env"][token], "${{ inputs.github-token }}")
                if not name:
                    event = fixture.top / "event.json"
                    event.write_text("{}")
                    fixture.env.update(INPUT_GITHUB_TOKEN="test-token", GITHUB_EVENT_NAME="workflow_dispatch",
                                       GITHUB_REF="refs/heads/main", GITHUB_EVENT_PATH=str(event))
                if name == "publish":
                    fixture.env["INPUT_EXPECTED_RELEASE_COMMIT"] = ""
                fixture.env["ACTION_PATH"] = str(ROOT / name)
                output = fixture.top / "metadata-output"
                output.write_text("")
                fixture.env["GITHUB_OUTPUT"] = str(output)
                fixture.run_cmd(["bash", "-c", run["run"]])
                actual = dict(line.split("=", 1) for line in output.read_text().splitlines())
                self.assertEqual(set(actual), expected)
                for key, value in metadata["outputs"].items():
                    self.assertEqual(value["value"], "${{ steps." + step + ".outputs." + key + " }}")
                if name == "inspect":
                    self.assertEqual(actual["ready"], "true")
                    self.assertEqual(actual["release-commit"], "")
                    self.assertEqual(actual["publication-plan"], "[]")
                self.assertFalse((fixture.repo / "scripts/action").exists())

    def test_documented_examples_and_contracts(self):
        guide = "\n".join((ROOT / path).read_text() for path in (
            "docs/checks.md", "docs/github-actions-reference.md", "docs/github-actions.md"))
        examples = [yaml.load(block, Loader=yaml.BaseLoader)
                    for block in re.findall(r"```yaml\n(.*?)```", guide, re.DOTALL)]
        workflow = next(example for example in examples if "jobs" in example)
        check = next(example for example in examples if "steps" in example)
        self.assertEqual(check["permissions"], {"contents": "read"})
        self.assertEqual(check["steps"][0]["with"]["fetch-depth"], "0")
        self.assertEqual(check["steps"][0]["with"]["persist-credentials"], "false")
        self.assertEqual(check["steps"][-1]["env"]["BASE_BRANCH"], "${{ github.base_ref }}")
        self.assertEqual(check["steps"][-1]["run"], 'changenote check --since "refs/remotes/origin/$BASE_BRANCH"')
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(workflow["jobs"]["release"]["permissions"],
                         {"contents": "write", "pull-requests": "write"})
        self.assertEqual(workflow["jobs"]["release"]["steps"][-1]["uses"],
                         "changenote/action/manage-pr@<full-action-commit-sha>")
        self.assertEqual(workflow["jobs"]["publish"]["permissions"], {"contents": "write"})
        self.assertEqual(workflow["jobs"]["publish"]["steps"][-1]["uses"],
                         "changenote/action/publish@<full-action-commit-sha>")
        inspection = next(example for example in examples if example.get("name") == "Publication inspection")
        self.assertEqual(inspection["permissions"], {"contents": "read"})
        self.assertEqual(inspection["jobs"]["inspect"]["steps"][-1]["uses"],
                         "changenote/action/inspect@<full-action-commit-sha>")
        for name in ("", "inspect", "publish"):
            action = read_yaml(ROOT / name / "action.yml")
            for key in (*action["inputs"], *action["outputs"]):
                self.assertIn("`" + key + "`", guide)


if __name__ == "__main__":
    unittest.main()
