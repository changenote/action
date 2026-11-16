# Lower-level GitHub Actions

Use these Actions when the workflow manages separate release operations and project package-manager setup.
Each operation installs the CLI selected by `version`, or reuses a trusted same-job `cli-path` returned by `/setup`.
Use `/prepare` for project tools and offline caches; `/manage-pr`, `/inspect`, and `/publish` perform separate operations.
Root manages PRs by default and enables scripts, tags, and Releases through explicit inputs. It has no `operation` input.
Use standalone Actions for individual operations; `/prepare` scopes are unchanged.
For automatic setup, use root's [config-driven release operations](github-actions.md#config-driven-github-publication).
For project-owned publication scripts, use the [root Action guide](github-actions.md#root-action-post-merge-commands).

- [Requirements](#requirements)
- [CLI setup](#cli-setup)
- [Environment preparation](#environment-preparation)
- [Release PR workflow](#release-pr-workflow)
- [Publication inspection](#publication-inspection)
- [Publication workflow](#publication-workflow)
- [Inputs and outputs](#inputs-and-outputs)
- [Recovery and limits](#recovery-and-limits)

For contributor PRs, use the read-only [check Action](checks.md#github-action-report).

## Requirements

The Release PR and publication Actions require Linux, Bash, Git, `gh`, `jq`, and a clean checkout.
Ubuntu GitHub-hosted runners include these tools.
Each Action sets up uv and installs a prebuilt changenote wheel from PyPI.
`version` defaults to `latest`; use an exact stable version with a required `v` prefix, such as `v0.9.2`, for reproducible runs.

- Run at the repository root.
  - Action scripts come from the Action checkout, not the consumer repository.
- Package version files, lockfiles, changelogs, and `.changenote/releases.json` must not be symlinks.
  - Both writing Actions check the batch path before CLI writes.
- For standalone operations, use the same project tool versions as preparation. Set `RUSTUP_TOOLCHAIN` explicitly when it must override checked-in Rust toolchain files.
- Prepare the package managers and cached dependencies required by [lockfile synchronization](https://github.com/changenote/changenote/blob/main/docs/configuration.md#automatic-lockfile-synchronization).
  - The CLI updates configured primary and additional version files and supported existing lockfiles, not unlisted manifests.
- Select a CLI version compatible with the reviewed Action SHA.
  - The CLI version and Action commit SHA are different values.
  - Use the same exact `version` across PR generation, inspection, and publication to avoid changes between jobs.

## CLI setup

Use [Setup](../setup/README.md) to install the CLI without a consumer checkout or GitHub token.
Installation uses a prebuilt PyPI wheel in an isolated temporary tool environment and adds the verified executable to `PATH`.
Network access to uv distribution servers and PyPI is required; no compatible wheel means failure, not a Rust or source-build fallback.
The Action does not cache the CLI executable between invocations.
See [CLI installation](development.md#cli-installation) for isolation and compatibility details.

| Input | Default | Behavior |
| --- | --- | --- |
| `version` | `latest` | Latest stable PyPI CLI, or an exact stable version with a required `v` prefix, such as `v0.13.0`. |
| `uv-version` | Empty | Use setup-uv's default version. |

Bare CLI versions, version ranges, Git revisions, URLs, and prereleases are rejected.
The Action SHA pins Action code, not CLI `latest`.

| Output | Meaning |
| --- | --- |
| `cli-path` | Absolute trusted executable path; valid only in this job. |
| `version` | Exact installed CLI version with a `v` prefix. |

Pass these outputs to later Actions' `cli-path` and `version` inputs to reuse the same installation.
Never use a path from contributor data or transfer it between jobs.
An exact `version` must match the executable; `latest` with a trusted path validates its stable version without resolving PyPI again.

## Environment preparation

Use [Prepare](../prepare/README.md) for project tools and offline dependency caches before standalone operations.
It requires Linux, Bash, Git, `gh`, `jq`, and standard coreutils, but no consumer checkout.
It reads the selected remote branch in temporary repositories without changing caller files, index, refs, or Git identity.
Run it on `push` or `workflow_dispatch` for that base branch; forced or deleted pushes and contributor PR events are rejected.
Every scope needs only `contents: read`.

| `operation` | Environment selected |
| --- | --- |
| `manage-pr` (default) | Current pending release plan. |
| `inspect` | Latest saved batch's parent configuration and consumed notes. |
| `publish` | Same batch scope, guarded by the required `expected-release-commit`. |
| `auto` | Saved-batch scope and the current pending PR plan. |

These names select preparation only; the Action never manages PRs, creates tags, or publishes Releases.
Use `inspect` preparation when discovering a batch, and guarded `publish` preparation after inspection or external CI selects its exact commit.

| Input | Default | Behavior |
| --- | --- | --- |
| `cli-path` | Empty | Install `version`, or reuse a trusted same-job Setup output. |
| `version` | `latest` | Stable PyPI CLI; exact versions require a `v` prefix. |
| `operation` | `manage-pr` | One of the four scopes above. |
| `github-token` | `github.token` | Repository token with contents read permission. |
| `base-branch` | Empty | Use the repository default branch; the workflow must run on that branch. |
| `expected-release-commit` | Empty | Required full lowercase 40-character batch SHA for `publish`; rejected for other scopes. |
| `node-version` | `lts/*` | Node.js for configured npm lockfiles. |
| `npm-version` | Empty | Use npm bundled with Node.js, or select an exact stable `x.y.z` version. |
| `rust-toolchain` | `stable` | Rust toolchain for configured Cargo lockfiles, not CLI installation. |
| `uv-version` | Empty | Use setup-uv's default for CLI installation and configured uv lockfiles. |

Calling this Action enables preparation; there is no cache toggle or custom cache-key input.
It finds supported existing lockfiles from configured primary and additional version files and fills the package managers' local dependency caches.
Shared lockfiles are prepared once per revision; inactive plans and manifests without supported lockfiles need no cache preparation.
It does not use `actions/cache` archives or promise cross-job cache reuse.
For cache commands, supported files, private package credentials, and build restrictions, see [Tool setup](github-actions.md#tool-setup).
Use the same CLI and project tool versions for preparation and later operations.

| Output | Meaning |
| --- | --- |
| `cargo` | Whether the selected environment requires Cargo. |
| `npm` | Whether the selected environment requires npm. |
| `uv` | Whether the selected environment requires uv lockfile support. |
| `pr-environment-ready` | Whether current PR preparation succeeded or was not requested. |

In `auto`, a current-plan preparation failure returns `pr-environment-ready=false` without suppressing successful historical-batch preparation.
CLI installation, required tool installation, and historical preparation failures still stop the Action.
The other scopes do not suppress preparation failures.

## Release PR workflow

This two-job example uses `/manage-pr` for PR management and `/publish` for built-in tags and GitHub Releases.
It does not use the project script inputs. Use the [command-hook workflow](https://github.com/changenote/example/blob/main/examples/actions/command-hooks.yml) when your project owns publication.
Replace each SHA placeholder with a reviewed full commit SHA. The CLI and Action must use compatible release-plan formats.

```yaml
name: Release
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: changenote-release-main
  cancel-in-progress: false
jobs:
  release:
    permissions:
      contents: write
      pull-requests: write
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0
          persist-credentials: false
      - uses: changenote/action/manage-pr@<full-action-commit-sha>
        with:
          base-branch: main

  publish:
    needs: release
    if: ${{ always() && github.ref == 'refs/heads/main' && needs.release.result != 'cancelled' }}
    permissions:
      contents: write
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main
          fetch-depth: 0
          persist-credentials: false
      - uses: changenote/action/publish@<full-action-commit-sha>
        with:
          base-branch: main
```

The Action fetches the current base branch, applies pending notes in a temporary worktree, and creates or updates one PR from `changenote-release/<base-branch>`.
The suffix is the selected `base-branch`, or the repository default branch when that input is empty.
For example, `main` uses `changenote-release/main`, and `release/1.x` uses `changenote-release/release/1.x`.
Reserve that branch for automation. See [branch migration](migration.md#release-pr-branch-names) before upgrading from the previous naming format.

New notes update the same PR. A rerun creates no commit or push when the release branch includes the current base commit and its generated tree is unchanged. If notes are removed, the Action closes only its managed PR and leaves the branch in place. A manually closed PR is replaced when notes remain.

`pr-draft` is available on root and `/manage-pr`:

| Value | Creation | Updates |
| --- | --- | --- |
| Empty (default) | Ready PR | Preserve draft status. |
| `create` | Draft PR | Preserve draft status. |
| `always` | Draft PR | Convert managed ready PRs to draft, including unchanged generated trees. |

Creation uses REST `draft`. Conversion uses GraphQL `convertPullRequestToDraft` and the managed PR's `node_id`, not REST PATCH.
Invalid values fail before API calls. A conversion failure fails the Action even if PR text or branch updates already succeeded.
No pending notes closes the PR without conversion. Ownership and lease checks remain required.

Release PR descriptions use a `Releases` heading and `package@version` headings. By default, notes are grouped by their own bump under `Major Changes`, `Minor Changes`, and `Patch Changes`; empty groups are omitted. Multiline notes remain within their list items. The Action requires a CLI that supports `status --include-note-sections`. This option adds ordered `note_sections` objects with `title` and `notes`; default release-plan output and saved batches are unchanged. Custom section configuration replaces the bump groups for both Release PRs and changelogs.

Existing branches require a marked PR in their history. Lease-based pushes stop if another actor moves the branch. The Action stages only release outputs and consumed notes. Notes and titles are data, not shell commands. PR bodies over 60,000 bytes omit release details.

In repository settings, enable **Actions > General > Allow GitHub Actions to create and approve pull requests**. Branch rules must permit the bot to push the release branch. The Action never approves or merges its PR.

PRs created with the default `GITHUB_TOKEN` do not automatically trigger PR workflows. If CI must run on the Release PR, use a GitHub App token (recommended) or PAT with repository contents and pull requests write permissions. Pass it through `github-token`. Checkout credentials do not select the Action's token.

## Publication inspection

The `/inspect` Action returns completed batches; `publication-needed` reports incomplete GitHub work independently of `release-commit` and `releases`.
The inspection Action requires Linux, Bash, Git, `gh`, `jq`, and standard coreutils. It installs the selected CLI wheel from PyPI through uv. It needs only `contents: read`. It reads the selected remote branch in a temporary repository; the caller's files, index, refs, tags, and Git identity are unchanged. A dirty or stale source checkout does not select the release. Temporary fetches and release-tree reconstruction are removed on success and failure.

```yaml
name: Publication inspection
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  inspect:
    runs-on: ubuntu-latest
    steps:
      - uses: changenote/action/inspect@<full-action-commit-sha>
        with:
          base-branch: main
```

This is a template, not part of the production release workflow. Use a reviewed Action SHA and a compatible CLI `version`. Inspection uses the same latest-batch discovery, full-tree verification, and remote-state inspection as publication. It never creates tags, commits, PRs, or Releases and does not inspect registries.

The `publication-plan` output is a compact JSON array of `name`, `version`, `tag`, `action`, and `conflicts`. Actions are `create-tag-and-release`, `create-release`, `none`, or `conflict`. Conflicts include a wrong remote tag identity, a draft Release, or a Release without its remote tag. Every batch entry is inspected before a conflict report is emitted. The `ready` output is true only after complete inspection finds no conflicts. `release-commit` identifies the verified batch commit.

When no batch exists, the Action succeeds with `ready=true`, an empty commit, and `[]`. Conflicts return the complete inspected report with `ready=false` and fail the step. Invalid input, tree/batch validation failures, or unavailable remote data fail without a ready plan; use the error diagnostic, not an empty plan, as the result. A readable summary goes to the step log. API failures are never treated as missing releases.

The inspection is advisory, not a reservation. Remote state can change afterward; real publication repeats preflight and race checks. Inspection does not grant permission to publish.

## Publication workflow

The two-job workflow above runs publication after PR management on every base-branch push.
Publication can recover an earlier batch even if PR management fails.
Its job needs only `contents: write`.

In this example, manual dispatch runs both PR management and built-in GitHub publication again.
This differs from root, where manual dispatch only manages the PR regardless of scripts or publication controls.
The [CLI repository's release workflow](https://github.com/changenote/changenote/blob/main/docs/development.md#repository-release-workflow) uses its own routing policy.

### Release-tree verification

Publication selects the latest first-parent release candidate. New candidates delete eligible top-level change notes; historical candidates change `.changenote/releases.json`. Version edits alone do not authorize publication. A malformed newest candidate stops selection instead of falling back to an older release.

The Action reconstructs a nonempty plan from the parent's consumed notes and compares the complete generated Git tree before publication. Retained notes are excluded from planning and restored unchanged before comparison. Filename bytes do not pass through UTF-8 conversion. Unrelated edits, including retained-note changes, fail verification. Historical configuration determines version sources, tag prefixes, and source links.

Known writer profiles cover file-free releases, historical metadata-only batches, and historical lockfile behavior. Historical note-bearing batches also support the older flat-changelog profile. Saved bytes are regenerated from validated notes, never copied from the candidate. Mixed profiles and arbitrary edits are rejected. The hidden `version --no-lockfiles` option is for temporary reconstruction only, not new releases.

Standard merge, squash, and rebase merges are supported. Later unrelated commits and new pending notes do not change the selected release SHA. Annotated tags are created from the verified plan after preflight of all local and remote tag conflicts; no repository batch file is needed.

### GitHub Release bodies

Each GitHub Release body comes from the corresponding package's `CHANGELOG.md` entry in the validated release commit. The package's configured directory selects the file, and the verified version selects the entry. Publication removes the version heading but preserves the Markdown body, including bump groups, nested lists, links, and code blocks. Empty groups are absent because changelog generation omits them. All package bodies are checked before any tag or Release write. Missing files, missing or duplicate version entries, and empty bodies stop publication without a saved-notes fallback. Later changelog edits do not change the selected body. Fixed-group members without direct notes keep their changelog's explanatory message.

Inspect entries locally with [`release-notes`](https://github.com/changenote/changenote/blob/main/docs/releases.md#read-a-release-entry).

### Saved-batch compatibility

Upgrade the Action before enabling file-free CLI releases. The Action accepts both file-free releases and historical metadata-only batches. New CLI version runs remove an existing regular batch file with the other release changes; no-op runs leave it unchanged. Use `release-commit` and `releases` outputs instead of reading the removed file.

Historical batches containing `notes` remain inspection-only unless publication is already complete: full batch and tree verification must pass, every remote tag must point to the release commit, and every GitHub Release must exist without draft status. Missing or conflicting publication stops without remote writes. Use matching old tooling or inspect it manually. Do not edit committed batch data or rewrite existing GitHub Release text. See [file-free rollout and recovery](migration.md#file-free-release-identity).

### Remote state

Existing remote tags must point to the selected commit. Missing tags and GitHub Releases are created; existing release text is not replaced. Draft releases, missing tags for existing releases, malformed batches, batch deletion without a new release, manually edited release trees, and tag conflicts stop publication. A batch in a root commit cannot be verified.
If no batch exists, publication makes no changes.

Root with explicit publication controls and no scripts, and standalone `/publish`, can complete the latest validated batch after later pushes.
Standalone `/inspect` and `/publish` always inspect tags and Releases. Their inputs and full-publication defaults are unchanged; `/publish` is not a selective retry.
Only root supports tags-only work or no built-in targets. See the [target matrix](github-actions.md#operations-and-inputs).
Root scripts can upload registry artifacts; the built-in publisher does not.
The root Action runs custom scripts only for a managed batch merged in the triggering push range.
An unrelated later push does not retry an older batch, and manual dispatch only manages the PR.
To retry custom scripts, re-run the original eligible workflow. A newer batch blocks that retry; scripts must handle partial publication safely.

## Inputs and outputs

The setup and preparation interfaces are listed under [CLI setup](#cli-setup) and [Environment preparation](#environment-preparation).
The [check Action reference](checks.md#github-action-report) covers PR coverage, exemptions, and reports.
For the root interface, see [Operations and inputs](github-actions.md#operations-and-inputs) and [Outputs](github-actions.md#outputs).

| Action | Input | Default |
| --- | --- | --- |
| All public Actions | `version` | `latest`; or an exact stable PyPI CLI version with a required `v` prefix |
| Release PR, Publication, Inspection | `github-token` | Workflow token |
| Release PR, Publication, Inspection | `base-branch` | Repository default branch |
| Release PR | `commit-message` | `chore(release): version packages` |
| Release PR | `pr-title` | `chore(release): version packages` |
| Root | `publish-script`, `release-script` | Empty; no custom publication |
| Root | `push-git-tags`, `create-github-releases` | Both `false`; Releases require explicit tags |
| Root, Release PR | `pr-draft` | Empty; also accepts `create` or `always` |
| Root | `prepare` | `true` for pending PR work and selected-batch replay tools; `false` uses caller-owned preparation |
| Operation Actions | `cli-path` | Empty; or a trusted same-job `/setup` output |
| Publication | `expected-release-commit` | Empty; retain latest-batch selection |

Root outputs are described in the [main guide](github-actions.md#outputs).
PR-only calls return no release identity and `ready=false`. Script-only success returns verified identity, `published=false`, `published-packages=[]`, and no requested GitHub work.
`ready` stays false until all requested release steps complete. It does not prove registry publication.
The root Action outputs `has-notes` (`true` or `false`), `pr-number` (number or empty string), and `pr-operation` (`created`, `updated`, `closed`, or `none`). `updated` includes a no-op version rerun that refreshes the PR metadata.
A selected and verified batch retains `release-commit` and `releases` even when GitHub work is complete.
`publication-needed` describes requested GitHub work only; it never determines whether a script runs. Read outputs only after success.

The publication Action accepts an optional `expected-release-commit`, a full lowercase 40-character commit SHA.
A mismatch with the verified latest batch fails before remote tag or Release writes.
Use this input after external CI instead of calling internal scripts.
Both inspection and publication output `releases`, a JSON array of `package`, `version`, and `tag` for the verified batch.
It includes all batch packages, including retries that create no remote objects.
If no batch exists, `releases` is `[]`.

The publication Action outputs `release-commit` (commit SHA or empty string), `published` (`true` if this run created any remote tag or GitHub Release), and `published-packages` (JSON, for example `[{"name":"pkg-a","version":"1.2.0"}]`). This is not registry publication. Read outputs only after successful steps.

## Recovery and limits

Disable the Release workflow to stop automation. Unmerged Release PR changes do not affect the base branch.

After a partial failure, retry the latest validated batch before merging another Release PR.
Discovery covers only the latest batch.
History rewrites or manual batch edits require manual inspection.
Never move tags automatically.
For the CLI repository's retry procedure, see [Repository release workflow](https://github.com/changenote/changenote/blob/main/docs/development.md#repository-release-workflow).
For the Action repository cutover, see [Migration](migration.md).

If PR creation fails after pushing a new branch, the Action checks for a successful remote PR creation before it removes that branch with a lease. If the API or cleanup also fails, inspect the marked PR and branch manually before retrying; an unowned branch is deliberately rejected. Do not delete a branch without checking its commit and PR history.

Before production use, verify repository permissions, branch rules, and App-token CI behavior in a disposable repository.
