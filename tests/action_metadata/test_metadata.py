"""Check Action YAML and execute composite commands in a consumer fixture."""

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
            if "uses" not in step:
                continue
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

    def test_dependabot_only_tracks_action_dependencies(self):
        updates = read_yaml(ROOT / ".github/dependabot.yml")["updates"]
        self.assertEqual([update["package-ecosystem"] for update in updates], ["github-actions"])
        self.assertGreaterEqual(int(updates[0]["cooldown"]["default-days"]), 7)

    def test_all_public_actions_install_the_requested_cli_before_use(self):
        for path, operation in (("action.yml", "version"), ("release/action.yml", "release"),
                                ("check/action.yml", "check"), ("preview/action.yml", "preview"),
                                ("publish/action.yml", "publish")):
            with self.subTest(action=path):
                metadata = read_yaml(ROOT / path)
                self.assertEqual(metadata["inputs"]["version"]["default"], "latest")
                steps = metadata["runs"]["steps"]
                install = next(step for step in steps if step.get("name") == "Install changenote CLI")
                self.assertEqual(install["env"]["INPUT_VERSION"], "${{ inputs.version }}")
                self.assertEqual(install["shell"], "bash")
                self.assertNotIn("${{", install["run"])
                self.assertNotIn("GH_TOKEN", install["env"])
                self.assertNotIn("GITHUB_TOKEN", install["env"])
                prefix = "" if path == "action.yml" else "../"
                self.assertEqual(install["run"], f'bash "$ACTION_PATH/{prefix}scripts/action/install-cli.sh"')
                run = next(step for step in steps if step.get("id") == operation)
                uv = next(step for step in steps if step.get("uses", "").startswith("astral-sh/setup-uv@"))
                self.assertRegex(uv["uses"], r"^astral-sh/setup-uv@[0-9a-f]{40}$")
                self.assertNotIn("if", uv)
                self.assertLess(steps.index(uv), steps.index(install))
                self.assertLess(steps.index(install), steps.index(run))
                if path != "release/action.yml":
                    self.assertFalse(any(step.get("uses", "").startswith("dtolnay/") for step in steps))

    def test_inputs_outputs_and_composite_paths(self):
        fixture = test_actions.Actions("test_no_batch")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for action, step, expected in (
            (
                ROOT / "action.yml",
                "version",
                {"has-notes", "pr-number", "pr-operation", "release-commit", "releases"},
            ),
            (
                ROOT / "publish/action.yml",
                "publish",
                {"release-commit", "releases", "published", "published-packages"},
            ),
            (
                ROOT / "preview/action.yml",
                "preview",
                {"release-commit", "releases", "ready", "publication-plan"},
            ),
        ):
            metadata = read_yaml(action)
            self.assertEqual(metadata["runs"]["using"], "composite")
            self.assertEqual(set(metadata["outputs"]), expected)
            self.assertEqual(
                metadata["inputs"]["github-token"]["default"], "${{ github.token }}"
            )
            self.assertEqual(metadata["inputs"]["base-branch"]["default"], "")
            if step == "publish":
                self.assertEqual(metadata["inputs"]["expected-release-commit"]["default"], "")
                self.assertEqual(
                    next(item for item in metadata["runs"]["steps"] if item.get("id") == "publish")["env"]["INPUT_EXPECTED_RELEASE_COMMIT"],
                    "${{ inputs.expected-release-commit }}",
                )
                self.assertNotIn("${{", next(item for item in metadata["runs"]["steps"] if item.get("id") == "publish")["run"])
                fixture.env["INPUT_EXPECTED_RELEASE_COMMIT"] = ""
            run = next(item for item in metadata["runs"]["steps"] if item.get("id") == step)
            self.assertEqual(run["id"], step)
            self.assertEqual(run["shell"], "bash")
            self.assertEqual(run["env"]["ACTION_PATH"], "${{ github.action_path }}")
            token_key = "INPUT_GITHUB_TOKEN" if step == "version" else "GH_TOKEN"
            self.assertEqual(run["env"][token_key], "${{ inputs.github-token }}")
            if step == "version":
                fixture.env["INPUT_GITHUB_TOKEN"] = "test-token"
                event = fixture.top / "root-event.json"
                event.write_text("{}")
                fixture.env.update(GITHUB_EVENT_NAME="workflow_dispatch",
                                   GITHUB_REF="refs/heads/main", GITHUB_EVENT_PATH=str(event))
            for key, value in metadata["outputs"].items():
                self.assertEqual(
                    value["value"], "${{ steps." + step + ".outputs." + key + " }}"
                )
            fixture.env["ACTION_PATH"] = str(action.parent)
            output = fixture.top / "metadata-output"
            output.write_text("")
            fixture.env["GITHUB_OUTPUT"] = str(output)
            fixture.run_cmd(["bash", "-c", run["run"]])
            actual = dict(
                line.split("=", 1) for line in output.read_text().splitlines()
            )
            self.assertEqual(set(actual), expected)
            if step in ("preview", "publish"):
                self.assertEqual(actual["releases"], "[]")
            if step == "preview":
                self.assertEqual(actual["ready"], "true")
                self.assertEqual(actual["release-commit"], "")
                self.assertEqual(actual["publication-plan"], "[]")
                self.assertEqual(
                    metadata["inputs"]["github-token"]["description"],
                    "Token with contents read permission.",
                )
            self.assertFalse((fixture.repo / "scripts/action").exists())

    def test_documented_examples_and_contracts(self):
        guide = "\n".join(
            (ROOT / path).read_text()
            for path in ("docs/checks.md", "docs/github-actions-reference.md")
        )
        blocks = re.findall(r"```yaml\n(.*?)```", guide, re.DOTALL)
        examples = [yaml.load(block, Loader=yaml.BaseLoader) for block in blocks]
        workflow = next(example for example in examples if "jobs" in example)
        check = next(example for example in examples if "steps" in example)
        self.assertEqual(check["permissions"], {"contents": "read"})
        self.assertEqual(check["steps"][0]["with"]["fetch-depth"], "0")
        self.assertEqual(check["steps"][0]["with"]["persist-credentials"], "false")
        self.assertEqual(
            check["steps"][-1]["env"]["BASE_BRANCH"], "${{ github.base_ref }}"
        )
        self.assertEqual(
            check["steps"][-1]["run"],
            'changenote check --since "refs/remotes/origin/$BASE_BRANCH"',
        )
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(
            workflow["jobs"]["release"]["permissions"],
            {"contents": "write", "pull-requests": "write"},
        )
        self.assertEqual(
            workflow["jobs"]["publish"]["permissions"], {"contents": "write"}
        )
        self.assertEqual(
            workflow["jobs"]["release"]["steps"][-1]["uses"],
            "changenote/action@<full-action-commit-sha>",
        )
        self.assertEqual(
            workflow["jobs"]["publish"]["steps"][-1]["uses"],
            "changenote/action/publish@<full-action-commit-sha>",
        )
        preview = next(
            example
            for example in examples
            if example.get("name") == "Publication preview"
        )
        self.assertEqual(preview["permissions"], {"contents": "read"})
        self.assertEqual(
            preview["jobs"]["preview"]["steps"][-1]["uses"],
            "changenote/action/preview@<full-action-commit-sha>",
        )
        for path in (
            ROOT / "action.yml",
            ROOT / "publish/action.yml",
            ROOT / "preview/action.yml",
        ):
            action = read_yaml(path)
            for key in (*action["inputs"], *action["outputs"]):
                self.assertIn("`" + key + "`", guide)


if __name__ == "__main__":
    unittest.main()
