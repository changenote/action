# Action development

This repository contains the GitHub Actions, not the Rust CLI source.
The CLI and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).

## Repository layout

- `action.yml`: root Action for release PRs and optional project publication scripts.
- `release/action.yml`: CLI installation, package-manager setup, and built-in GitHub publication.
- `check/action.yml`: read-only PR note reports.
- `preview/action.yml`: read-only publication inspection.
- `publish/action.yml`: validated tag and GitHub Release publication.
- `VERSION`: independent Action release version.
- `.changenote/`: release configuration and pending notes for the `action` package.
- `.github/workflows/release.yml`: version PRs and GitHub publication for this repository.
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
The CLI and Action have independent release versions and commit SHAs.
A CLI release does not automatically change the Action pin.
Update `CLI_REVISION` and `CLI_VERSION` together after review, then add an Action change note and run the complete suite.

## Local checks

Install Bash, Git, `gh`, `jq`, ShellCheck, actionlint, and zizmor.
Run from the Action repository root after installing the trusted CLI:

```sh
for script in scripts/action/*.sh; do bash -n "$script"; done
shellcheck -x scripts/action/*.sh
actionlint
zizmor --offline .github/
changenote status
uv run --no-project python -m unittest discover -s tests/actions -v
uv run --no-project --with pyyaml python -m unittest discover -s tests/action_metadata -v
```

Tests use temporary consumer repositories and a file-backed GitHub mock.
They do not push remote tags, create hosted Releases, or upload registry packages.
Do not replace the reviewed CLI pin with contributor code for privileged release tests.

## Action releases

This repository uses changenote to release the single `action` package.
`VERSION` is its version source; `cli-source.env` is not an Action version file.
The initial `0.0.0` baseline is unreleased. The initial patch note plans `v0.0.1`.
Do not copy the CLI's release number or change its pin to match the Action version.

Add notes according to the [Action note policy](../.changenote/README.md), then run `changenote status`.
CI validates the plan with the trusted installed CLI.
The first version PR generates `CHANGELOG.md` and `.changenote/releases.json`, updates `VERSION`, and consumes the initial note.
Those generated files are not created by this setup change.

The Release workflow uses a reviewed full SHA of `changenote/action/release` to manage this repository.
This workflow pin is separate from the CLI pin bundled with the Action being developed.
Updating `cli-source.env` does not update the workflow's release tooling automatically.
Review and update each pin separately when needed.
The pinned Action has some tag-based tool dependencies; its SHA does not freeze the complete build toolchain.

On pushes to `main`, `auto` manages the version PR and publishes incomplete validated batches.
Merge the version PR only after review; the following main push publishes its `v<version>` tag and GitHub Release.
The workflow never approves or merges its own PR.
The `/release` Action does not run or wait for project CI; use PR review and branch rules before merging a version PR.
It uploads no registry packages and creates no moving major-version aliases.
Manual runs default to `manage-pr`; select `retry-publication` explicitly to finish an incomplete publication.
Runs are serialized and do not cancel a running release operation.

Before enabling this workflow:

1. Enable **Actions > General > Allow GitHub Actions to create and approve pull requests** in repository settings.
2. Permit the release job to write contents and pull requests and to push the managed release branch.
3. Check the repository's PR review and branch rules.
   - PRs created with the default `GITHUB_TOKEN` do not trigger PR CI automatically.
   - If PR CI is required, configure a reviewed GitHub App token or PAT through the Action's `github-token` input.

Adding or testing this setup does not authorize `changenote version`, `changenote tag`, or a hosted Release run.
Hosted permissions, event delivery, and cache restoration require separate authorized verification.
To stop release automation, disable the workflow before recovery.
Inspect remote publication state before a retry; never move existing tags or replace published artifacts automatically.

## Verification limits

Local tests do not verify hosted cache restoration, tool-install Actions, fork events, token scopes, branch rules, or deployment approvals.
A maintainer must test these settings in an authorized disposable repository before production use.
No release or remote upload is approved by this guide.
For repository publication order and production pins, see [Migration](migration.md).
