"""Root orchestration and standalone publication with local Git and mock GitHub."""

import json
from pathlib import Path
import unittest

import test_actions

OUTPUTS = {
    "release-commit", "releases", "published", "published-packages",
    "publication-plan", "publication-needed", "ready", "has-notes",
    "pr-number", "pr-operation",
}
RELEASES = [{"package": "pkg", "version": "1.0.1", "tag": "v1.0.1"}]


class RootAction(unittest.TestCase):
    def setUp(self):
        self.f = test_actions.Actions("test_no_batch")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        for key in tuple(self.f.env):
            if key.startswith("INPUT_"):
                self.f.env.pop(key)
        self.f.env["INPUT_GITHUB_TOKEN"] = "test-token"
        self.f.git("config", "gc.auto", "0")
        self.f.git("config", "maintenance.auto", "false")
        self.event = self.f.top / "event.json"
        self.event.write_text(json.dumps({"forced": False, "deleted": False}))
        self.f.env.update(GITHUB_EVENT_PATH=str(self.event), GITHUB_REF="refs/heads/main",
                          TMPDIR=str(self.f.top / "root-temp"))
        Path(self.f.env["TMPDIR"]).mkdir()

    def run_root(self, publication=True, event="push", ok=True):
        self.f.env.update(GITHUB_EVENT_NAME=event)
        for key in ("INPUT_PUSH_GIT_TAGS", "INPUT_CREATE_GITHUB_RELEASES"):
            self.f.env.pop(key, None)
            if publication:
                self.f.env[key] = "true"
        result, outputs = self.f.action("release", ok=ok)
        self.assertNotIn("test-token", result.stdout + result.stderr + json.dumps(outputs))
        self.assertEqual(list(Path(self.f.env["TMPDIR"]).iterdir()), [])
        if result.returncode == 0:
            self.assertEqual(set(outputs), OUTPUTS)
        return result, outputs

    def test_no_batch_and_manual_runs_do_not_publish(self):
        for publication, event in ((True, "push"), (True, "workflow_dispatch"),
                                   (False, "workflow_dispatch")):
            with self.subTest(publication=publication, event=event):
                _, out = self.run_root(publication, event)
                self.assertEqual(out["release-commit"], "")
                self.assertEqual(out["releases"], "[]")
                self.assertEqual(out["publication-needed"], "false")
                self.assertEqual(out["published"], "false")
                self.assertEqual(out["has-notes"], "false")
                self.assertEqual(out["publication-plan"], "[]")
                self.assertEqual(out["published-packages"], "[]")
                self.assertEqual(out["pr-number"], "")
                self.assertEqual(out["pr-operation"], "none")
        self.assertEqual(self.f.state()["releases"], [])
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")

    def test_push_creates_pr_without_a_saved_batch(self):
        self.f.note("Literal $(touch injected) and `touch injected`")
        _, out = self.run_root()
        self.assertEqual(out["pr-operation"], "created")
        self.assertEqual(out["has-notes"], "true")
        self.assertEqual(out["release-commit"], "")
        self.assertEqual(out["ready"], "true")
        self.assertFalse((self.f.repo / "injected").exists())

    def test_manual_calls_only_manage_pr(self):
        self.f.release()
        self.f.note("Next release", "next")
        for publication in (True, False):
            _, out = self.run_root(publication, "workflow_dispatch")
            self.assertIn(out["pr-operation"], ("created", "updated"))
            self.assertEqual(out["release-commit"], "")
            self.assertEqual(out["publication-plan"], "[]")
            self.assertEqual(out["ready"], "false")
        self.assertEqual(self.f.state()["releases"], [])
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")

    def test_auto_publishes_latest_batch_and_manages_next_pr(self):
        sha = self.f.release()
        self.f.later_commit()
        self.f.note("Next release", "next")
        pending = (self.f.repo / ".changenote/next.md").read_bytes()
        _, out = self.run_root()
        self.assertEqual(out["release-commit"], sha)
        self.assertEqual(json.loads(out["releases"]), RELEASES)
        self.assertEqual(out["publication-needed"], "true")
        self.assertEqual(out["pr-operation"], "created")
        self.assertEqual(out["pr-number"], "2")
        self.assertEqual(out["has-notes"], "true")
        self.assertEqual(json.loads(out["publication-plan"])[0]["action"], "create-tag-and-release")
        self.assertEqual(json.loads(out["published-packages"]), [{"name": "pkg", "version": "1.0.1"}])
        self.assertEqual(self.f.state()["releases"][0]["tag_name"], "v1.0.1")
        self.assertEqual(out["published"], "true")
        self.assertEqual(out["ready"], "true")
        self.assertEqual((self.f.repo / ".changenote/next.md").read_bytes(), pending)

    def test_completed_inspection_retains_identity_without_republication(self):
        sha = self.f.release()
        self.f.action("publish")
        _, inspected = self.f.action("inspect")
        self.assertEqual(inspected["release-commit"], sha)
        self.assertEqual(inspected["publication-needed"], "false")
        _, out = self.run_root()
        self.assertEqual(out["release-commit"], sha)
        self.assertEqual(json.loads(out["releases"]), RELEASES)
        self.assertEqual(out["published"], "false")
        self.assertEqual(out["ready"], "true")

    def test_standalone_retry_finishes_partial_publication_without_pr_work(self):
        sha = self.f.release()
        self.f.env["INPUT_EXPECTED_RELEASE_COMMIT"] = sha
        self.f.set_state(release_fail="v1.0.1")
        self.f.action("publish", ok=False)
        self.assertIn(sha, self.f.git("ls-remote", "--tags", "origin"))
        self.f.set_state(release_fail=None)
        _, out = self.f.action("publish")
        self.assertEqual(out["published"], "true")
        self.assertEqual(len(self.f.state()["pulls"]), 1)
        _, again = self.f.action("publish")
        self.assertEqual(again["published"], "false")

    def test_standalone_publish_rejects_a_stale_exact_commit_without_writes(self):
        sha = self.f.release()
        self.f.note("Second batch", "second")
        self.f.cli("version")
        self.f.commit("second release")
        self.f.git("push", "origin", "main")
        self.f.env["INPUT_EXPECTED_RELEASE_COMMIT"] = sha
        result, _ = self.f.action("publish", ok=False)
        self.assertIn("changed after", result.stderr)
        self.assertEqual(self.f.state()["releases"], [])
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")

    def test_auto_still_publishes_when_pr_management_fails(self):
        sha = self.f.release()
        self.f.note("Next release", "next")
        self.f.set_state(pr_fail=True)
        result, out = self.run_root(ok=False)
        self.assertIn("PR permission denied", result.stderr)
        self.assertEqual(out["release-commit"], sha)
        self.assertEqual(out["published"], "true")
        self.assertNotEqual(result.returncode, 0)

    def test_auto_rejects_a_new_batch_between_inspection_and_publication(self):
        f = self.f
        f.release()
        f.note("Next batch", "next")
        f.cli("version")
        newer = f.commit("next release")
        f.git("push", "origin", "HEAD:refs/heads/staged-batch")
        f.env.update(RACE_REMOTE=str(f.remote), RACE_BATCH=newer)
        gh = f.bin / "gh"
        gh.write_text(
            '#!/usr/bin/env bash\n'
            'if [[ "$*" == *"/releases?"* ]]; then\n'
            '  git --git-dir="$RACE_REMOTE" update-ref refs/heads/main "$RACE_BATCH"\n'
            'fi\n'
            'exec uv run --no-project python "$MOCK_GH_SCRIPT" "$@"\n'
        )
        gh.chmod(0o755)
        result, out = self.run_root(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed after", result.stderr)
        self.assertEqual(out["published"], "false")
        self.assertEqual(f.state()["releases"], [])
        self.assertEqual(f.git("ls-remote", "--tags", "origin"), "")

    def test_each_target_scope_runs_pr_generation_once(self):
        log = self.f.top / "cli-calls"
        binary = self.f.bin / "changenote"
        binary.unlink()
        binary.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$CLI_CALLS"\nexec "$REAL_CLI" "$@"\n')
        binary.chmod(0o755)
        self.f.env.update(CLI_CALLS=str(log), REAL_CLI=str(test_actions.CLI))
        self.f.note()
        for publication in (True, False):
            log.write_text("")
            self.run_root(publication, "workflow_dispatch")
            self.assertEqual(log.read_text().splitlines().count("status --include-note-sections"), 1)

    def test_selected_rust_toolchain_is_used_by_auto_workers(self):
        self.f.release()
        calls = self.f.top / "toolchain-calls"
        binary = self.f.bin / "changenote"
        binary.unlink()
        binary.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$RUSTUP_TOOLCHAIN" >> "$TOOLCHAIN_CALLS"\nexec "$REAL_CLI" "$@"\n')
        binary.chmod(0o755)
        self.f.env.update(TOOLCHAIN_CALLS=str(calls), REAL_CLI=str(test_actions.CLI),
                          INPUT_RUST_TOOLCHAIN="stable", RUSTUP_TOOLCHAIN="not-selected")
        self.run_root()
        self.assertEqual(set(calls.read_text().splitlines()), {"stable"})

    def test_invalid_inputs_and_removed_modes_fail_before_api_calls(self):
        baseline = self.f.env.copy()
        cases = [
            {"INPUT_CREATE_GITHUB_RELEASES": "true", "INPUT_PUSH_GIT_TAGS": "false"},
            {"INPUT_PUSH_GIT_TAGS": "TRUE"}, {"INPUT_PUSH_GIT_TAGS": ""},
            {"INPUT_CREATE_GITHUB_RELEASES": "yes"}, {"INPUT_PR_DRAFT": "false"},
            {"INPUT_PREPARE": "yes"}, {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "pull_request_target"}, {"INPUT_RETRY": "true"},
            {"INPUT_EXPECTED_RELEASE_COMMIT": "a" * 40},
            {"INPUT_NPM_VERSION": "latest"}, {"INPUT_NPM_VERSION": "1.2.3; touch injected"},
            {"INPUT_RUST_TOOLCHAIN": "stable; touch injected"},
        ]
        for values in cases:
            with self.subTest(values=values):
                self.f.env = {**baseline, "GITHUB_EVENT_NAME": "push", **values}
                result, out = self.f.action("release", ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(out, {})
        self.f.env = dict(baseline, GITHUB_EVENT_NAME="push")
        for payload in ({"forced": True, "deleted": False}, {"forced": False, "deleted": True},
                        {}, {"forced": "false", "deleted": False}):
            self.event.write_text(json.dumps(payload))
            _, out = self.f.action("release", ok=False)
            self.assertEqual(out, {})
        self.assertEqual(self.f.state().get("calls", []), [])

    def test_root_validation_has_no_public_mode_output(self):
        self.f.env.update(GITHUB_EVENT_NAME="workflow_dispatch")
        output = self.f.top / "validation-output"
        output.write_text("")
        self.f.env["GITHUB_OUTPUT"] = str(output)
        self.f.run_cmd(["bash", str(test_actions.SOURCE / "scripts/action/release.sh"), "validate"])
        self.assertEqual(dict(line.split("=", 1) for line in output.read_text().splitlines()),
                         {"has-scripts": "false"})
        self.assertEqual(self.f.state().get("calls", []), [])


if __name__ == "__main__":
    unittest.main()
