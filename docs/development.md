# Action development

This repository contains the GitHub Actions, not the Rust CLI source.
The CLI and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).

## Repository layout

- `action.yml`: one root pipeline; PR-only by default, with optional scripts and explicit tag/Release controls.
- `setup/action.yml`: CLI installation with same-job path and exact-version outputs.
- `prepare/action.yml`: project tools and offline caches without PR or publication writes.
- `manage-pr/action.yml`: release PR lifecycle only.
- `inspect/action.yml`: verified batch identity and read-only GitHub publication inspection.
- `check/action.yml`: read-only PR note reports.
- `publish/action.yml`: validated tag and GitHub Release publication.
- `VERSION`: independent Action release version.
- `.changenote/`: release configuration and pending notes for the `action` package.
- `.github/workflows/release.yml`: version PRs and GitHub publication for this repository.
- `scripts/action/`: shared Action implementation and CLI installer.
- `tests/actions/`: local Git/mock GitHub integration tests.
- `tests/action_metadata/`: metadata, installation, and example checks.

Consumer workflow templates and their checks are in [changenote/example](https://github.com/changenote/example/tree/main/examples/actions).

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
Root, `/setup`, and `/prepare` use `uv-version` for CLI installation and configured uv lockfiles.
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
zizmor --offline .github/ action.yml setup/action.yml prepare/action.yml check/action.yml manage-pr/action.yml inspect/action.yml publish/action.yml
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
Published PyPI CLI `0.13.0` supports Swift `.xcconfig` version files and `changelog.source_repository`.
Use `version: 'v0.13.0'` for reproducible checks of the current integration fixtures.
Older PyPI CLI `0.9.2` does not support these features.
Do not skip tests or use a different registry as a silent fallback.
Selecting an unpublished version fails; the Action does not build it from Git or Cargo.

## Action releases

This repository uses changenote to release the single `action` package independently of the CLI.
`VERSION` is its version source. Do not copy a CLI release number into it.
The initial `0.0.0` baseline is unreleased; the initial patch note plans `v0.0.1`.

Add notes according to the [Action note policy](../.changenote/README.md), then run `changenote status`.
CI validates the plan with the installed CLI.
A version PR updates `VERSION`, writes `CHANGELOG.md`, and consumes notes. Historical CLI writers also save `.changenote/releases.json`; the file-free writer removes that legacy file on its first nonempty release. The Action supports both storage profiles.
Those generated files are not created by this setup change.

The repository's Release workflow uses the root `./` Action with both publication controls explicitly true after checking out `${{ github.sha }}`.
This runs the Action from the same commit as the checkout, without a separate Action SHA update.
It accepts the `version` input and defaults to `latest`, the latest stable published CLI.
External Action dependencies remain pinned to full commit SHAs.

On pushes to `main`, root manages the version PR and completes requested tags and GitHub Releases for validated batches.
Merge the version PR only after review; the following main push publishes its `v<version>` tag and GitHub Release.
The workflow never approves or merges its own PR.
The root Action does not run or wait for project CI; use PR review and branch rules before merging a version PR.
It uploads no registry packages and creates no moving major-version aliases.
Manual workflow choices call standalone `manage-pr`, or prepare and inspect the batch before standalone `publish` with an exact commit guard. These menu choices are not root operations.
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

## Root release controls verification

The candidate starts from `51cbfee2492850a8a5f3e131572c07914dd2f84a` (the previous reviewed Action SHA).
Before edits, the tracked diff was empty (SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
Only the user-supplied plan was untracked. No external consumer pins were changed.

Published PyPI CLI `0.13.0` was tested in a disposable repository without Git worktrees.
With changelog output disabled, the committed metadata-only batch tagged successfully (exit 0).
The annotated `v1.0.1` peeled to release commit `1b2deaafdaac0f28a2169fb206431b86ef47fd5d`; no changelog existed.
`release-notes --package=probe --version 1.0.1` failed (exit 1) because changelog output was disabled.
An initial tag attempt with an untracked probe log failed the clean-tree check; the clean retry above passed.
No upstream change, source installation, or tag-generation fallback is needed.

Validation tools: changenote `0.13.0`, uv `0.13.5`, PyYAML `6.0.3`, jq `1.8.1`, ShellCheck `0.11.0`, actionlint `1.7.11`, and zizmor `1.32.0`.
Missing tools were installed outside the repository.
Bash syntax, ShellCheck, actionlint, offline zizmor, `changenote status`, and `git diff --check` passed.
The 61 non-worktree metadata checks passed locally, including Markdown paths/anchors and YAML example contracts.

[Implementation CI](https://github.com/changenote/action/actions/runs/43598901257) passed 215 integration tests and all 62 metadata tests (both exit 0) at `683d59965ff2874069ccc8f9595bd51e173d6679`.
CI selected published PyPI CLI `0.13.1` through the unchanged `latest` policy; the local compatibility probe used `0.13.0`.
The first CI run found six failures in remaining old-mode fixtures and private token fallback. These were corrected before the passing runs; no required gate was waived.
The full diff was reviewed for correctness, security, lifecycle safety, compatibility, regressions, and scope. Wrong-branch rejection has explicit coverage even with preparation disabled.

The verified source/test diff SHA-256 is `89840be752e6ab886c841d5aa7f591c875a7fa72e84acfbadea7f1d92395bbc1`:

```sh
git diff --binary 51cbfee2492850a8a5f3e131572c07914dd2f84a -- action.yml manage-pr/action.yml scripts/action tests | sha256sum
```

Documentation-only evidence updates do not change this identity.
[PR checks](https://github.com/changenote/action/pull/11/checks) retain complete test results for the final revision.

The full integration suite and the metadata consumer-checkout smoke test create disposable Git worktrees.
They require an authorized runner; this agent session prohibits worktree creation.
Automatic pull-request CI runs both complete suites without hosted publication.
Review its full results, CLI version, exit status, and tested commit before plan completion.
Focused metadata checks can run locally without the consumer-checkout smoke test; these do not replace full CI evidence.

Hosted validation remains a separate handoff to the repository maintainer and registry/project owner.
After separate authorization, use a disposable repository, a reviewed candidate, and owner-configured credentials or Trusted Publishing.
Exercise managed-merge routing, original-run retries, draft PR creation/conversion, selected tag/Release scopes, and an explicitly approved registry upload.
Mocks do not prove event delivery, branch rules, token scopes, hosted tool setup, OIDC, registry ownership, or upload success.
Do not roll out to production or upload registry packages based only on these checks. Do not send secrets through chat.
No release workflow dispatch, version tag, package publication, or external pin migration is authorized.
See [root migration and recovery](migration.md#root-release-controls) and [rollback rules](migration.md#rollback-and-recovery).

## Action composition verification

On 2026-11-14, local verification of the seven-entry refactor passed 188 integration tests and 55 metadata tests with published CLI `0.13.0`.
Bash syntax, ShellCheck, actionlint 1.7.11, changenote status, local Markdown links, and offline zizmor checks passed.
The security scan uses the explicit annotations described below; hosted behavior remains unverified.

Historical composition validation passed 184 integration tests and 51 metadata tests with an isolated CLI 0.12.1 wheel.
The fixtures isolate the hosted runner ref; both suites also pass when the parent environment contains a PR merge ref.
[Hosted composition CI](https://github.com/changenote/action/actions/runs/43580500104) subsequently passed both suites with published PyPI CLI `0.13.0`.
The production installer remains wheel-only and has no source-build fallback.

Audit the seven public Action definitions and repository workflows with offline zizmor.
Exact npm tool installation has a per-step annotation because it intentionally installs the caller's validated tool version without a project lockfile; lifecycle scripts are disabled.
Dependabot uses a seven-day cooldown.
Repository-local Action calls have explicit self-repository audit annotations: the workflow checks out the exact event SHA with no persisted credentials, and required actionlint does not support the suggested `$/` syntax.
Contract tests check that these local calls use the reviewed checkout and do not run preparation commands from an untrusted download. These annotations do not waive other security checks.

The example repository has a pinned root workflow and inactive composition templates.
Production pin updates still require a reviewed, published Action SHA.
See [migration and production-pin requirements](migration.md#composable-action-interfaces).
Hosted tools, token scopes, branch rules, and publication still need a separately authorized disposable-repository test.

## Source-link rollout

Source-link contract tests require a CLI with `changelog.source_repository` support.
Published PyPI CLI `0.13.0` provides this feature; use the same exact `version: 'v0.13.0'` for PR generation, selection, and publication.
Run the Action test suites with that installed executable on `PATH`.
Unreleased CLI features can be tested locally with an isolated wheel built from a reviewed CLI revision.
Local feature wheels do not change the production installer or add a source fallback.

Enabling the setting remains a separate configuration change that requires authorization.
No Action production-code change or new permission is needed for source rendering.
Local mocks do not verify hosted event delivery, token scopes, branch rules, registry access, or actual publication.
Validate those paths in an authorized disposable repository before production rollout; do not treat local completion as release approval.

Before downgrading tooling, remove the setting if no batch has been generated.
For an existing batch, keep compatible tooling and its historical configuration; do not edit generated links to force replay to pass.
See the CLI [rollout and recovery rules](https://github.com/changenote/changenote/blob/main/docs/development.md#source-link-rollout).

## Verification limits

Local checks do not verify hosted uv setup, registry access from runners, project tool setup, package caches, fork events, token scopes, branch rules, or deployment approvals.
A maintainer must test these settings in an authorized disposable repository before production use.
No release or remote upload is approved by this guide.
For repository publication order and production pins, see [Migration](migration.md).
