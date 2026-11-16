"""Exercise read-only release discovery in standalone temporary repositories."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/action/route-release.py"
BATCH = ".changenote/releases.json"


class ReleaseCandidates(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.env = dict(os.environ, GIT_AUTHOR_NAME="Fixture", GIT_COMMITTER_NAME="Fixture",
                        GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_EMAIL="fixture@example.invalid",
                        GIT_OPTIONAL_LOCKS="0")
        self.git("init", "-q", "-b", "main")
        (self.root / ".changenote").mkdir()
        (self.root / "VERSION").write_text("1.0.0\n")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env, text=True).strip()

    def commit(self):
        self.git("add", "--", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def select(self, ok=True):
        before = (self.git("show-ref"), self.git("status", "--porcelain"))
        result = subprocess.run(
            ["uv", "run", "--no-project", "--no-config", "python", str(SCRIPT),
             "select-release", self.git("rev-parse", "HEAD")],
            cwd=self.root, env=self.env, text=True, capture_output=True,
        )
        self.assertEqual((self.git("show-ref"), self.git("status", "--porcelain")), before)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        return result.stderr

    def release(self):
        note = self.root / ".changenote/fix.md"
        note.write_text("---\npkg: patch\n---\nFix\n")
        parent = self.commit()
        note.unlink()
        (self.root / "VERSION").write_text("1.0.1\n")
        return parent

    def test_file_free_release_and_later_unrelated_commit(self):
        parent = self.release()
        release = self.commit()
        (self.root / "later").write_text("unrelated")
        self.commit()
        self.assertEqual(self.select(), {"release": release, "parent": parent, "file_free": True})

    def test_historical_batch_and_migration_deletion(self):
        parent = self.release()
        (self.root / BATCH).write_text(json.dumps([{"package": "pkg"}]))
        release = self.commit()
        self.assertEqual(self.select(), {"release": release, "parent": parent, "file_free": False})
        parent = self.release()
        (self.root / BATCH).unlink()
        release = self.commit()
        self.assertEqual(self.select(), {"release": release, "parent": parent, "file_free": True})

    def test_version_edits_and_ignored_markdown_are_not_candidates(self):
        names = ["README.md", "aGeNtS.md", "CLAUDE.md", "GEMINI.md", ".hidden.md", "nested/note.md"]
        for name in names:
            path = self.root / ".changenote" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("ignored")
        self.commit()
        for name in names:
            (self.root / ".changenote" / name).unlink()
        (self.root / "VERSION").write_text("2.0.0\n")
        self.commit()
        self.assertEqual(self.select()["release"], "")

    def test_invalid_newest_batch_is_not_skipped(self):
        self.release()
        self.commit()
        (self.root / BATCH).write_text("[]")
        self.commit()
        self.assertIn("non-empty object array", self.select(ok=False))

    def test_batch_removal_without_consumed_notes_is_rejected(self):
        self.release()
        (self.root / BATCH).write_text('[{"package":"pkg"}]')
        self.commit()
        (self.root / BATCH).unlink()
        self.commit()
        self.assertIn("removed without consumed notes", self.select(ok=False))

    def test_root_batch_and_symlink_batch_are_rejected(self):
        (self.root / BATCH).write_text('[{"package":"pkg"}]')
        self.commit()
        self.assertIn("root commit", self.select(ok=False))
        (self.root / BATCH).unlink()
        (self.root / BATCH).symlink_to("../VERSION")
        self.commit()
        self.assertIn("regular file", self.select(ok=False))

    @unittest.skipUnless(os.name == "posix", "requires byte filenames")
    def test_non_utf8_consumed_note_path_is_not_decoded(self):
        name = os.fsdecode(b"fix-\xff.md")
        path = self.root / ".changenote" / name
        path.write_text("note")
        parent = self.commit()
        path.unlink()
        release = self.commit()
        self.assertEqual(self.select(), {"release": release, "parent": parent, "file_free": True})
