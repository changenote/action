# Changenote Manage PR

Create, update, or close the managed Release PR on Linux without approving, merging, or publishing it.

## Usage

See [action.yml](action.yml).
Replace both placeholders with reviewed full commit SHAs from the correct repositories.
Change `main` to your release branch throughout the workflow.

```yaml
name: Manage Release PR
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
concurrency:
  group: changenote-release-main
  cancel-in-progress: false
jobs:
  release:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-checkout-commit-sha>
        with:
          persist-credentials: false
      - uses: changenote/action/prepare@<full-action-commit-sha>
        with:
          base-branch: main
          version: 'v0.13.0'
      - uses: changenote/action/manage-pr@<full-action-commit-sha>
        with:
          base-branch: main
          version: 'v0.13.0'
```

Run on `push` or `workflow_dispatch`, not contributor PR events.
The Action requires a clean checkout and prepared project tools and offline caches for configured lockfiles.
The example uses [Prepare](../prepare/README.md) for that setup.

## Configuration

- `base-branch` defaults to the repository default branch.
- `pr-draft`: empty creates ready PRs; `create` drafts new PRs; `always` also converts managed ready PRs to draft on updates, including unchanged trees.
  - Empty and `create` preserve draft status on updates. No pending notes closes the PR without conversion. Conversion errors fail the Action.
- `github-token` defaults to the workflow token.
- `commit-message` and `pr-title` both default to `chore(release): version packages`.
- `version` defaults to CLI `latest`; exact stable versions require a `v` prefix.
- `cli-path` can reuse a trusted [Setup](../setup/README.md) output from this job; an exact `version` must match it.

Pin the CLI as well as the Action SHA, and use matching CLI and project tool versions for preparation and PR generation.
The CLI is installed from a prebuilt PyPI wheel, not built from source.

## Outputs

- `has-notes`: whether pending notes exist.
- `pr-number`: the managed PR number, or empty.
- `pr-operation`: `created`, `updated`, `closed`, or `none`; `updated` can include a version-generation no-op.

Read outputs only after success.
New notes update the same managed PR; removing pending notes closes it without deleting the reserved branch.

## Recommended permissions

Use `contents: write` and `pull-requests: write`, and enable PR creation by GitHub Actions in repository settings.
Branch rules must permit the automation to push its managed branch.
PRs created with the default workflow token do not automatically trigger PR CI; pass a reviewed GitHub App token or PAT through `github-token` when required.

## Advanced usage

- [Managed branch rules, PR bodies, and token setup](../docs/github-actions-reference.md#release-pr-workflow).
- [Complete inputs and outputs](../docs/github-actions-reference.md#inputs-and-outputs).
- [Failure recovery](../docs/github-actions-reference.md#recovery-and-limits).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
