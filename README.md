# changenote Actions

GitHub Actions for [changenote](https://github.com/changenote/changenote) release PRs, note checks, tags, and GitHub Releases.

| Entry point | Purpose | CLI setup |
| --- | --- | --- |
| `changenote/action/release` | Manage release PRs and publish tags and GitHub Releases. | Installs the selected CLI and prepares package-manager caches. |
| `changenote/action` | Manage release PRs and run optional project publication scripts. | Installs the selected CLI. |
| `changenote/action/check` | Check contributor PR notes with read-only permissions. | Installs the selected CLI. |
| `changenote/action/preview` | Inspect the latest validated publication batch without remote writes. | Installs the selected CLI. |
| `changenote/action/publish` | Publish tags and GitHub Releases for a validated batch. | Installs the selected CLI. |

All five Actions accept `version`, the changenote CLI version to install from PyPI with uv.
It defaults to `latest`, the latest stable published version. Use an exact version for repeatable runs:

```yaml
- uses: changenote/action/release@<full-action-commit-sha>
  with:
    version: 'v0.1.0'
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
      - uses: changenote/action/release@<full-action-commit-sha>
        with:
          operation: ${{ github.event_name == 'workflow_dispatch' && 'manage-pr' || 'auto' }}
```

Manual runs in this example only manage the PR. Actions never approve or merge their PRs.
Built-in publication creates tags and GitHub Releases, not registry uploads.
The root Action runs project publication scripts only when explicitly configured.

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
