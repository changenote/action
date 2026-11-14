"""Exercise isolated PyPI installation with a uv stub; never build consumer code."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReleaseSetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.top = Path(temporary.name)
        self.consumer = self.top / "consumer"
        self.consumer.mkdir()
        (self.consumer / "pyproject.toml").write_text("invalid consumer project\n")
        (self.consumer / "uv.toml").write_text("invalid consumer config\n")
        (self.consumer / ".python-version").write_text("not-selected\n")
        self.runner = self.top / "runner temp"
        self.runner.mkdir()
        self.bin = self.top / "bin"
        self.bin.mkdir()
        self.calls = self.top / "calls"
        self.path_file = self.top / "path"
        self.path_file.write_text("")
        stub = self.bin / "uv"
        stub.write_text(
            '#!/usr/bin/env bash\nset -eu\n'
            'printf "%s\\0" "$@" >> "$CALLS"\n'
            'pwd > "$CALLS.cwd"\n'
            'printf "%s\\n" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR" > "$CALLS.directories"\n'
            'printf "%s|%s|%s" "${GH_TOKEN-unset}" "${GITHUB_TOKEN-unset}" '
            '"${INPUT_GITHUB_TOKEN-unset}" > "$CALLS.tokens"\n'
            '[[ ${MODE:-} != failure ]] || exit 7\n'
            '[[ ${MODE:-} != missing ]] || exit 0\n'
            'mkdir -p "$UV_TOOL_DIR/changenote/bin" "$UV_TOOL_BIN_DIR"\n'
            'binary="$UV_TOOL_DIR/changenote/bin/changenote"\n'
            'printf "%s\\n" \'#!/usr/bin/env bash\' '
            '\'printf "%s\\n" "${REPORTED_VERSION:-changenote 9.8.7}"\' > "$binary"\n'
            'if [[ ${MODE:-} != nonexecutable ]]; then chmod +x "$binary"; fi\n'
            'if [[ ${MODE:-} == outside ]]; then\n'
            '  cp "$binary" "$CALLS.outside"\n'
            '  binary="$CALLS.outside"\nfi\n'
            'ln -s "$binary" "$UV_TOOL_BIN_DIR/changenote"\n'
        )
        stub.chmod(0o755)
        cargo = self.bin / "cargo"
        cargo.write_text('#!/usr/bin/env bash\ntouch "$CALLS.cargo"\nexit 99\n')
        cargo.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                        RUNNER_TEMP=str(self.runner), GITHUB_PATH=str(self.path_file),
                        CALLS=str(self.calls), GH_TOKEN="must-not-leak",
                        GITHUB_TOKEN="must-not-leak", INPUT_GITHUB_TOKEN="must-not-leak",
                        UV_TOOL_DIR=str(self.top / "unused tools"),
                        UV_TOOL_BIN_DIR=str(self.top / "unused bin"))
        for key in ("INPUT_VERSION", "REPORTED_VERSION", "MODE"):
            self.env.pop(key, None)

    def run_setup(self, ok=True):
        before = {str(p): p.read_bytes() for p in self.consumer.rglob("*") if p.is_file()}
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/action/install-cli.sh")],
            cwd=self.consumer, env=self.env, text=True, capture_output=True, timeout=30,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(before, {
            str(p): p.read_bytes() for p in self.consumer.rglob("*") if p.is_file()
        })
        self.assertFalse(Path(str(self.calls) + ".cargo").exists())
        self.assertFalse((self.top / "unused tools").exists())
        self.assertFalse((self.top / "unused bin").exists())
        return result

    def arguments(self):
        return self.calls.read_bytes().decode().split("\0")[:-1]

    def test_default_installs_latest_wheel_from_pypi_outside_consumer(self):
        self.run_setup()
        directory = Path(self.path_file.read_text().strip()).parent
        self.assertEqual(directory.parent, self.runner)
        self.assertEqual(self.arguments(), [
            "tool", "install", "--no-config", "--no-sources", "--no-cache", "--no-build",
            "--default-index", "https://pypi.org/simple", "--resolution", "highest",
            "--prerelease", "disallow", "changenote",
        ])
        self.assertEqual(Path(str(self.calls) + ".cwd").read_text().strip(), str(directory))
        self.assertEqual(Path(str(self.calls) + ".directories").read_text().splitlines(), [
            str(directory / "tools"), str(directory / "bin"),
        ])
        self.assertEqual(Path(str(self.calls) + ".tokens").read_text(), "unset|unset|unset")
        self.assertTrue((directory / "bin/changenote").is_symlink())

    def test_v_prefix_is_removed_only_for_the_exact_package_requirement(self):
        self.env["INPUT_VERSION"] = "v9.8.7"
        self.run_setup()
        self.assertEqual(self.arguments()[-1], "changenote==9.8.7")

    def test_latest_and_empty_values_do_not_reuse_a_stale_install(self):
        for version in ("latest", ""):
            with self.subTest(version=version):
                self.env["INPUT_VERSION"] = version
                self.calls.unlink(missing_ok=True)
                self.run_setup()
                self.assertEqual(self.arguments()[-1], "changenote")
        paths = self.path_file.read_text().splitlines()
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0], paths[1])

    def test_bare_and_invalid_versions_fail_before_installation_or_activation(self):
        for version in ("9.8.7", "0.1.0", "main", "vlatest", "v1", "v1.2", "v01.2.3",
                        "v1.2.3-beta.1", "v1.2.3+build", "^v1.2.3", ">=v1.2.3",
                        "https://example.invalid/cli", "--root", "v1.2.3\n",
                        "$(touch injected)", "v1.2.3; touch injected"):
            with self.subTest(version=version):
                self.env["INPUT_VERSION"] = version
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("version must be latest or an exact stable version with a v prefix", result.stderr)
                self.assertFalse(self.calls.exists())
                self.assertEqual(self.path_file.read_text(), "")
                self.assertEqual(list(self.runner.iterdir()), [])

    def test_installation_failure_does_not_activate_an_existing_cli(self):
        self.env["MODE"] = "failure"
        result = self.run_setup(ok=False)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.path_file.read_text(), "")

    def test_missing_and_nonexecutable_binaries_are_rejected(self):
        for mode in ("missing", "nonexecutable"):
            with self.subTest(mode=mode):
                self.env["MODE"] = mode
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("executable file", result.stderr)
                self.assertEqual(self.path_file.read_text(), "")

    def test_symlinks_outside_the_tool_environment_are_rejected(self):
        self.env["MODE"] = "outside"
        result = self.run_setup(ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stay inside its tool environment", result.stderr)
        self.assertEqual(self.path_file.read_text(), "")

    def test_mismatched_and_invalid_versions_are_not_activated(self):
        self.env["INPUT_VERSION"] = "v9.8.7"
        for reported in ("changenote 0.0.1", "other 9.8.7", "changenote 9.8.7-beta.1",
                         "changenote 09.8.7", "changenote 9.8.7\nextra"):
            with self.subTest(reported=reported):
                self.env["REPORTED_VERSION"] = reported
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.path_file.read_text(), "")


if __name__ == "__main__":
    unittest.main()
