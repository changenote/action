"""Preparation scopes and PR validation do not depend on root operation dispatch."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class InputBoundaries(unittest.TestCase):
    def validate(self, target, scope="", expected="", event="workflow_dispatch"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "outputs"
            output.write_text("")
            payload = root / "event.json"
            payload.write_text(json.dumps({"forced": False, "deleted": False}))
            env = dict(os.environ)
            for key in list(env):
                if key.startswith("INPUT_"):
                    env.pop(key)
            env.update(GITHUB_EVENT_NAME=event, GITHUB_EVENT_PATH=str(payload),
                       GITHUB_OUTPUT=str(output), INPUT_OPERATION=scope,
                       INPUT_EXPECTED_RELEASE_COMMIT=expected)
            result = subprocess.run(["bash", str(ROOT / "scripts/action/inputs.sh"), target],
                                    env=env, text=True, capture_output=True, timeout=30)
            return result, output.read_text()

    def test_valid_preparation_scopes_on_push_and_manual_events(self):
        for event in ("push", "workflow_dispatch"):
            for scope in ("manage-pr", "inspect", "auto", "publish"):
                with self.subTest(event=event, scope=scope):
                    result, output = self.validate("prepare", scope, "a" * 40 if scope == "publish" else "", event)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(output, f"operation={scope}\n")

    def test_invalid_scopes_and_commit_guards_fail_without_outputs(self):
        for scope, expected in (("select", ""), ("retry-publication", ""), ("hooks", ""),
                                ("publish", ""), ("publish", "A" * 40),
                                ("publish", "a" * 39), ("inspect", "a" * 40)):
            with self.subTest(scope=scope, expected=expected):
                result, output = self.validate("prepare", scope, expected)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")

    def test_pr_validation_accepts_only_safe_events_without_root_dispatch(self):
        for event in ("push", "workflow_dispatch", "pull_request", "pull_request_target"):
            result, output = self.validate("manage-pr", event=event)
            self.assertEqual(result.returncode == 0, event in ("push", "workflow_dispatch"))
            self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
