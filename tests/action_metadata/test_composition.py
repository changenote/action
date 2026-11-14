"""Public operation boundaries and shared CLI reuse contracts."""

from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def metadata(name):
    path = ROOT / name / "action.yml" if name else ROOT / "action.yml"
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


class Composition(unittest.TestCase):
    def test_all_remote_dependencies_in_public_actions_have_full_sha_pins(self):
        for path in ROOT.rglob("action.yml"):
            action = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            for step in action["runs"]["steps"]:
                if "uses" in step:
                    with self.subTest(path=path, dependency=step["uses"]):
                        self.assertRegex(step["uses"], r"^[^@\s]+@[0-9a-f]{40}$")

    def test_root_is_a_superset_with_a_nonpublishing_compatibility_default(self):
        root, release = metadata(""), metadata("release")
        self.assertTrue(set(release["inputs"]).issubset(root["inputs"]))
        self.assertEqual(set(root["outputs"]), set(release["outputs"]))
        self.assertEqual(root["inputs"]["operation"]["default"], "hooks")
        self.assertEqual(release["inputs"]["operation"]["default"], "auto")
        for action in (root, release):
            self.assertIn("release.sh", action["runs"]["steps"][-1]["run"])

    def test_setup_returns_explicit_same_job_cli_identity(self):
        setup = metadata("setup")
        self.assertEqual(set(setup["outputs"]), {"cli-path", "version"})
        self.assertEqual(set(setup["inputs"]), {"version", "uv-version"})
        self.assertNotIn("github-token", setup["inputs"])
        self.assertNotIn("github.token", str(setup))

    def test_each_operation_accepts_and_validates_a_reused_cli(self):
        for name in ("", "release", "prepare", "manage-pr", "select", "preview", "publish", "check"):
            with self.subTest(action=name):
                action = metadata(name)
                self.assertEqual(action["inputs"]["cli-path"]["default"], "")
                install = next(step for step in action["runs"]["steps"]
                               if step.get("name") == "Install changenote CLI")
                self.assertEqual(install["env"]["INPUT_CLI_PATH"], "${{ inputs.cli-path }}")
                self.assertNotIn("if", install)

    def test_select_and_preview_have_the_same_complete_batch_contract(self):
        select, preview = metadata("select"), metadata("preview")
        self.assertEqual(select["inputs"], preview["inputs"])
        self.assertEqual(set(select["outputs"]), set(preview["outputs"]))
        self.assertEqual(set(select["outputs"]), {
            "release-commit", "releases", "ready", "publication-plan", "publication-needed",
        })
        self.assertNotIn("retry", select["inputs"])
        for action in (select, preview):
            self.assertTrue(action["runs"]["steps"][-1]["run"].endswith('/scripts/action/preview.sh"'))

    def test_pr_management_and_preparation_do_not_dispatch_publication(self):
        pr, prepare = metadata("manage-pr"), metadata("prepare")
        self.assertEqual(set(pr["outputs"]), {"has-notes", "pr-number", "pr-operation"})
        self.assertTrue(pr["runs"]["steps"][-1]["run"].endswith('/scripts/action/version.sh"'))
        self.assertEqual(set(prepare["outputs"]), {"cargo", "npm", "uv", "pr-environment-ready"})
        self.assertNotIn("publish-script", prepare["inputs"])
        for step in prepare["runs"]["steps"]:
            run = step.get("run", "")
            self.assertNotRegex(run, r"(?:publish|version|lifecycle)\.sh")
            if "release.sh" in run:
                self.assertTrue(run.endswith(" validate"))

    def test_workflow_expressions_do_not_enter_shell_source(self):
        for path in ROOT.rglob("action.yml"):
            action = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            for step in action["runs"]["steps"]:
                if "run" in step:
                    with self.subTest(path=path, step=step.get("name", step.get("id"))):
                        self.assertEqual(step["shell"], "bash")
                        self.assertIsNone(re.search(r"\$\{\{", step["run"]))


if __name__ == "__main__":
    unittest.main()
