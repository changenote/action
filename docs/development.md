# Action development

This repository contains the GitHub Actions, not the Rust CLI source.
The CLI and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).

## Repository layout

- `action.yml`: complete root workflow; defaults to compatible managed-merge scripts and also exposes built-in operations.
- `setup/action.yml`: CLI installation with same-job path and exact-version outputs.
- `prepare/action.yml`: project tools and offline caches without PR or publication writes.
- `manage-pr/action.yml`: release PR lifecycle only.
- `select/action.yml`: verified batch identity and separate GitHub publication state.
- `release/action.yml`: compatibility entry point for root's shared built-in operations.
- `check/action.yml`: read-only PR note reports.
- `preview/action.yml`: read-only publication inspection.
- `publish/action.yml`: validated tag and GitHub Release publication.
- `VERSION`: independent Action release version.
- `.changenote/`: release configuration and pending notes for the `action` package.
- `.github/workflows/release.yml`: version PRs and GitHub publication for this repository.
- `scripts/action/`: shared Action implementation and CLI installer.
- `tests/actions/`: local Git/mock GitHub integration tests.
- `tests/action_metadata/`: metadata, installation, and example checks.
- `examples/github-actions/`: consumer workflow templates.

## CLI installation

All public Actions accept `version`; standalone operations install changenote from PyPI through uv unless they receive a trusted same-job `cli-path`.
`/setup` returns `cli-path` and the exact installed `version` for reuse without a second installation.
The default `latest` selects the latest stable published CLI; the repository stores no CLI version or source-revision pin.
Use an exact stable version with the required `v` prefix, such as `v0.9.2`, for repeatable runs.
Bare versions, version ranges, URLs, Git revisions, and prereleases are rejected.
`version` selects the CLI, not the Action's own `VERSION` file.

From the Action repository root, install the latest stable CLI with uv:

```sh
uv tool install --no-config --no-build --default-index https://pypi.org/simple --prerelease disallow changenote
export PATH="$(uv tool dir --bin):$PATH"
changenote --version
```

For an exact version, use `uv tool install --no-config --no-build --default-index https://pypi.org/simple 'changenote==0.9.2'`.
The Action converts `version: 'v0.9.2'` to that package requirement.
CI runs the shared installer with `INPUT_VERSION=latest` before the integration tests.
Tests use the installed executable on `PATH`, not an Action-local Cargo build or a sibling repository.

The Actions set up uv and install a prebuilt wheel into a new runner temporary tool environment.
Root, `/setup`, `/prepare`, and `/release` use `uv-version` for CLI installation and configured uv lockfiles.
It sets up Rust with `rust-toolchain` only when configured Cargo lockfiles require it.
The other Actions do not install Rust for the CLI.
The installer runs outside the consumer checkout, removes GitHub token variables, and disables project configuration, source overrides, source builds, and prereleases.
The selected executable is verified before its directory is added to `GITHUB_PATH`.
Installation failure does not fall back to an executable already on `PATH`.
There is no Action-managed CLI executable cache; default `latest` is resolved on each invocation.
uv setup and wheel installation need network access. A missing version or compatible wheel fails without a Cargo/source-build fallback.

For reproducible version PRs, selection, and publication, use the same exact CLI version in every job.
A reviewed Action SHA alone does not freeze the CLI when `version` is `latest`.
Old CLI versions might not support newer configuration or release data; test the selected version before production use.

## Local checks

Install Bash, Git, `gh`, `jq`, uv, ShellCheck, actionlint, and zizmor.
Run from the repository root after installing changenote:

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
They do not push hosted tags, create hosted Releases, or upload registry packages.
Installer unit tests use a uv stub to check version requirements, consumer isolation, executable links, and failure handling without downloads.
CI retains Rust for Cargo lockfile integration fixtures, not CLI installation.

## Published CLI compatibility

PyPI and crates.io can publish different CLI versions. The default follows PyPI, not crates.io or Git main.
During this change, the latest PyPI release is `0.9.2`, while crates.io provides `0.11.0`.
PyPI `0.9.2` cannot parse Swift `.xcconfig` version files; the three existing Swift integration tests fail with that release.
Do not skip those tests or use a different registry as a silent fallback.
A CLI maintainer must separately publish compatible wheels before the full suite and that feature can pass with this installation route.
Selecting an unpublished version fails; the Action does not build it from Git or Cargo.

## Action releases

This repository uses changenote to release the single `action` package independently of the CLI.
`VERSION` is its version source. Do not copy a CLI release number into it.
The initial `0.0.0` baseline is unreleased; the initial patch note plans `v0.0.1`.

Add notes according to the [Action note policy](../.changenote/README.md), then run `changenote status`.
CI validates the plan with the installed CLI.
The first version PR generates `CHANGELOG.md` and `.changenote/releases.json`, updates `VERSION`, and consumes the initial note.
Those generated files are not created by this setup change.

The repository's Release workflow uses the root `./` Action with an explicit operation after checking out `${{ github.sha }}`.
This runs the Action from the same commit as the checkout, without a separate Action SHA update.
It accepts the `version` input and defaults to `latest`, the latest stable published CLI.
External Action dependencies remain pinned to full commit SHAs.

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
   - If PR CI is required, configure a reviewed GitHub App token or PAT through `github-token`.

Adding or testing this setup does not authorize `changenote version`, `changenote tag`, or a hosted Release run.
To stop release automation, disable the workflow before recovery.
Inspect remote publication state before a retry; never move existing tags or replace published artifacts automatically.
For an unexpected CLI change with `latest`, select an exact version in the caller workflow.

## Action composition verification

Local composition validation passed 184 integration tests and 51 metadata tests on an isolated composition branch with a locally built CLI 0.12.1 wheel.
The fixtures isolate the hosted runner ref; both suites also pass when the parent environment contains a PR merge ref.
The published PyPI 0.9.2 installer remains unchanged; that CLI does not support the existing Swift fixtures.
The compatible local wheel is test evidence, not a source-build fallback or proof that compatible artifacts exist on PyPI.

The nine public Action definitions pass offline zizmor checks.
Exact npm tool installation has a per-step annotation because it intentionally installs the caller's validated tool version without a project lockfile; lifecycle scripts are disabled.
The existing workflow-level Dependabot cooldown and self-repository syntax advisories also occur on the unchanged baseline.
They are not silently treated as a clean workflow security scan.

The example repository's new interfaces remain inactive templates until a maintainer publishes and reviews the new Action SHA.
See [migration and production-pin requirements](migration.md#composable-action-interfaces).
Hosted tools, token scopes, branch rules, and publication still need a separately authorized disposable-repository test.

## Verification limits

Local checks do not verify hosted uv setup, registry access from runners, project tool setup, package caches, fork events, token scopes, branch rules, or deployment approvals.
A maintainer must test these settings in an authorized disposable repository before production use.
No release or remote upload is approved by this guide.
For repository publication order and production pins, see [Migration](migration.md).
