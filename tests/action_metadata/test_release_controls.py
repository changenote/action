"""Validate root controls before API access and keep public examples consistent."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ReleaseControls(unittest.TestCase):
    def validate(self, entry="root", **inputs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            event = path / "event.json"
            event.write_text(json.dumps({"forced": False, "deleted": False}))
            output = path / "output"
            output.touch()
            env = {k: v for k, v in os.environ.items() if not k.startswith("INPUT_")}
            env.update(GITHUB_EVENT_NAME="push", GITHUB_EVENT_PATH=str(event), GITHUB_OUTPUT=str(output))
            env.update(inputs)
            script, arg = ("release.sh", "validate") if entry == "root" else ("inputs.sh", "manage-pr")
            result = subprocess.run(["bash", str(ROOT / "scripts/action" / script), arg],
                                    env=env, text=True, capture_output=True, timeout=30)
            return result, output.read_text()

    def test_literal_controls_and_invalid_combination(self):
        for releases in ("true", "false", "", "True", "1", " false"):
            for tags in ("true", "false", "", "yes", "0"):
                with self.subTest(releases=releases, tags=tags):
                    result, output = self.validate(INPUT_CREATE_GITHUB_RELEASES=releases, INPUT_PUSH_GIT_TAGS=tags)
                    valid = releases in ("true", "false") and tags in ("true", "false") and not (releases == "true" and tags == "false")
                    self.assertEqual(result.returncode == 0, valid, result.stderr)
                    self.assertEqual(output, "has-scripts=false\n" if valid else "")

    def test_draft_input_on_both_public_entry_points(self):
        for entry in ("root", "manage-pr"):
            for value in ("", "create", "always", "true", "false", "Always", " create"):
                result, output = self.validate(entry, INPUT_PR_DRAFT=value)
                self.assertEqual(result.returncode == 0, value in ("", "create", "always"))
                if result.returncode:
                    self.assertEqual(output, "")
        action = yaml.load((ROOT / "manage-pr/action.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(action["inputs"]["pr-draft"]["default"], "")
        for step in (action["runs"]["steps"][0], action["runs"]["steps"][-1]):
            self.assertEqual(step["env"]["INPUT_PR_DRAFT"], "${{ inputs.pr-draft }}")

    def test_either_nonblank_script_requires_router_tools(self):
        for publish, final, expected in (("", "", "false"), (" \n\t", " ", "false"),
                                         ("echo upload", "", "true"), ("", "echo final", "true")):
            result, output = self.validate(INPUT_PUBLISH_SCRIPT=publish, INPUT_RELEASE_SCRIPT=final,
                                           INPUT_PREPARE="false")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output, f"has-scripts={expected}\n")
        action = yaml.load((ROOT / "action.yml").read_text(), Loader=yaml.BaseLoader)
        steps = action["runs"]["steps"]
        uv = next(s for s in steps if s.get("name") == "Set up uv")
        self.assertIn("steps.inputs.outputs.has-scripts == 'true'", uv["if"])
        self.assertRegex(uv["uses"], r"@[0-9a-f]{40}$")
        selection = next(s for s in steps if s.get("id") == "selection")
        discovery = next(s for s in steps if s.get("id") == "environment")
        self.assertLess(steps.index(selection), steps.index(discovery))

    def test_small_root_examples_use_known_inputs_and_explicit_permissions(self):
        action = yaml.load((ROOT / "action.yml").read_text(), Loader=yaml.BaseLoader)
        guide = (ROOT / "docs/github-actions.md").read_text()
        examples = re.findall(r"```yaml\n(.*?)```", guide, re.DOTALL)
        self.assertEqual(len(examples), 5)
        for block in examples:
            job = yaml.load(block, Loader=yaml.BaseLoader)
            self.assertEqual(job["permissions"], {"contents": "write", "pull-requests": "write"})
            step = job["steps"][0]
            self.assertEqual(step["uses"], "changenote/action@<full-action-commit-sha>")
            self.assertLessEqual(set(step.get("with", {})), set(action["inputs"]))
            self.assertNotIn("operation", step["with"])
            if step["with"].get("create-github-releases") == "true":
                self.assertEqual(step["with"]["push-git-tags"], "true")


if __name__ == "__main__":
    unittest.main()
