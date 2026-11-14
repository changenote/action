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

    def test_root_has_no_modes_or_standalone_inputs(self):
        root = metadata("")
        self.assertNotIn("operation", root["inputs"])
        for key in ("mode", "scope", "environment-operation"):
            self.assertNotIn(key, root["inputs"])
        for key in ("create-github-releases", "push-git-tags"):
            self.assertEqual(root["inputs"][key]["default"], "false")
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

    def test_each_public_action_has_a_linked_readme(self):
        overview = (ROOT / "README.md").read_text()
        for path in PUBLIC:
            with self.subTest(action=path):
                readme = Path(path).with_name("README.md")
                text = (ROOT / readme).read_text()
                self.assertIn("[action.yml](action.yml)", text)
                prefix = "../" if readme.parent != Path(".") else ""
                self.assertIn(f"]({prefix}docs/", text)
                self.assertIn(f"]({prefix}LICENSE)", text)
                if prefix:
                    self.assertIn(f"]({readme.as_posix()})", overview)

    def test_readme_workflows_use_pinned_public_interfaces(self):
        for path in PUBLIC:
            readme = Path(path).with_name("README.md")
            blocks = re.findall(r"```yaml\n(.*?)```", (ROOT / readme).read_text(), re.DOTALL)
            self.assertTrue(blocks, readme)
            for block in blocks:
                workflow = yaml.load(block, Loader=yaml.BaseLoader)
                jobs = workflow.get("jobs", {"example": workflow})
                for job in jobs.values():
                    for step in job.get("steps", []):
                        if "uses" not in step:
                            continue
                        with self.subTest(readme=readme, uses=step["uses"]):
                            self.assertRegex(step["uses"],
                                             r"^[^@\s]+@([0-9a-f]{40}|<full-(action|checkout)-commit-sha>)$")
                            name = step["uses"].split("@", 1)[0]
                            if name != "changenote/action" and not name.startswith("changenote/action/"):
                                continue
                            directory = name.removeprefix("changenote/action").lstrip("/")
                            action_path = str(Path(directory) / "action.yml")
                            self.assertIn(action_path, PUBLIC)
                            inputs = metadata(directory)["inputs"]
                            supplied = step.get("with", {})
                            self.assertLessEqual(set(supplied), set(inputs))
                            for key, spec in inputs.items():
                                if spec.get("required") == "true" and "default" not in spec:
                                    self.assertIn(key, supplied)

    def test_workflow_expressions_do_not_enter_shell_source(self):
        for path in PUBLIC:
            action = yaml.load((ROOT / path).read_text(), Loader=yaml.BaseLoader)
            for step in action["runs"]["steps"]:
                if "run" in step:
                    self.assertEqual(step["shell"], "bash")
                    self.assertIsNone(re.search(r"\$\{\{", step["run"]))


if __name__ == "__main__":
    unittest.main()
