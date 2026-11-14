"""Draft state is controlled only on managed PRs, through both public workers."""

import json
import unittest

import test_actions


class DraftPRs(unittest.TestCase):
    def setUp(self):
        self.f = test_actions.Actions("test_no_batch")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        event = self.f.top / "event.json"
        event.write_text("{}")
        self.f.env.update(INPUT_GITHUB_TOKEN="test-token", GITHUB_EVENT_NAME="workflow_dispatch",
                          GITHUB_REF="refs/heads/main", GITHUB_EVENT_PATH=str(event))

    def reset(self):
        self.doCleanups()
        self.setUp()

    def graphql(self):
        return [c for c in self.f.state().get("calls", []) if "graphql" in c]

    def test_creation_modes_and_lost_response_on_both_entry_points(self):
        for entry in ("version", "release"):
            for mode in ("", "create", "always"):
                for lost in (False, True):
                    with self.subTest(entry=entry, mode=mode, lost=lost):
                        self.reset()
                        self.f.note()
                        self.f.env["INPUT_PR_DRAFT"] = mode
                        self.f.set_state(pr_lost_response=lost)
                        _, out = self.f.action(entry)
                        pr = self.f.state()["pulls"][0]
                        self.assertEqual(pr["draft"], bool(mode))
                        self.assertEqual(out["pr-operation"], "created")
                        self.assertEqual(out["pr-number"], "1")
                        self.assertEqual(self.graphql(), [])

    def test_update_preserves_drafts_except_always_converts_ready_even_on_noop(self):
        for entry in ("version", "release"):
            for mode in ("", "create", "always"):
                for draft in (False, True):
                    with self.subTest(entry=entry, mode=mode, draft=draft):
                        self.reset()
                        self.f.note()
                        self.f.action()
                        prs = self.f.state()["pulls"]
                        prs[0]["draft"] = draft
                        self.f.set_state(pulls=prs, calls=[])
                        before = self.f.git("ls-remote", "origin", "refs/heads/" + test_actions.BRANCH)
                        self.f.env["INPUT_PR_DRAFT"] = mode
                        _, out = self.f.action(entry)
                        self.assertEqual(self.f.state()["pulls"][0]["draft"], draft or mode == "always")
                        self.assertEqual(len(self.graphql()), int(mode == "always" and not draft))
                        self.assertEqual(out["pr-operation"], "updated")
                        self.assertEqual(before, self.f.git("ls-remote", "origin", "refs/heads/" + test_actions.BRANCH))
                        # A changed tree uses the same update policy.
                        self.f.note("Another fix", "another")
                        self.f.action(entry)
                        self.assertEqual(self.f.state()["pulls"][0]["draft"], draft or mode == "always")

    def test_no_notes_closes_without_conversion(self):
        for entry in ("version", "release"):
            with self.subTest(entry=entry):
                self.reset()
                self.f.note()
                self.f.action()
                self.f.git("rm", ".changenote/fix.md")
                self.f.commit("remove notes")
                self.f.git("push", "origin", "main")
                self.f.env["INPUT_PR_DRAFT"] = "always"
                _, out = self.f.action(entry)
                self.assertEqual(out["pr-operation"], "closed")
                self.assertEqual(self.graphql(), [])
                self.assertFalse(self.f.state()["pulls"][0]["draft"])

    def test_invalid_values_fail_before_api_calls(self):
        for entry in ("version", "release"):
            for mode in ("true", "false", "Always", " create", "never"):
                self.f.env["INPUT_PR_DRAFT"] = mode
                result, _ = self.f.action(entry, ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.f.state().get("calls", []), [])

    def test_mutation_failure_fails_after_pr_text_update(self):
        for entry in ("version", "release"):
            with self.subTest(entry=entry):
                self.reset()
                self.f.note()
                self.f.action()
                self.f.env.update(INPUT_PR_DRAFT="always", INPUT_PR_TITLE="Updated title")
                self.f.set_state(draft_fail=True)
                result, _ = self.f.action(entry, ok=False)
                self.assertIn("Draft conversion denied", result.stderr)
                self.assertNotEqual(result.returncode, 0)
                pr = self.f.state()["pulls"][0]
                self.assertEqual(pr["title"], "Updated title")
                self.assertFalse(pr["draft"])

    def test_unmanaged_pr_never_converts(self):
        self.f.note()
        self.f.action()
        prs = self.f.state()["pulls"]
        prs[0]["body"] = "Not managed"
        self.f.set_state(pulls=prs)
        self.f.env["INPUT_PR_DRAFT"] = "always"
        result, _ = self.f.action(ok=False)
        self.assertIn("unmanaged", result.stderr)
        self.assertEqual(self.graphql(), [])

    def test_missing_node_id_fails_without_mutation(self):
        self.f.note()
        self.f.action()
        prs = self.f.state()["pulls"]
        prs[0].pop("node_id")
        self.f.set_state(pulls=prs)
        self.f.env["INPUT_PR_DRAFT"] = "always"
        result, _ = self.f.action(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.graphql(), [])


if __name__ == "__main__":
    unittest.main()
