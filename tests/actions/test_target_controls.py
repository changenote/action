"""Root target selection and script stages use only disposable local remotes."""

import json
import unittest

import test_actions
import test_command_hooks


class TargetControls(unittest.TestCase):
    def setUp(self):
        self.h = test_command_hooks.CommandHooks("test_disabled_changelog_does_not_block_hooks_or_metadata")
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.f = self.h.f

    def flags(self, releases=False, tags=False):
        self.f.env.update(INPUT_CREATE_GITHUB_RELEASES=str(releases).lower(),
                          INPUT_PUSH_GIT_TAGS=str(tags).lower())

    def worker(self, name, releases, tags, expected=None, ok=True):
        output = self.f.top / "worker-output"
        output.write_text("")
        self.f.env["GITHUB_OUTPUT"] = str(output)
        args = ["bash", str(test_actions.SOURCE / f"scripts/action/{name}.sh")]
        if name == "publish":
            args.append(expected)
        args.extend((str(releases).lower(), str(tags).lower()))
        result = self.f.run_cmd(args, ok=ok)
        return result, dict(line.split("=", 1) for line in output.read_text().splitlines())

    def test_all_four_root_target_combinations(self):
        sha = self.h.merged()
        for releases, tags in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(releases=releases, tags=tags):
                self.flags(releases, tags)
                self.f.set_state(calls=[])
                result, out = self.h.run_hooks(ok=not (releases and not tags))
                if releases and not tags:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.f.state()["calls"], [])
                    continue
                self.assertEqual(out["release-commit"], sha if tags else "")
                self.assertEqual(out["published"], str(tags).lower())
                self.assertEqual(out["ready"], str(tags).lower())
                if not releases:
                    self.assertFalse(any("/releases?" in " ".join(c) or c[:2] == ["release", "create"]
                                         for c in self.f.state()["calls"]))
        self.assertEqual(len(self.f.state()["releases"]), 1)
        # Existing tags do not make the invalid input combination valid.
        self.flags(True, False)
        self.f.set_state(calls=[])
        self.h.run_hooks(ok=False)
        self.assertEqual(self.f.state()["calls"], [])

    def test_disabled_changelog_tags_only_and_no_github_work(self):
        config = self.f.repo / ".changenote/config.json"
        value = json.loads(config.read_text())
        value["changelog"] = {"enabled": False}
        config.write_text(json.dumps(value))
        self.f.commit("disable changelog")
        self.f.git("push", "origin", "main")
        sha = self.h.merged()
        self.f.set_state(releases_api_fail=True, calls=[])
        _, out = self.worker("inspect", False, False)
        self.assertEqual(out["release-commit"], sha)
        self.assertEqual(out["publication-plan"], "[]")
        _, out = self.worker("inspect", False, True)
        self.assertEqual(json.loads(out["publication-plan"])[0]["action"], "create-tag")
        _, out = self.worker("publish", False, True, sha)
        self.assertEqual(out["published"], "true")
        self.assertEqual(self.f.git("ls-remote", "origin", "refs/tags/v1.0.1^{}").split()[0], sha)
        self.assertEqual(self.f.state()["releases"], [])
        self.assertFalse(any("/releases?" in " ".join(c) for c in self.f.state()["calls"]))
        for name in ("inspect", "publish"):
            result, _ = self.worker(name, True, True, sha, ok=False)
            self.assertIn("disabled", result.stderr)

    def test_script_stage_order_shared_artifacts_and_clean_builtin_source(self):
        sha = self.h.merged()
        self.flags(True, True)
        self.f.env["REMOTE"] = str(self.f.remote)
        publish = '''test -z "$(git ls-remote --tags "$REMOTE")"
        echo build > artifact
        echo dirty > VERSION
        echo tampered > .changenote/releases.json
        echo publish >> "$CALLS"'''
        release = '''test "$(cat artifact)" = build
        test "$(cat VERSION)" = dirty
        test -n "$(git ls-remote --tags "$REMOTE")"
        echo release >> "$CALLS"'''
        _, out = self.h.run_hooks(publish, release)
        self.assertEqual(self.h.lines(), ["publish", "release"])
        self.assertEqual(out["release-commit"], sha)
        self.assertEqual(out["published"], "true")
        self.assertEqual(out["ready"], "true")
        self.assertIn("Fix behavior", self.f.state()["releases"][0]["body"])

    def test_optional_script_combinations_with_builtin_publication_and_retries(self):
        self.h.merged()
        self.flags(True, True)
        for publish, release in (("", 'echo final >> "$CALLS"'),
                                 ('echo upload >> "$CALLS"', ""),
                                 ('echo upload >> "$CALLS"', 'echo final >> "$CALLS"')):
            self.h.calls.unlink(missing_ok=True)
            for _ in range(2):
                _, out = self.h.run_hooks(publish, release)
                self.assertEqual(out["ready"], "true")
            expected = (["upload"] if publish else []) + (["final"] if release else [])
            self.assertEqual(self.h.lines(), expected * 2)
        self.assertEqual(len(self.f.state()["releases"]), 1)

    def test_failures_stop_later_stages_and_final_failure_retains_publication(self):
        self.h.merged()
        self.flags(True, True)
        self.h.run_hooks('echo upload >> "$CALLS"; exit 7', 'echo final >> "$CALLS"', ok=False)
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")
        self.f.set_state(release_fail="v1.0.1")
        result, out = self.h.run_hooks('echo upload >> "$CALLS"', 'echo final >> "$CALLS"', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("final", self.h.lines())
        self.assertEqual(out["ready"], "false")
        self.f.set_state(release_fail=None)
        result, out = self.h.run_hooks('echo upload >> "$CALLS"', 'exit 9', ok=False)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(out["published"], "true")
        self.assertEqual(out["ready"], "false")
        self.assertEqual(len(self.f.state()["releases"]), 1)

    def test_requested_api_failure_and_tag_conflict_stop_before_scripts(self):
        sha = self.h.merged()
        self.flags(True, True)
        self.f.set_state(releases_api_fail=True)
        result, _ = self.h.run_hooks('echo unexpected >> "$CALLS"', ok=False)
        self.assertIn("Release API unavailable", result.stderr)
        self.f.set_state(releases_api_fail=False)
        self.f.git("tag", "v1.0.1", sha + "^")
        self.f.git("push", "origin", "refs/tags/v1.0.1")
        self.flags(False, True)
        result, _ = self.h.run_hooks('echo unexpected >> "$CALLS"', ok=False)
        self.assertIn("another commit", result.stderr)
        self.assertEqual(self.h.lines(), [])
        self.assertEqual(self.f.state()["releases"], [])

    def test_changed_head_after_either_script_is_rejected(self):
        self.h.merged()
        self.flags(True, True)
        result, _ = self.h.run_hooks('git commit --allow-empty -m changed', ok=False)
        self.assertIn("changed the selected release HEAD", result.stderr)
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")
        result, out = self.h.run_hooks("", 'git commit --allow-empty -m changed', ok=False)
        self.assertIn("changed the selected release HEAD", result.stderr)
        self.assertEqual(out["ready"], "false")
        self.assertEqual(len(self.f.state()["releases"]), 1)

    def test_unrelated_push_with_scripts_does_not_catch_up_old_batch(self):
        sha = self.h.merged()
        self.f.later_commit()
        self.flags(True, True)
        _, out = self.h.run_hooks('echo unexpected >> "$CALLS"', before=sha)
        self.assertEqual(out["release-commit"], "")
        self.assertEqual(out["ready"], "false")
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")
        self.assertEqual(self.h.lines(), [])
        _, out = self.h.run_hooks(before=sha)
        self.assertEqual(out["published"], "true")
        self.assertEqual(out["release-commit"], sha)

    def test_manual_event_never_runs_scripts_or_builtin_publication(self):
        self.h.merged()
        self.flags(True, True)
        _, out = self.h.run_hooks('echo unexpected >> "$CALLS"', 'echo final >> "$CALLS"',
                                  event="workflow_dispatch")
        self.assertEqual(out["release-commit"], "")
        self.assertEqual(out["ready"], "false")
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")
        self.assertEqual(self.h.lines(), [])

    def test_tags_only_checks_all_packages_before_writing_and_retries_partial_push(self):
        (self.f.repo / "b").mkdir()
        (self.f.repo / "b/VERSION").write_text("2.0.0\n")
        config = self.f.repo / ".changenote/config.json"
        value = json.loads(config.read_text())
        value["packages"]["b"] = {"path": "b", "version_file": "VERSION"}
        config.write_text(json.dumps(value))
        self.f.cli("add", "b", "--patch", "b", "-m", "Fix b")
        self.f.commit("second package")
        self.f.git("push", "origin", "main")
        sha = self.h.merged()
        batch = json.loads((self.f.repo / ".changenote/releases.json").read_text())
        first, second = (item["tag"] for item in batch)
        self.f.git("tag", second, sha + "^")
        self.f.git("push", "origin", "refs/tags/" + second)
        result, out = self.worker("publish", False, True, sha, ok=False)
        self.assertIn("another commit", result.stderr)
        self.assertEqual(out["published"], "false")
        self.assertEqual(self.f.git("ls-remote", "origin", "refs/tags/" + first), "")
        self.f.git("push", "origin", ":refs/tags/" + second)
        hook = self.f.remote / "hooks/pre-receive"
        hook.write_text(f'#!/usr/bin/env bash\nwhile read -r old new ref; do\n  if [[ $ref == refs/tags/{second} ]]; then exit 1; fi\ndone\n')
        hook.chmod(0o755)
        result, out = self.worker("publish", False, True, sha, ok=False)
        self.assertIn("Tag push failed", result.stderr)
        self.assertEqual(out["published"], "true")
        self.assertEqual(len(json.loads(out["published-packages"])), 1)
        hook.unlink()
        _, out = self.worker("publish", False, True, sha)
        self.assertEqual(len(json.loads(out["published-packages"])), 1)
        self.assertEqual(self.f.state()["releases"], [])

    def test_tags_only_namespace_conflict_and_push_race(self):
        sha = self.h.merged()
        self.f.git("tag", "v1.0.1/child", sha)
        self.f.git("push", "origin", "refs/tags/v1.0.1/child")
        result, _ = self.worker("publish", False, True, sha, ok=False)
        self.assertIn("namespace conflict", result.stderr)
        self.f.git("push", "origin", ":refs/tags/v1.0.1/child")
        hook = self.f.remote / "hooks/pre-receive"
        hook.write_text(f'#!/usr/bin/env bash\nenv -u GIT_QUARANTINE_PATH -u GIT_OBJECT_DIRECTORY -u GIT_ALTERNATE_OBJECT_DIRECTORIES git --git-dir="{self.f.remote}" update-ref refs/tags/v1.0.1 "{sha}"\nexit 1\n')
        hook.chmod(0o755)
        _, out = self.worker("publish", False, True, sha)
        self.assertEqual(out["published"], "false")
        self.assertEqual(self.f.state()["releases"], [])

    def test_legacy_checks_remain_full_readonly_with_disabled_targets(self):
        self.f.legacy_release()
        sha = self.f.git("rev-parse", "HEAD")
        for tags in (False, True):
            result, out = self.worker("inspect", False, tags, ok=False)
            self.assertIn("complete existing publication", result.stderr)
            self.assertEqual(out["ready"], "false")
        self.f.action("publish", ok=False)
        self.assertEqual(self.f.git("ls-remote", "--tags", "origin"), "")
        self.f.git("tag", "v1.0.1", sha)
        self.f.git("push", "origin", "refs/tags/v1.0.1")
        self.f.set_state(releases=[{"tag_name": "v1.0.1", "draft": False, "body": "keep"}])
        _, out = self.worker("publish", False, False, sha)
        self.assertEqual(out["published"], "false")
        self.f.set_state(releases_api_fail=True)
        self.worker("inspect", False, False, ok=False)


if __name__ == "__main__":
    unittest.main()
