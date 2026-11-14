# Action development

This repository contains the GitHub Actions, not the Rust CLI source.
The CLI and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).

## Repository layout

- `action.yml`: root Action for release PRs and optional project publication scripts.
- `release/action.yml`: CLI installation, package-manager setup, and built-in GitHub publication.
- `check/action.yml`: read-only PR note reports.
- `preview/action.yml`: read-only publication inspection.
- `publish/action.yml`: validated tag and GitHub Release publication.
- `cli-source.env`: trusted CLI repository, full revision, and expected version.
- `scripts/action/`: shared Action implementation.
- `tests/actions/`: local Git/mock GitHub integration tests.
- `tests/action_metadata/`: Action metadata, setup, and example checks.
- `examples/github-actions/`: consumer workflow templates.

## Trusted CLI installation

Run from the Action repository root with Rust, Cargo, and uv installed:

```sh
source ./cli-source.env
cargo install --git "$CLI_REPOSITORY" --rev "$CLI_REVISION" --locked
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
test "$(changenote --version)" = "changenote $CLI_VERSION"
```

The current metadata selects:

| Variable | Value |
| --- | --- |
| `CLI_REPOSITORY` | `https://github.com/changenote/changenote` |
| `CLI_REVISION` | `c644511a48a4c09a72b1d7a7b58dc6d6d8f374f5` |
| `CLI_VERSION` | `0.11.0` |

CI installs this exact pin before the integration tests.
Tests use the installed `changenote` executable on `PATH`, not an Action-local Cargo build or a sibling CLI checkout.
The `/release` Action uses the same metadata with `cargo install --git`, `--rev`, and `--locked`.
It still installs the selected Rust toolchain and caches the executable.
It does not compile Action source or contributor PR source as the CLI.

Treat `cli-source.env` as trusted executable shell input. Source only a reviewed Action checkout.
When changing the pin, review the CLI revision and confirm its version, then run the complete Action suite.
Keep the CLI and Action release versions equal. Their repositories have separate commit SHAs.

## Local checks

Install Bash, Git, `gh`, `jq`, ShellCheck, actionlint, and zizmor.
Run from the Action repository root after installing the trusted CLI:

```sh
for script in scripts/action/*.sh; do bash -n "$script"; done
shellcheck -x scripts/action/*.sh
actionlint
zizmor --offline .github/
uv run --no-project python -m unittest discover -s tests/actions -v
uv run --no-project --with pyyaml python -m unittest discover -s tests/action_metadata -v
```

Tests use temporary consumer repositories and a file-backed GitHub mock.
They do not push remote tags, create hosted Releases, or upload registry packages.
Do not replace the reviewed CLI pin with contributor code for privileged release tests.

## Verification limits

Local tests do not verify hosted cache restoration, tool-install Actions, fork events, token scopes, branch rules, or deployment approvals.
A maintainer must test these settings in an authorized disposable repository before production use.
No release or remote upload is approved by this guide.
For repository publication order and production pins, see [Migration](migration.md).
