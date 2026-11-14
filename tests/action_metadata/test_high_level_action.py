"""Root setup, mode selection, and environment-scope boundaries."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class RootMetadata(unittest.TestCase):
    def setUp(self):
        self.action = yaml.load((ROOT / "action.yml").read_text(), Loader=yaml.BaseLoader)
        self.steps = self.action["runs"]["steps"]

    def step(self, name):
        return next(step for step in self.steps if step.get("name") == name)

    def test_defaults_and_output_forwarding(self):
        defaults = {
            "cli-path": "", "prepare": "true", "version": "latest", "create-github-releases": "false",
            "push-git-tags": "false", "pr-draft": "",
            "github-token": "${{ github.token }}", "base-branch": "",
            "node-version": "lts/*", "npm-version": "", "rust-toolchain": "stable",
            "uv-version": "", "commit-message": "chore(release): version packages",
            "pr-title": "chore(release): version packages", "publish-script": "", "release-script": "",
        }
        self.assertEqual({key: value["default"] for key, value in self.action["inputs"].items()}, defaults)
        for key, value in self.action["outputs"].items():
            self.assertEqual(value["value"], "${{ steps.version.outputs." + key + " }}")

    def test_setup_order_and_reuse(self):
        labels = [step.get("name", step.get("uses")) for step in self.steps]
        self.assertEqual(labels, [
            "Validate release inputs", "Set up uv", "Install changenote CLI",
            "Select release work", "Discover release environments", "Set up Rust",
            "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1",
            "Install selected npm version", "Populate offline package caches", "Run release operation",
        ])
        uv = self.step("Set up uv")
        self.assertEqual(uv["if"], "steps.inputs.outputs.has-scripts == 'true' || inputs.cli-path == '' || inputs.prepare == 'true'")
        self.assertEqual(uv["with"], {"version": "${{ inputs.uv-version }}", "enable-cache": "false"})
        install = self.step("Install changenote CLI")
        self.assertNotIn("if", install)
        self.assertEqual(install["run"], 'bash "$ACTION_PATH/scripts/action/install-cli.sh"')

    def test_environment_scope_is_separate_from_root_mode(self):
        for name in ("Discover release environments", "Populate offline package caches"):
            step = self.step(name)
            self.assertEqual(step["if"], "inputs.prepare == 'true'")
            self.assertEqual(step["env"]["INPUT_OPERATION"], "${{ steps.selection.outputs.environment-operation }}")
            self.assertNotIn("INPUT_EXPECTED_RELEASE_COMMIT", step["env"])
        run = self.step("Run release operation")
        self.assertNotIn("INPUT_OPERATION", run["env"])
        self.assertEqual(run["env"]["INPUT_PUSH_GIT_TAGS"], "${{ inputs.push-git-tags }}")
        self.assertNotIn("INPUT_RETRY", run["env"])
        self.assertNotIn("INPUT_EXPECTED_RELEASE_COMMIT", run["env"])
        self.assertEqual(run["env"]["INPUT_PR_ENVIRONMENT_READY"],
                         "${{ steps.environment.outputs.pr-environment-ready != 'false' && steps.warm.outputs.pr-environment-ready != 'false' }}")

    def test_tool_versions_and_shell_boundaries(self):
        rust = self.step("Set up Rust")
        self.assertEqual(rust["if"], "steps.environment.outputs.cargo == 'true'")
        self.assertEqual(rust["with"]["toolchain"], "${{ inputs.rust-toolchain }}")
        node = next(step for step in self.steps if step.get("uses", "").startswith("actions/setup-node@"))
        self.assertEqual(node["if"], "steps.environment.outputs.npm == 'true'")
        self.assertEqual(node["with"]["package-manager-cache"], "false")
        self.assertEqual(node["with"]["node-version"], "${{ inputs.node-version }}")
        npm = self.step("Install selected npm version")
        self.assertEqual(npm["if"], "steps.environment.outputs.npm == 'true' && inputs.npm-version != ''")
        self.assertEqual(npm["run"], 'npm install --global --ignore-scripts --no-audit --no-fund "npm@$INPUT_NPM_VERSION"')
        validate = self.step("Validate release inputs")
        self.assertNotIn("GH_TOKEN", validate["env"])
        for key in ("create-github-releases", "push-git-tags", "pr-draft", "prepare", "npm-version", "rust-toolchain", "publish-script", "release-script"):
            self.assertEqual(validate["env"]["INPUT_" + key.upper().replace("-", "_")], "${{ inputs." + key + " }}")
        for name in ("Discover release environments", "Populate offline package caches"):
            env = self.step(name)["env"]
            self.assertEqual(env["GH_TOKEN"], "${{ inputs.github-token }}")
            self.assertEqual(env["INPUT_BASE_BRANCH"], "${{ inputs.base-branch }}")
            self.assertEqual(env["INPUT_RUST_TOOLCHAIN"], "${{ inputs.rust-toolchain }}")
        for step in self.steps:
            if "run" in step:
                self.assertNotIn("${{", step["run"])
                self.assertEqual(step["shell"], "bash")


if __name__ == "__main__":
    unittest.main()
