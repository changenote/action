"""Public responsibility boundaries and shared CLI contracts."""

from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = {"action.yml", "setup/action.yml", "prepare/action.yml", "check/action.yml",
          "manage-pr/action.yml", "inspect/action.yml", "publish/action.yml"}


def metadata(name):
    path = ROOT / name / "action.yml" if name else ROOT / "action.yml"
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class Composition(unittest.TestCase):
    def test_exactly_seven_public_actions_without_aliases(self):
        self.assertEqual({str(path.relative_to(ROOT)) for path in ROOT.rglob("action.yml")}, PUBLIC)
        for name in ("release", "select", "preview"):
            self.assertFalse((ROOT / name).exists())

    def test_all_remote_dependencies_have_full_sha_pins(self):
        for path in PUBLIC:
            for step in metadata(str(Path(path).parent) if "/" in path else "")["runs"]["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^[^@\s]+@[0-9a-f]{40}$")

    def test_root_has_only_workflow_modes_and_no_standalone_inputs(self):
        root = metadata("")
        self.assertEqual(root["inputs"]["operation"]["default"], "hooks")
        self.assertEqual(root["inputs"]["operation"]["description"],
                         "hooks manages PRs and runs trusted scripts after a managed merge; auto manages PRs and publishes pending batches on pushes. Manual runs only manage PRs.")
        self.assertNotIn("retry", root["inputs"])
        self.assertNotIn("expected-release-commit", root["inputs"])
        self.assertEqual(set(root["outputs"]), {
            "release-commit", "releases", "published", "published-packages", "publication-plan",
            "publication-needed", "ready", "has-notes", "pr-number", "pr-operation",
        })

    def test_setup_returns_same_job_cli_identity_without_project_setup(self):
        setup = metadata("setup")
        self.assertEqual(set(setup["outputs"]), {"cli-path", "version"})
        self.assertEqual(set(setup["inputs"]), {"version", "uv-version"})
        self.assertNotIn("github.token", str(setup))

    def test_each_operation_validates_a_reused_cli(self):
        for name in ("", "prepare", "manage-pr", "inspect", "publish", "check"):
            with self.subTest(action=name):
                action = metadata(name)
                self.assertEqual(action["inputs"]["cli-path"]["default"], "")
                install = next(step for step in action["runs"]["steps"]
                               if step.get("name") == "Install changenote CLI")
                self.assertEqual(install["env"]["INPUT_CLI_PATH"], "${{ inputs.cli-path }}")
                self.assertNotIn("if", install)

    def test_inspection_is_readonly_and_returns_completed_batches(self):
        inspect = metadata("inspect")
        self.assertEqual(set(inspect["outputs"]), {
            "release-commit", "releases", "ready", "publication-plan", "publication-needed",
        })
        self.assertNotIn("retry", inspect["inputs"])
        self.assertEqual(inspect["inputs"]["github-token"]["description"],
                         "Token with contents read permission.")
        self.assertTrue(inspect["runs"]["steps"][-1]["run"].endswith('/scripts/action/inspect.sh"'))

    def test_preparation_and_pr_validation_are_not_root_dispatch(self):
        for name in ("prepare", "manage-pr"):
            action = metadata(name)
            validate = action["runs"]["steps"][0]
            self.assertTrue(validate["run"].endswith(f'/scripts/action/inputs.sh" {name}'))
            self.assertNotIn("INPUT_OPERATION", validate["env"] if name == "manage-pr" else {})
        prepare = metadata("prepare")
        self.assertEqual(prepare["inputs"]["operation"]["default"], "manage-pr")
        self.assertIn("inspect", prepare["inputs"]["operation"]["description"])
        self.assertNotIn("select", prepare["inputs"]["operation"]["description"])
        self.assertEqual(set(prepare["outputs"]), {"cargo", "npm", "uv", "pr-environment-ready"})
        self.assertEqual(set(metadata("manage-pr")["outputs"]),
                         {"has-notes", "pr-number", "pr-operation"})
        for step in prepare["runs"]["steps"]:
            self.assertNotRegex(step.get("run", ""), r"(?:publish|version|lifecycle|release)\.sh")

    def test_workflow_expressions_do_not_enter_shell_source(self):
        for path in PUBLIC:
            action = yaml.load((ROOT / path).read_text(), Loader=yaml.BaseLoader)
            for step in action["runs"]["steps"]:
                if "run" in step:
                    self.assertEqual(step["shell"], "bash")
                    self.assertIsNone(re.search(r"\$\{\{", step["run"]))


if __name__ == "__main__":
    unittest.main()
