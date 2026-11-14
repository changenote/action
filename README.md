# changenote Actions

GitHub Actions for [changenote](https://github.com/changenote/changenote) note checks, release PRs, Git tags, and GitHub Releases.

| Entry point | Responsibility |
| --- | --- |
| [`changenote/action`](action.yml) | Complete workflow: `hooks` (default) or `auto`. |
| [`changenote/action/setup`](setup/README.md) | Install the CLI and return its exact version and same-job path. |
| [`changenote/action/prepare`](prepare/README.md) | Prepare project tools and offline lockfile caches, without PR or publication writes. |
| [`changenote/action/check`](check/README.md) | Check contributor PR note coverage with read-only permissions. |
| [`changenote/action/manage-pr`](manage-pr/README.md) | Generate version changes and create, update, or close the managed Release PR. |
| [`changenote/action/inspect`](inspect/README.md) | Verify the latest committed batch and inspect GitHub publication state without writes. |
| [`changenote/action/publish`](publish/README.md) | Revalidate the batch and create missing tags and GitHub Releases. |

All Actions support Linux.

## Breaking API changes

Action v0.1.0 removes the former `release`, `select`, and `preview` paths without aliases.
Root accepts only `hooks` and `auto`; use the standalone Actions for individual operations.
See [Migration](docs/migration.md#composable-action-interfaces) before changing a production pin.

## Usage

See [action.yml](action.yml) for the root Action interface.
Replace placeholders with reviewed full commit SHAs from the correct repositories, and change `main` to your release branch throughout the workflow.

```yaml
name: Release
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: write
  pull-requests: write
concurrency:
  group: changenote-release-${{ github.ref }}
  cancel-in-progress: false
jobs:
  release:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-checkout-commit-sha>
        with:
          persist-credentials: false
      - uses: changenote/action@<full-action-commit-sha>
        with:
          base-branch: main
          version: 'v0.13.0'
          operation: auto
```

On push, `auto` manages the Release PR and publishes incomplete validated batches.
On manual events, it only manages the PR.
The default `hooks` mode manages PRs and runs optional trusted scripts after a verified managed merge; it does not enable built-in publication.
Actions never approve or merge their PRs.

Built-in publication creates Git tags and GitHub Releases in the caller's repository, not registry uploads.
Use separate Actions for external CI and deployment approvals.
`/inspect` also returns completed batches; gate automatic GitHub work with `publication-needed`.
For an explicit publication retry, inspect the latest batch and pass its commit to `/publish`.

## CLI and project setup

Every Action accepts `version`, which defaults to the latest stable CLI from PyPI.
Use `latest` or an exact stable version with a required `v` prefix, such as `v0.13.0`; bare versions, ranges, Git revisions, and prereleases are rejected.
The Action's own release version in `VERSION` is independent of the CLI, and an Action SHA does not pin CLI `latest`.
Installation needs network access and a compatible prebuilt wheel, with no Rust or source-build fallback.

Use [Setup](setup/README.md) to reuse a trusted `cli-path` in the same job, and [Prepare](prepare/README.md) for project tools and offline caches.
Root `auto` includes preparation by default; set `prepare: 'false'` after caller-owned preparation.
For root `hooks`, prepare required project tools and caches before invocation.

## Recommended permissions

The root release workflow needs `contents: write` and `pull-requests: write` as shown above.
Enable PR creation by GitHub Actions and permit the bot to push its managed branch.
If Release PRs must trigger CI, pass a reviewed GitHub App token or PAT through `github-token`; PRs created with the default workflow token do not automatically trigger PR CI.
Read-only check and inspection workflows need only `contents: read`.
See [token and branch requirements](docs/github-actions-reference.md#release-pr-workflow) for setup details.

## Advanced usage

- [GitHub Actions guide](docs/github-actions.md): setup, permissions, scripts, and external CI.
- [Standalone Action reference](docs/github-actions-reference.md): CLI setup, preparation, PR management, inspection, and publication.
- [PR note checks](docs/checks.md): contributor checks.
- [Example workflows](examples/github-actions/): complete and composed workflows.
- [Development](docs/development.md): CLI compatibility, Action releases, and local checks.
- [Migration](docs/migration.md): API changes, coordinated pin updates, and rollback.

The CLI source and registry publication remain in [changenote/changenote](https://github.com/changenote/changenote).

## License

[MIT](LICENSE).
