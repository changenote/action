"""Check the opt-in high-level composite's setup order and input boundaries."""

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ReleaseMetadata(unittest.TestCase):
    def setUp(self):
        self.action = yaml.load((ROOT / "release/action.yml").read_text(), Loader=yaml.BaseLoader)
        self.steps = self.action["runs"]["steps"]

    def step(self, name):
        return next(step for step in self.steps if step.get("name") == name)

    def test_defaults_and_output_forwarding(self):
        self.assertEqual(self.action["runs"]["using"], "composite")
        defaults = {
            "cli-path": "", "prepare": "true",
            "version": "latest", "operation": "auto", "github-token": "${{ github.token }}",
            "base-branch": "", "expected-release-commit": "", "retry": "false",
            "node-version": "lts/*", "npm-version": "", "rust-toolchain": "stable",
            "uv-version": "", "commit-message": "chore(release): version packages",
            "pr-title": "chore(release): version packages",
        }
        self.assertEqual({key: value["default"] for key, value in self.action["inputs"].items()}, defaults)
        self.assertEqual(set(self.action["outputs"]), {
            "release-commit", "releases", "published", "published-packages",
            "publication-plan", "publication-needed", "ready", "has-notes",
            "pr-number", "pr-operation",
        })
        for key, value in self.action["outputs"].items():
            self.assertEqual(value["value"], "${{ steps.release.outputs." + key + " }}")
        # Root exposes the complete dispatcher but preserves its hooks default.
        root = yaml.load((ROOT / "action.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(set(root["outputs"]), set(self.action["outputs"]))
        self.assertTrue(set(self.action["inputs"]).issubset(root["inputs"]))
        self.assertEqual(root["inputs"]["operation"]["default"], "hooks")
        self.assertEqual(root["inputs"]["publish-script"]["default"], "")
        self.assertEqual(root["inputs"]["release-script"]["default"], "")
        self.assertIn("release.sh", root["runs"]["steps"][-1]["run"])

    def test_setup_order_and_selected_cli_installation(self):
        labels = [step.get("name", step.get("uses")) for step in self.steps]
        self.assertEqual(labels, [
            "Validate release inputs", "Set up uv", "Install changenote CLI",
            "Discover release environments", "Set up Rust",
            "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1",
            "Install selected npm version", "Populate offline package caches", "Run release operation",
        ])
        self.assertFalse(any(step.get("id") == "cache" for step in self.steps))
        install = self.step("Install changenote CLI")
        self.assertNotIn("if", install)
        self.assertEqual(install["run"], 'bash "$ACTION_PATH/../scripts/action/install-cli.sh"')
        self.assertEqual(install["env"]["INPUT_VERSION"], "${{ inputs.version }}")
        rust = next(step for step in self.steps if step.get("uses", "").startswith("dtolnay/"))
        self.assertEqual(rust["with"]["toolchain"], "${{ inputs.rust-toolchain }}")
        self.assertEqual(rust["if"], "steps.environment.outputs.cargo == 'true'")
        self.assertLess(labels.index("Discover release environments"), labels.index("Set up Rust"))
        for name, script, operation in (
            ("Validate release inputs", "release.sh", "validate"),
            ("Discover release environments", "release-environment.sh", "discover"),
            ("Populate offline package caches", "release-environment.sh", "warm"),
            ("Run release operation", "release.sh", "run"),
        ):
            self.assertEqual(self.step(name)["run"], f'bash "$ACTION_PATH/../scripts/action/{script}" {operation}')

    def test_config_based_environment_conditions_and_versions(self):
        node = next(step for step in self.steps if step.get("uses", "").startswith("actions/setup-node@"))
        uv = next(step for step in self.steps if step.get("uses", "").startswith("astral-sh/setup-uv@"))
        self.assertEqual(node["if"], "steps.environment.outputs.npm == 'true'")
        self.assertEqual(node["with"], {
            "node-version": "${{ inputs.node-version }}", "package-manager-cache": "false",
        })
        self.assertEqual(uv["if"], "inputs.cli-path == '' || inputs.prepare == 'true'")
        self.assertEqual(uv["with"], {"version": "${{ inputs.uv-version }}", "enable-cache": "false"})
        self.assertLess(self.steps.index(uv), self.steps.index(self.step("Install changenote CLI")))
        npm = self.step("Install selected npm version")
        self.assertEqual(npm["if"], "steps.environment.outputs.npm == 'true' && inputs.npm-version != ''")
        self.assertEqual(npm["env"], {"INPUT_NPM_VERSION": "${{ inputs.npm-version }}"})
        self.assertEqual(npm["run"], 'npm install --global --ignore-scripts --no-audit --no-fund "npm@$INPUT_NPM_VERSION"')
        self.assertEqual(self.step("Populate offline package caches")["if"], "inputs.prepare == 'true'")

    def test_expressions_enter_shell_only_through_environment(self):
        for step in self.steps:
            if "run" not in step:
                continue
            with self.subTest(step=step["name"]):
                self.assertEqual(step["shell"], "bash")
                self.assertNotIn("${{", step["run"])
                if "ACTION_PATH" in step["env"]:
                    self.assertEqual(step["env"]["ACTION_PATH"], "${{ github.action_path }}")
        validate = self.step("Validate release inputs")
        for key in ("operation", "expected-release-commit", "retry", "npm-version", "rust-toolchain"):
            self.assertEqual(validate["env"]["INPUT_" + key.upper().replace("-", "_")], "${{ inputs." + key + " }}")
        self.assertNotIn("GH_TOKEN", validate["env"])
        install = self.step("Install changenote CLI")
        self.assertNotIn("GH_TOKEN", install["env"])
        self.assertNotIn("INPUT_RUST_TOOLCHAIN", install["env"])
        for name in ("Discover release environments", "Populate offline package caches", "Run release operation"):
            env = self.step(name)["env"]
            self.assertEqual(env["INPUT_OPERATION"], "${{ steps.inputs.outputs.operation }}")
            self.assertEqual(env["GH_TOKEN"], "${{ inputs.github-token }}")
            self.assertEqual(env["INPUT_BASE_BRANCH"], "${{ inputs.base-branch }}")
            self.assertEqual(env["INPUT_EXPECTED_RELEASE_COMMIT"], "${{ inputs.expected-release-commit }}")
        for name in ("Discover release environments", "Populate offline package caches"):
            self.assertEqual(self.step(name)["env"]["INPUT_RUST_TOOLCHAIN"], "${{ inputs.rust-toolchain }}")
        self.assertEqual(self.step("Populate offline package caches")["id"], "warm")
        run = self.step("Run release operation")
        self.assertEqual(run["env"]["INPUT_PR_ENVIRONMENT_READY"], "${{ steps.environment.outputs.pr-environment-ready != 'false' && steps.warm.outputs.pr-environment-ready != 'false' }}")
        self.assertEqual(run["id"], "release")
        for key in ("retry", "npm-version", "rust-toolchain", "commit-message", "pr-title"):
            self.assertEqual(run["env"]["INPUT_" + key.upper().replace("-", "_")], "${{ inputs." + key + " }}")


if __name__ == "__main__":
    unittest.main()
