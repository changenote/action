"""Exercise registry installation with a Cargo stub; never build consumer code."""

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
        (self.consumer / ".cargo").mkdir(parents=True)
        (self.consumer / ".cargo/config.toml").write_text("invalid consumer config\n")
        (self.consumer / "Cargo.toml").write_text('build = "build.rs"\n')
        (self.consumer / "build.rs").write_text('compile_error!("must not build consumer");\n')
        (self.consumer / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "not-selected"\n')
        self.runner = self.top / "runner temp"
        self.runner.mkdir()
        self.bin = self.top / "bin"
        self.bin.mkdir()
        self.calls = self.top / "calls"
        self.path_file = self.top / "path"
        self.path_file.write_text("")
        stub = self.bin / "cargo"
        stub.write_text(
            '#!/usr/bin/env bash\nset -eu\n'
            'printf "%s\\0" "$@" >> "$CALLS"\n'
            'printf "%s" "$RUSTUP_TOOLCHAIN" > "$CALLS.toolchain"\n'
            'pwd > "$CALLS.cwd"\n'
            'printf "%s|%s|%s" "${GH_TOKEN-unset}" "${GITHUB_TOKEN-unset}" '
            '"${INPUT_GITHUB_TOKEN-unset}" > "$CALLS.tokens"\n'
            '[[ ${MODE:-} != failure ]] || exit 7\n'
            'while [[ $# -gt 0 ]]; do\n'
            '  if [[ $1 == --root ]]; then root=$2; shift; fi\n'
            '  shift\ndone\n'
            '[[ ${MODE:-} != missing ]] || exit 0\n'
            'mkdir -p "$root/bin"\n'
            'printf "%s\\n" \'#!/usr/bin/env bash\' '
            '\'printf "%s\\n" "${REPORTED_VERSION:-changenote 9.8.7}"\' > "$root/bin/changenote"\n'
            '[[ ${MODE:-} != nonexecutable ]] || exit 0\n'
            'chmod +x "$root/bin/changenote"\n'
            'if [[ ${MODE:-} == symlink ]]; then\n'
            '  mv "$root/bin/changenote" "$root/binary"\n'
            '  ln -s "$root/binary" "$root/bin/changenote"\nfi\n'
        )
        stub.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                        RUNNER_TEMP=str(self.runner), GITHUB_PATH=str(self.path_file),
                        CALLS=str(self.calls), GH_TOKEN="must-not-leak",
                        GITHUB_TOKEN="must-not-leak", INPUT_GITHUB_TOKEN="must-not-leak")
        for key in ("INPUT_VERSION", "INPUT_RUST_TOOLCHAIN", "REPORTED_VERSION", "MODE"):
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
        return result

    def arguments(self):
        return self.calls.read_bytes().decode().split("\0")[:-1]

    def test_default_installs_latest_from_crates_io_outside_consumer(self):
        self.run_setup()
        directory = Path(self.path_file.read_text().strip()).parent
        self.assertEqual(directory.parent, self.runner)
        self.assertEqual(self.arguments(), [
            "install", "--registry", "crates-io", "--locked", "--root", str(directory),
            "changenote",
        ])
        self.assertEqual(Path(str(self.calls) + ".cwd").read_text().strip(), str(directory))
        self.assertEqual(Path(str(self.calls) + ".toolchain").read_text(), "stable")
        self.assertEqual(Path(str(self.calls) + ".tokens").read_text(), "unset|unset|unset")
        self.assertFalse((self.consumer / "target").exists())

    def test_exact_version_is_not_a_semver_range(self):
        for version in ("9.8.7", "v9.8.7"):
            with self.subTest(version=version):
                self.calls.unlink(missing_ok=True)
                self.env.update(INPUT_VERSION=version, INPUT_RUST_TOOLCHAIN="1.85.0")
                self.run_setup()
                args = self.arguments()
                self.assertEqual(args[args.index("--version") + 1], "=9.8.7")
                self.assertEqual(Path(str(self.calls) + ".toolchain").read_text(), "1.85.0")

    def test_latest_and_empty_values_do_not_reuse_a_stale_install(self):
        for version in ("latest", ""):
            with self.subTest(version=version):
                self.env["INPUT_VERSION"] = version
                self.calls.unlink(missing_ok=True)
                self.run_setup()
                self.assertNotIn("--version", self.arguments())
        paths = self.path_file.read_text().splitlines()
        self.assertEqual(len(paths), 2)
        self.assertNotEqual(paths[0], paths[1])

    def test_invalid_versions_fail_before_installation_or_activation(self):
        for version in ("main", "vlatest", "1", "1.2", "01.2.3", "1.2.3-beta.1", "1.2.3+build",
                        "^1.2.3", ">=1.2.3", "https://example.invalid/cli", "--root", "1.2.3\n",
                        "$(touch injected)", "1.2.3; touch injected"):
            with self.subTest(version=version):
                self.env["INPUT_VERSION"] = version
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("version must be latest or an exact stable version", result.stderr)
                self.assertFalse(self.calls.exists())
                self.assertEqual(self.path_file.read_text(), "")
                self.assertEqual(list(self.runner.iterdir()), [])

    def test_installation_failure_does_not_activate_an_existing_cli(self):
        self.env["MODE"] = "failure"
        result = self.run_setup(ok=False)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.path_file.read_text(), "")

    def test_missing_nonexecutable_and_symlinked_binaries_are_rejected(self):
        for mode in ("missing", "nonexecutable", "symlink"):
            with self.subTest(mode=mode):
                self.env["MODE"] = mode
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("regular executable file", result.stderr)
                self.assertEqual(self.path_file.read_text(), "")

    def test_mismatched_and_invalid_versions_are_not_activated(self):
        self.env["INPUT_VERSION"] = "9.8.7"
        for reported in ("changenote 0.0.1", "other 9.8.7", "changenote 9.8.7-beta.1",
                         "changenote 09.8.7", "changenote 9.8.7\nextra"):
            with self.subTest(reported=reported):
                self.env["REPORTED_VERSION"] = reported
                result = self.run_setup(ok=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.path_file.read_text(), "")


if __name__ == "__main__":
    unittest.main()
