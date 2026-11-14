# changenote Actions

GitHub Actions for [changenote](https://github.com/changenote/changenote) release PRs, note checks, tags, and GitHub Releases.

| Entry point | Purpose | CLI setup |
| --- | --- | --- |
| `changenote/action` | Complete workflow: managed-merge scripts or built-in release operations. | Installs or reuses the CLI; built-in operations prepare package-manager caches. |
| `changenote/action/setup` | Install the CLI once and return its same-job path and exact version. | Installs the selected CLI. |
| `changenote/action/prepare` | Prepare project tools and offline lockfile caches only. | Installs or reuses the CLI. |
| `changenote/action/manage-pr` | Create, update, or close the managed Release PR only. | Installs or reuses the CLI. |
| `changenote/action/select` | Return a verified batch and its separate GitHub publication state. | Installs or reuses the CLI. |
| `changenote/action/release` | Compatibility entry point for built-in operations; defaults to `auto`. | Uses the root's shared implementation. |
| `changenote/action/check` | Check contributor PR notes with read-only permissions. | Installs the selected CLI. |
| `changenote/action/preview` | Inspect the latest validated publication batch without remote writes. | Installs the selected CLI. |
| `changenote/action/publish` | Publish tags and GitHub Releases for a validated batch. | Installs the selected CLI. |

All Actions accept `version`, the changenote CLI version to install from PyPI with uv.
Operation Actions also accept a trusted `cli-path` returned by `/setup` in the same job, to avoid another installation.
It defaults to `latest`, the latest stable published version. Use an exact version for repeatable runs:

```yaml
- uses: changenote/action@<full-action-commit-sha>
  with:
    operation: auto
    version: 'v0.9.2'
```

Exact versions require the `v` prefix and must be published on PyPI.
Bare versions, version ranges, Git revisions, and prereleases are rejected.
Each Action sets up uv and installs a prebuilt CLI wheel outside the consumer checkout.
CLI installation does not require Rust and does not fall back to a source build.
The Action does not pin a CLI version; pinning the Action SHA alone does not pin `latest`.
Use a PyPI version that supports your configuration; see [Published CLI compatibility](docs/development.md#published-cli-compatibility).

## Release workflow

Replace every placeholder with a reviewed full commit SHA before use.
The Action SHA belongs to `changenote/action`, not the CLI repository.

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
          operation: ${{ github.event_name == 'workflow_dispatch' && 'manage-pr' || 'auto' }}
```

The root defaults to `operation: hooks` for compatibility: it manages PRs and runs optional verified post-merge scripts, with no built-in publication.
This example explicitly selects `auto` on pushes; manual runs only manage the PR. Actions never approve or merge their PRs.
Built-in publication creates tags and GitHub Releases, not registry uploads.
The root Action runs project publication scripts only when explicitly configured for `hooks`.
Use the single-purpose Actions to compose separate jobs or add external CI and approvals.
`/select` and `/preview` always return a verified batch, including completed batches; use `publication-needed` to gate automatic GitHub work.
See [CLI reuse and operation boundaries](docs/github-actions.md#root-operations-and-reusable-actions).

## Documentation

- [GitHub Actions guide](docs/github-actions.md): setup, permissions, operations, project scripts, and external CI.
- [Lower-level reference](docs/github-actions-reference.md): PR management, preview, and publication.
- [PR note checks](docs/checks.md): read-only contributor checks.
- [Example workflows](examples/github-actions/): release, project scripts, and external CI.
- [Development](docs/development.md): CLI installation, independent Action releases, and local checks.
- [Repository migration](docs/migration.md): publication order, new SHA selection, and verification limits.

The CLI source and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).
The Action has its own version in `VERSION`; its first planned release is `v0.0.1`.
The `version` input selects the CLI independently of the Action's version.
See [Action releases](docs/development.md#action-releases) for this repository's release workflow.

The project uses the [MIT license](LICENSE).
