# changenote Actions

GitHub Actions for [changenote](https://github.com/changenote/changenote) note checks, release PRs, Git tags, and GitHub Releases.

| Entry point | Responsibility |
| --- | --- |
| `changenote/action` | Complete workflow: `hooks` (default) or `auto`. |
| `changenote/action/setup` | Install the CLI and return its exact version and same-job path. |
| `changenote/action/prepare` | Prepare project tools and offline lockfile caches, without PR or publication writes. |
| `changenote/action/check` | Check contributor PR note coverage with read-only permissions. |
| `changenote/action/manage-pr` | Generate version changes and create, update, or close the managed Release PR. |
| `changenote/action/inspect` | Verify the latest committed batch and inspect GitHub publication state without writes. |
| `changenote/action/publish` | Revalidate the batch and create missing tags and GitHub Releases. |

All Actions support Linux and accept `version`, the CLI version to install from PyPI with uv.
Use `latest` or an exact stable version with a required `v` prefix, such as `v0.13.0`.
Bare versions, ranges, Git revisions, and prereleases are rejected.
Installation uses a prebuilt wheel outside the consumer checkout, with no Rust or source-build fallback.
An Action SHA does not pin the CLI when `version` is `latest`.

To reuse the CLI, run `/setup` once and pass its trusted `cli-path` to later Actions in the same job.
Use `/prepare` for project tools and caches. Its `operation` chooses an environment scope, not an operation to execute.
Root `auto` includes preparation by default; set `prepare: 'false'` after caller-owned preparation.

## Release workflow

Replace placeholders with reviewed full commit SHAs from the correct repositories.

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
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-checkout-commit-sha>
        with:
          persist-credentials: false
      - uses: changenote/action@<full-action-commit-sha>
        with:
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

## Breaking API changes

The former `release`, `select`, and `preview` paths are removed without aliases.
Root accepts only `hooks` and `auto`; individual operations use the corresponding standalone Actions.
See [Migration](docs/migration.md#composable-action-interfaces) before changing a production pin.

## Documentation

- [GitHub Actions guide](docs/github-actions.md): setup, permissions, scripts, and external CI.
- [Standalone Action reference](docs/github-actions-reference.md): PR management, inspection, and publication.
- [PR note checks](docs/checks.md): contributor checks.
- [Example workflows](examples/github-actions/): complete and composed workflows.
- [Development](docs/development.md): CLI compatibility, Action releases, and local checks.
- [Migration](docs/migration.md): API changes, coordinated pin updates, and rollback.

The CLI source and registry publication remain in [changenote/changenote](https://github.com/changenote/changenote).
The Action has its own independent version in `VERSION`; the `version` input selects the CLI.
The project uses the [MIT license](LICENSE).
