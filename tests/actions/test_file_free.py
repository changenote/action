"""File-free release identity uses the same verified Git tree on both CLI writers."""

import json
import unittest

import test_actions


class FileFree(unittest.TestCase):
    def setUp(self):
        self.f = test_actions.Actions("test_no_batch")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def finish_release(self, retain=None):
        f = self.f
        plan = json.loads(f.cli("version"))
        # Model the new storage profile when testing the historical CLI too.
        (f.repo / ".changenote/releases.json").unlink(missing_ok=True)
        if retain is not None:
            (f.repo / ".changenote/retained.md").write_bytes(retain)
        sha = f.commit("file-free release")
        f.git("push", "origin", "main")
        return sha, [{key: entry[key] for key in ("package", "version", "tag")} for entry in plan]

    def test_metadata_tags_and_retry_target_the_release_after_later_commits(self):
        f = self.f
        f.note()
        sha, plan = self.finish_release()
        f.later_commit()
        _, inspected = f.action("inspect")
        self.assertEqual(inspected["release-commit"], sha)
        self.assertEqual(json.loads(inspected["releases"]), plan)
        _, published = f.action("publish")
        self.assertEqual(published["published"], "true")
        self.assertEqual(f.git("rev-parse", plan[0]["tag"] + "^{commit}"), sha)
        state = f.state()["releases"]
        _, retried = f.action("publish")
        self.assertEqual(retried["published"], "false")
        self.assertEqual(f.state()["releases"], state)
        self.assertFalse((f.repo / ".changenote/releases.json").exists())

    def test_retained_notes_do_not_change_the_consumed_plan(self):
        f = self.f
        f.note()
        f.cli("add", "retained", "--package", "pkg", "--bump", "minor", "--message", "Later feature")
        f.commit("later note reached base")
        retained = (f.repo / ".changenote/retained.md").read_bytes()
        (f.repo / ".changenote/retained.md").unlink()
        sha, plan = self.finish_release(retained)
        _, inspected = f.action("inspect")
        self.assertEqual(inspected["release-commit"], sha)
        self.assertEqual(plan[0]["version"], "1.0.1")
        self.assertEqual(json.loads(inspected["releases"]), plan)
        self.assertEqual((f.repo / ".changenote/retained.md").read_bytes(), retained)

    def test_malformed_newest_candidate_never_publishes_an_older_release(self):
        f = self.f
        f.note()
        self.finish_release()
        f.note(name="bad")
        (f.repo / ".changenote/bad.md").unlink()
        f.commit("invalid note consumption")
        f.git("push", "origin", "main")
        result, outputs = f.action("publish", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outputs["releases"], "[]")
        self.assertEqual(f.git("ls-remote", "--tags", "origin"), "")
        self.assertEqual(f.state()["releases"], [])

    def test_historical_metadata_then_file_free_migration(self):
        f = self.f
        f.note()
        releases = json.loads(f.cli("version"))
        for entry in releases:
            del entry["notes"]
        (f.repo / ".changenote/releases.json").write_text(json.dumps(releases, indent=2) + "\n")
        old = f.commit("historical metadata release")
        f.git("push", "origin", "main")
        _, inspected = f.action("inspect")
        self.assertEqual(inspected["release-commit"], old)
        f.note()
        new, plan = self.finish_release()
        _, inspected = f.action("inspect")
        self.assertEqual(inspected["release-commit"], new)
        self.assertEqual(json.loads(inspected["releases"]), plan)
        self.assertEqual(plan[0]["version"], "1.0.2")
        self.assertFalse((f.repo / ".changenote/releases.json").exists())

    def test_local_conflict_preflights_every_tag_before_creating_any(self):
        f = self.f
        (f.repo / "b").mkdir()
        (f.repo / "b/VERSION").write_text("2.0.0\n")
        config = {"packages": {"pkg": {"path": ".", "version_file": "VERSION"},
                               "b": {"path": "b", "version_file": "VERSION"}},
                  "fixed": [["pkg", "b"]]}
        (f.repo / ".changenote/config.json").write_text(json.dumps(config))
        f.commit("fixed group")
        f.note()
        sha, plan = self.finish_release()
        first, second = [entry["tag"] for entry in plan]
        f.git("tag", second, sha + "^")
        result, _ = f.action("publish", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different commit", result.stderr)
        self.assertEqual(f.git("tag", "--list"), second)
        self.assertNotEqual(first, second)
        self.assertEqual(f.git("ls-remote", "--tags", "origin"), "")
        self.assertEqual(f.state()["releases"], [])
