"""Source-link contracts with an installed feature CLI, local Git, and mocked GitHub."""

import json
import shutil
import unittest

import test_actions
from test_inspect import snapshot

REPOSITORY = "https://github.com/test/repo"


class SourceLinks(unittest.TestCase):
    def setUp(self):
        self.new_fixture()

    def new_fixture(self):
        self.f = test_actions.Actions("test_no_batch")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.git("config", "gc.auto", "0")
        self.f.git("config", "maintenance.auto", "false")

    def configure(self, **controls):
        f = self.f
        path = f.repo / ".changenote/config.json"
        config = json.loads(path.read_text())
        config["changelog"] = {"source_repository": REPOSITORY, **controls}
        path.write_text(json.dumps(config))
        f.commit("source configuration")
        f.git("push", "origin", "main")

    def merge_release(self, mode="squash"):
        f = self.f
        f.git("fetch", "origin", test_actions.BRANCH)
        if mode == "merge":
            f.git("merge", "--no-ff", "FETCH_HEAD", "-m", "merge release")
        elif mode == "rebase":
            f.git("cherry-pick", "FETCH_HEAD")
        else:
            f.git("merge", "--squash", "FETCH_HEAD")
            f.commit("squash release")
        sha = f.git("rev-parse", "HEAD")
        f.git("push", "origin", "main")
        return sha

    def assert_no_source_api(self):
        self.assertFalse(any(
            "/commits/" in argument
            for call in self.f.state()["calls"] for argument in call
        ))

    def test_sources_match_pr_changelog_and_release_across_merge_modes(self):
        for index, mode in enumerate(("merge", "squash", "rebase")):
            with self.subTest(mode=mode):
                if index:
                    self.new_fixture()
                f = self.f
                self.configure(note_template="{package}@{version} [{bump}]\n\n{summary}")
                f.note("Fix output ([#7](https://github.com/test/repo/pull/7)).")
                first = f.git("rev-parse", "HEAD")
                path = f.repo / ".changenote/fix.md"
                path.write_text(path.read_text() + "More detail.\n")
                second = f.commit("edit note")
                f.git("mv", ".changenote/fix.md", ".changenote/renamed.md")
                third = f.commit("rename note")
                f.git("push", "origin", "main")
                f.action()
                body = f.state()["pulls"][0]["body"]
                links = [f"[{sha[:12]}]({REPOSITORY}/commit/{sha})" for sha in sorted((first, second, third))]
                for link in links:
                    self.assertEqual(body.count(link), 1)
                self.assertIn("[#7](https://github.com/test/repo/pull/7)", body)
                # A newer pending note is retained, not included in this batch.
                f.note("Next release only", "future")
                release = self.merge_release(mode)
                expected = f.cli("release-notes", "--package", "pkg", "--version", "1.0.1") + "\n"
                for link in links:
                    self.assertEqual(expected.count(link), 1)
                self.assertNotIn("Next release only", expected)
                self.assertTrue((f.repo / ".changenote/future.md").exists())
                # Later configuration and checkout remote changes cannot replace the historical URL.
                config = f.repo / ".changenote/config.json"
                value = json.loads(config.read_text())
                value["changelog"]["source_repository"] = "https://github.com/other/repo"
                config.write_text(json.dumps(value))
                f.commit("later repository URL")
                f.git("push", "origin", "main")
                if mode == "merge":
                    f.git("remote", "remove", "origin")
                else:
                    f.git("remote", "set-url", "origin", str(f.top / "not-the-publication-remote"))
                _, out = f.action("inspect")
                self.assertEqual(out["release-commit"], release)
                self.assertEqual(out["ready"], "true")
                _, out = f.action("publish")
                self.assertEqual(out["published"], "true")
                self.assertEqual(f.state()["releases"][0]["body"], expected)
                _, out = f.action("publish")
                self.assertEqual(out["published"], "false")
                self.assertEqual(len(f.state()["releases"]), 1)
                self.assert_no_source_api()

    def test_disabled_changelog_keeps_pr_sources_but_rejects_publication(self):
        f = self.f
        self.configure(enabled=False)
        f.note("Fix")
        source = f.git("rev-parse", "HEAD")
        f.action()
        self.assertIn(f"{REPOSITORY}/commit/{source}", f.state()["pulls"][0]["body"])
        self.merge_release()
        self.assertFalse((f.repo / "CHANGELOG.md").exists())
        before = snapshot(f.remote)
        for operation in ("inspect", "publish"):
            result, _ = f.action(operation, ok=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("disabled", result.stderr)
            self.assertEqual(snapshot(f.remote), before)
            self.assertEqual(f.state()["releases"], [])

    def test_edited_link_cannot_bypass_complete_tree_verification(self):
        f = self.f
        self.configure()
        self.merge_source_release()
        path = f.repo / "CHANGELOG.md"
        path.write_text(path.read_text().replace(REPOSITORY, "https://github.com/forged/repo"))
        # Fold the edit into the batch commit, as a manually changed release tree.
        f.git("add", "--", "CHANGELOG.md")
        f.git("commit", "--amend", "--no-edit")
        f.git("push", "--force", "origin", "main")
        before = snapshot(f.remote)
        result, _ = f.action("publish", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("generated release tree", result.stderr)
        self.assertEqual(snapshot(f.remote), before)
        self.assertEqual(f.state()["releases"], [])

    def merge_source_release(self):
        self.f.note("Fix")
        self.f.action()
        return self.merge_release()

    def test_missing_historical_sources_fail_replay_but_extraction_needs_no_history(self):
        f = self.f
        self.configure()
        self.merge_source_release()
        expected = f.cli("release-notes", "--package", "pkg", "--version", "1.0.1")
        real_git = shutil.which("git")
        wrapper = f.bin / "git"
        wrapper.write_text(
            '#!/usr/bin/env bash\n'
            'for arg in "$@"; do [[ $arg != log ]] || exit 1; done\n'
            f'exec "{real_git}" "$@"\n'
        )
        wrapper.chmod(0o755)
        self.assertEqual(f.cli("release-notes", "--package", "pkg", "--version", "1.0.1"), expected)
        before = snapshot(f.remote)
        result, _ = f.action("publish", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot prove note sources", result.stderr)
        self.assertEqual(snapshot(f.remote), before)
        self.assertEqual(f.state()["releases"], [])
        self.assert_no_source_api()


if __name__ == "__main__":
    unittest.main()
