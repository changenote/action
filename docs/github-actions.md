# GitHub release Actions

Choose an entry point for your workflow:

| Goal | Guide |
| --- | --- |
| Install tools and publish tags and GitHub Releases | [Config-driven publication](#config-driven-github-publication) |
| Run project-owned publication scripts after a verified merge | [Root Action](#root-action-post-merge-commands) |
| Validate the release commit in separate CI jobs | [External CI and artifacts](#external-ci-and-artifacts-logice-example) |
| Manage separate release operations and project tool setup | [Lower-level Actions](github-actions-reference.md) |
| Check contributor PR notes without publication | [PR note checks](checks.md#github-action-report) |

Built-in publication creates Git tags and GitHub Releases, not registry artifacts.
Keep changelog output enabled for built-in publication.
The CLI repository owns its [release routing and registry setup](https://github.com/changenote/changenote/blob/main/docs/development.md#repository-release-workflow).
For CLI installation and local checks, see [Development](development.md).
For the repository move and production cutover, see [Migration](migration.md).

## Root operations and reusable Actions

Use the root for a complete workflow, or compose single-purpose Actions for separate jobs, permissions, external CI, and approvals.
The root accepts only `hooks` and `auto`. Its default remains `hooks`, with no built-in publication.
Set `operation: auto` explicitly for PR management and built-in GitHub publication on push.
Both modes only manage the PR on manual events.

| Entry point | Responsibility |
| --- | --- |
| Root | Event policy, PR orchestration, follow-up work, and error handling. |
| `/setup` | Install the CLI and return its exact `version` and same-job `cli-path`. |
| `/prepare` | Prepare project tools and offline caches; create no PRs, tags, or Releases. |
| `/manage-pr` | Generate version changes and manage the Release PR, without merging or publishing. |
| `/check` | Check contributor PR note coverage without writes. |
| `/inspect` | Verify the latest committed batch and inspect GitHub publication state without writes. |
| `/publish` | Revalidate the batch and create Git tags and GitHub Releases, not registry uploads. |

Each standalone operation can install its CLI.
To reuse one installation, run `/setup` once and pass its trusted `cli-path` to subsequent Actions in the same job.
The path must be absolute, executable, and named `changenote`; never take it from contributor data.
An exact `version` must match that executable.
With `version: latest` and an explicit path, the installed stable version is validated without resolving PyPI again.
Paths do not transfer between jobs. Use the same exact CLI and project tool versions across jobs.

`/prepare` uses `operation` only as an environment scope: `manage-pr` for pending notes, `inspect` or `publish` for the saved batch, and `auto` for both.
The `publish` scope requires `expected-release-commit`; other scopes reject that guard.
Preparation does not execute the named release operation.
Root's `auto` prepares tools by default; on manual events it prepares only pending PR work.
Set root `prepare: 'false'` after caller-owned preparation, including a previous `/prepare` step.
Root's `hooks` retains caller-owned project setup.

Custom `publish-script` and `release-script` inputs require `hooks`.
Use standalone Actions for individual operations and publication retries.
For removed interfaces and coordinated pin updates, see [Migration](migration.md#composable-action-interfaces).

## Root Action: post-merge commands

Use `changenote/action@<full-action-commit-sha>` to manage version PRs and run optional project commands after a managed PR is merged.
See [the command-hook workflow](../examples/github-actions/command-hooks.yml).
Replace all SHA placeholders with reviewed compatible full commit SHAs.
The root Action needs Bash, Git, `gh`, `jq`, and Python 3 on Linux. Ubuntu runners provide these tools.
It sets up uv and installs a CLI wheel from PyPI using `version`. CLI installation needs no Rust toolchain.
The default `hooks` operation does not prepare the project's runtime or dependencies.
Prepare supported lockfile tools and caches for PR generation and release replay as described in [automatic lockfile synchronization](https://github.com/changenote/changenote/blob/main/docs/configuration.md#automatic-lockfile-synchronization).
Never build the trusted CLI from a contributor PR.

The existing inputs `github-token`, `base-branch`, `commit-message`, and `pr-title` retain their defaults.
The token needs contents and pull requests write permissions for PR management, including read access for merge association.
`base-branch` defaults to the repository default branch.
The Action never approves or merges its PR.
If generated PRs must start CI, use a GitHub App token or PAT through `github-token`; the default workflow token does not start PR workflows.

| Optional input | Default | Execution |
| --- | --- | --- |
| `version` | `latest` | Install the latest stable CLI from PyPI, or an exact version with a required `v` prefix, such as `v0.9.2`. |
| `publish-script` | Empty | Publish packages after managed-merge and full-tree verification. |
| `release-script` | Empty | Create tags, assets, or a GitHub Release after successful `publish-script`, or directly if it is absent. |

Both script inputs accept Bash script text. Whitespace-only input is absent.
For example, use `publish-script: uv publish` for prepared Python artifacts or `publish-script: cargo publish --locked` for a prepared crate.
A project script can test, build, and upload in one command.
With both inputs, the fixed order is **publish, then release**. With one input, only that command runs.
In `hooks`, neither input means no tags, GitHub Releases, or registry uploads.
There are no built-in registry integrations or command-order options.

On a normal base-branch push, the router checks only new batch-changing first-parent commits in that push range.
It selects the latest batch and requires exactly one associated merged PR with the reserved same-repository release branch, selected base, managed body marker, and matching merge commit.
Titles and commit messages do not authorize command execution.
Merge, squash, and rebase merges are supported.
Contributor PR events, wrong branches, forced/deleted pushes, missing history, invalid associations, and API failures stop the root Action before commands.
In `hooks`, manual `workflow_dispatch` only manages the PR, regardless of script inputs.
An unrelated later push does not run commands for an old batch.
If one push contains multiple release batches, only the latest is selected; finish one release before merging the next.

Before execution, the Action reconstructs the consumed-note plan and checks the complete generated tree.
It fetches the base branch again after reconstruction and rejects a changed batch selection.
It does not switch silently to another release commit.
This check does not reserve the branch against a later merge.
GitHub tag/Release state does not decide whether commands run. Changelog output can be disabled.
Historical note-bearing batches remain read-only; custom commands are rejected for them.
The stricter [legacy, changelog-body, and remote-publication rules](github-actions-reference.md#publication-workflow) of `/inspect` and `/publish` remain unchanged.

Commands run once per batch per eligible invocation in a disposable worktree at the verified release commit.
They share generated files between commands and have an `origin` remote without stored management credentials.
Commands must not change HEAD; a changed HEAD prevents the next command.
Git pushes need caller-provided Git authentication; setting `GH_TOKEN` alone does not configure a Git credential helper.
The caller's tracked files, index contents, HEAD, and Git identity are not replaced by the hook runner.
PR management retains its normal fetch behavior.
Untracked files from earlier workflow steps are not copied into that worktree.
Build artifacts there, or explicitly use an artifact directory downloaded by the workflow.
Temporary trees are removed after success or failure, so retain artifacts before the command exits if retries require identical bytes.

Both commands receive:

- `CHANGENOTE_RELEASE_COMMIT`: the verified full commit SHA.
- `CHANGENOTE_RELEASES`: a compact JSON array with `package`, `version`, and `tag` for every package in the batch.
  - Read this array for a monorepo. There is no single global version variable.

The caller supplies trusted command text, runtimes, dependencies, artifacts, credentials, and job permissions.
Do not construct command inputs from PR titles, notes, or other contributor data.
The `github-token` input is not automatically exported to commands.
Pass needed credentials explicitly through the Action step's `env`, such as `GH_TOKEN` for a caller-owned GitHub Release script or the registry's required variable.
A command runs with the job's authority. This is not a security sandbox, and caller-provided secrets remain accessible to trusted code.
Grant `id-token: write` only when the configured publication method needs it.

Project tests, artifact checks, and a package dry run must pass before an upload.
The publication script can enforce those checks at the verified commit.
Metadata verification is not proof that project CI passed.
For separate CI jobs, native runners, independent deployment approvals, or cross-platform artifacts, keep the external-CI structure below rather than compress it into a single command job.
A composite Action cannot set job concurrency or call a reusable workflow as a job.
Configure caller concurrency with `cancel-in-progress: false`, but do not treat it as a durable FIFO queue: newer pending runs can replace older pending runs.

The root retains `has-notes`, `pr-number`, and `pr-operation` outputs.
It adds `release-commit` and `releases` for the verified merged batch, even when both commands are absent.
No selected merge returns an empty commit and `[]`.
Read outputs only after a successful Action step; command success alone does not prove publication state.
A PR-maintenance failure does not suppress an independently verified merged batch, but the Action still reports failure.

### Hook retries and migration

A command failure fails the Action. A failed `publish-script` prevents `release-script`.
The Action does not retry commands or undo external writes.
Re-running the original eligible workflow repeats configured commands from the beginning, even when a GitHub Release already exists.
Scripts must handle already-published versions and partial uploads safely.
If a newer release batch has replaced the selected batch, the old run fails instead of publishing a different version.
Inspect state and recover explicitly; do not move tags or replace published packages automatically.

Replace `publish-command` with `publish-script` and `release-command` with `release-script` in workflows.
The old input names are not supported. Script text, execution order, and empty defaults are unchanged.

Consumers of the older root Action must restrict invocation to base-branch `push` and `workflow_dispatch` events.
Do not use the root on contributor PRs. Use `/check` for read-only note checks.
Standalone operation Actions install the CLI unless a trusted `cli-path` is supplied. Separate caller installation is not required.
Use the `version` input when an exact CLI version is required; otherwise each invocation resolves `latest`.
Both commands are opt-in; upgrading without command inputs does not enable package or GitHub publication.
Consumers of removed entry points must migrate their workflow and Action SHA together; see [Migration](migration.md#composable-action-interfaces).
No consumer or production workflow is migrated by these examples.

### Hosted handoff and recovery

Local Git/mock tests do not establish release readiness.

| Responsible role | Prerequisite and action | Expected result and unverified path | Restriction |
| --- | --- | --- | --- |
| Repository maintainer | After separate authorization, configure a disposable repository, reviewed Action SHA, branch rules, token, and environments. Merge a managed PR, then re-run its original workflow. | Confirm hosted event delivery, merge association, command order, token scopes, branch permissions, and pending-run behavior. | Do not test with a production Release workflow. |
| Registry/project owner | After artifact review and specific upload authorization, configure credentials or Trusted Publishing and perform a controlled upload followed by the project release step. | Confirm registry ownership, OIDC configuration, deployment approvals, and actual publication. | Dummy-command tests authorize no upload. Never send secrets through chat. |

To stop custom publication, disable the consumer workflow or remove both commands; cancel active runs separately.
Restore the previous reviewed Action SHA and matching workflow to roll back code.
Do not edit saved release batches or move existing tags.
After a partial upload, inspect registry, tag, and Release state before retrying.
Reuse original artifacts if rebuilt bytes would conflict. Fix a faulty published package with a new version.
Yanks and asset removal require separate maintainer authorization.

## Config-driven GitHub publication

Use the root with `operation: auto` for PR management and built-in GitHub publication.
Keep package settings in `.changenote/config.json`. Select workflow behavior and tool versions with Action inputs.
Use `/setup`, `/prepare`, `/manage-pr`, `/inspect`, and `/publish` for separate stages.

## Minimal workflow

Copy [the minimal workflow](../examples/github-actions/release.yml) to `.github/workflows/release.yml`.
Replace its SHA placeholder with a reviewed full Action commit SHA.
No separate CLI version pin, Rust installation, or publication script is needed.

The explicitly selected `auto` operation manages the Release PR and publishes incomplete validated batches on ordinary pushes.
It can complete an older batch after later pushes, like the lower-level publication Action.
It does not require a new batch in the current push or an associated merged managed PR.
It does not run project CI.
Use the separate operations below when CI must validate the exact release commit before publication.

The workflow menu defaults to `manage-pr` and calls the standalone PR Action after preparation.
Its `retry-publication` choice prepares and inspects the latest batch, then calls standalone `publish` with the inspected commit. These are workflow choices, not root operations.
The Action never merges its PR.

Before use:

1. Create and commit the package configuration and version files.
2. Enable **Actions > General > Allow GitHub Actions to create and approve pull requests**.
3. Permit the bot to push the managed release branch.
4. If Release PRs must trigger CI, pass a GitHub App token or PAT through `github-token`.
   - PRs created with the default `GITHUB_TOKEN` do not automatically trigger PR workflows.
5. Use Ubuntu runners and the selected base branch for push and manual events.
   - Contributor PR events, forced pushes, and deleted-branch pushes are rejected.

Repository settings and token permissions cannot be supplied by package configuration.
Do not merge another Release PR until the current batch and downstream artifacts are complete.

## Change source links

Release PR details use the CLI's rendered note sections.
To include commit links, use the published CLI with `version: 'v0.13.0'` and set `changelog.source_repository` in `.changenote/config.json` to a canonical `https://github.com/<owner>/<repo>` URL.
No new Action input or GitHub permission is needed.
The CLI reads local first-parent note history, follows actual renames, and includes creation and later edits in a stable order.
A `Sources:` paragraph precedes each note summary; verified Markdown PR links in the summary remain unchanged.
These commits identify note edits, not necessarily the complete implementation. PR lookup is not automatic.

Use the same exact compatible CLI version for PR generation, inspection, and publication.
The Action prepares complete base-branch history; source-enabled versioning rejects uncommitted notes or unprovable history before writes.
Historical replay uses the selected release parent's configuration and history, even after the live URL or checkout remote changes.
Complete-tree verification is unchanged. GitHub Release bodies come from the verified changelog without another source lookup.
With changelog output disabled, PR details can show links, but inspection and publication remain unsupported before remote writes.
See the CLI [source-link rules](https://github.com/changenote/changenote/blob/main/docs/notes.md#automatic-commit-source-links) and [rollout limits](development.md#source-link-rollout).

## Tool setup

Each Action accepts `version`. Standalone operation Actions install a prebuilt CLI wheel from PyPI with `uv tool install`, unless `cli-path` reuses an installation.
The `version` input defaults to `latest`, the latest stable published PyPI version.
An exact version must have a `v` prefix, such as `v0.9.2`; it selects the requirement `changenote==0.9.2`.
Bare versions, ranges, Git revisions, URLs, and prereleases are rejected before installation.
The Action verifies the installed version before adding it to `PATH`; it never falls back to a caller-installed CLI after failure.

Installation runs in a new runner temporary directory, not the consumer checkout.
uv uses an isolated tool environment with project configuration, source overrides, and source builds disabled.
GitHub token variables are removed from installation.
The `uv-version` input selects uv for root, `/setup`, and `/prepare` installation and supported project uv lockfiles.
The `rust-toolchain` input is only used when configured Cargo lockfiles require Rust.
There is no Action-managed executable cache; `latest` is resolved again for each invocation.
Installation needs access to uv distribution servers and PyPI, and a compatible wheel must exist.
CI tests the latest published CLI; see [Development](development.md#cli-installation).
Use the same exact `version` across PR generation, selection, and publication when reproducible replay is required.

For each release operation, the Action reads validated configuration in temporary checkouts.
It discovers primary and additional manifest outputs, then finds their nearest supported lockfile.
Shared lockfiles are prepared once per revision.
Plain-text versions, manifests without lockfiles, and inactive release plans need no package-cache preparation.

Selection and publication use the selected batch's parent configuration and only its consumed notes, not the complete pending parent plan.
Retained notes do not add unrelated package tools or downloads to that batch.
Automatic operation also prepares the current pending PR plan.
This supports historical releases after configuration changes.

| Manifest with existing lockfile | Cache preparation |
| --- | --- |
| `Cargo.toml` | `cargo fetch` |
| `package.json` | `npm install --ignore-scripts --no-audit --no-fund` |
| `pyproject.toml` | `uv sync --no-install-project --no-install-workspace --no-build` |

Preparation runs online in temporary checkouts and can refresh their temporary lockfiles.
This supports historical batches whose manifest versions changed without lockfile synchronization.
The selected Rust toolchain overrides consumer toolchain files for setup and replay.
uv uses a private temporary environment, not the consumer's configured environment or `.venv` symlink.
Version writes and publication replay retain their offline commands.
npm lifecycle scripts are disabled. uv project installation and source builds are disabled.
Preparation does not change the consumer checkout.
The Action removes `GH_TOKEN` and `GITHUB_TOKEN` from package-cache commands.
Configure private package credentials through the package manager's normal configuration.
Do not depend on the Action's write token for dependency downloads.

Use the same Node.js, npm, Rust, and uv versions for PR generation, selection, and publication.
Version differences can change lockfiles and cause full-tree verification to fail.
Pin tool versions when reproducible lockfiles are required.
The existing restrictions on unsupported lockfiles and dynamic manifest versions still apply.

## Operations and inputs

| Root `operation` | Behavior | Token permissions |
| --- | --- | --- |
| `hooks` (default) | Manage the PR and run optional scripts for a verified managed merge in the triggering push. Manual runs only manage the PR. | Contents write, pull requests write |
| `auto` | On push, manage the PR and publish incomplete validated work. Manual runs only manage the PR. | Contents write, pull requests write |

Root owns PR execution once per run and the final PR failure status.
Invalid hook routing stops before PR writes.
A PR-management failure does not suppress eligible verified follow-up work; the run still reports the PR error.
In `auto`, current-plan preparation failure does not suppress historical publication.
CLI installation, required tool installation, and historical-environment failures stop the Action.
Use separate jobs if downstream work must be independent of PR-management failure.

| Input | Default | Rule |
| --- | --- | --- |
| `version` | `latest` | Stable PyPI CLI version; exact versions require a `v` prefix. |
| `github-token` | `github.token` | Contents and pull requests write for root and PR management. Inspection needs only contents read; publication needs contents write. |
| `base-branch` | Repository default branch | Root and preparation must run on this branch. |
| `cli-path` | Empty | Reuse the trusted same-job executable returned by `/setup`; otherwise install `version`. |
| `prepare` | `true` | Root prepares project tools for `auto`; set `false` after caller-owned preparation. |
| `node-version` | `lts/*` | Node.js for configured npm lockfiles. |
| `npm-version` | Bundled npm | Optional exact stable npm version. |
| `rust-toolchain` | `stable` | Toolchain for configured Cargo lockfiles. |
| `uv-version` | setup-uv default | uv for CLI installation and configured uv lockfiles. |
| `commit-message` | `chore(release): version packages` | Generated release commit message. |
| `pr-title` | `chore(release): version packages` | Managed PR title. |
| `publish-script`, `release-script` | Empty | Trusted Bash scripts, only for root `hooks`. |

Standalone `publish` accepts optional `expected-release-commit`, a full lowercase 40-character SHA.
Use it after external CI to prevent a changed release target from being published.
Omitting it retains latest-batch publication.
The guarded `publish` preparation scope requires the same input.
Root accepts neither this guard nor a retry flag.
All publication paths repeat full-tree replay, changelog validation, conflict detection, and remote race checks.

## Outputs

Read outputs only after a successful Action step, except documented failure reports from `check` and `inspect`.

- `release-commit`: the selected verified commit, or empty.
  - `inspect` returns completed batches as well as incomplete batches.
  - Root `auto` returns pending publication work only; manual runs return no batch.
  - Root `hooks` returns the verified managed merge independently of configured scripts.
- `releases`: compact JSON for every package in the batch:

  ```json
  [{"package":"logice","version":"1.2.3","tag":"v1.2.3"}]
  ```

- `published`: whether this run created a remote tag or GitHub Release.
- `published-packages`: only packages changed remotely during this run.
- `publication-plan`: inspected GitHub publication work, from `inspect` or root `auto` on push.
- `publication-needed`: whether GitHub publication is incomplete. Gate automatic work with this value, not commit presence. Registry work has separate completion state.
- `ready`: whether inspection or publication completed without conflicts. It is not a CI result or authorization for another publishing system.
- `has-notes`, `pr-number`, `pr-operation`: PR-management results.

Root retains all these output names.
In `hooks`, `published` and `ready` remain false because trusted scripts do not inspect GitHub publication state.
PR management alone does not set `ready` to true.
Standalone `publish` returns `release-commit`, `releases`, `published`, and `published-packages`.

## External CI and artifacts: Logice example

Use [the Logice-style workflow](../examples/github-actions/logice-release.yml) when external CI must validate the selected commit.
This is a migration example, not a modification to the Logice repository.

Its single package configuration needs no new fields:

```json
{
  "packages": {
    "logice": {
      "path": ".",
      "version_file": "VERSION",
      "version_outputs": ["web/package.json"],
      "tag_prefix": "v"
    }
  }
}
```

The workflow keeps these boundaries:

1. `/setup` and `/prepare` prepare the tools, then `/inspect` returns the verified batch with read-only GitHub permissions.
   - Automatic CI is gated by `publication-needed`; explicit manual retries can include completed work.
2. The existing reusable CI workflow validates that exact `revision`.
3. `manage-pr` runs independently with PR-write permissions.
4. `publish` receives the CI-selected `expected-release-commit`.
   - If the latest remote batch changes, publication stops before remote writes.
   - It does not silently switch to the newer batch.
5. The existing Docker workflow receives the verified commit and tag from `releases`.
   - The example uses the first entry because Logice has one release package.
   - For multiple packages, select the package explicitly before building artifacts.

The consumer no longer needs a local setup-changenote Action, cache shell commands, internal script paths, or VERSION parsing.
It still needs its own CI and Docker workflows with `workflow_call` inputs `revision` and `version-tag`.
Keep those jobs separate to preserve permission and validation boundaries.

Explicit manual retries use the same selected batch even when GitHub publication is complete.
This reruns CI and downstream artifact publication even if GitHub publication reports `published=false`.
Existing release text and tags are not replaced.

## Verification limits

Local tests cover operation routing, source isolation, setup commands, metadata, and publication guards.
Linux container tests use real Git repositories and a mocked GitHub API.
Hosted tool installation, package-cache behavior, fork settings, token permissions, and branch rules still need a disposable-repository test.
No hosted publication or registry upload is authorized by these examples.
