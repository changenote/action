# changenote Actions

GitHub Actions for [changenote](https://github.com/changenote/changenote) release PRs, note checks, tags, and GitHub Releases.

| Entry point | Purpose | CLI setup |
| --- | --- | --- |
| `changenote/action/release` | Manage release PRs and publish tags and GitHub Releases. | Installs the trusted pinned CLI and prepares package-manager caches. |
| `changenote/action` | Manage release PRs and run optional project publication scripts. | Caller installs the CLI. |
| `changenote/action/check` | Check contributor PR notes with read-only permissions. | Caller installs the CLI. |
| `changenote/action/preview` | Inspect the latest validated publication batch without remote writes. | Caller installs the CLI. |
| `changenote/action/publish` | Publish tags and GitHub Releases for a validated batch. | Caller installs the CLI. |

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
- [Lower-level reference](docs/github-actions-reference.md): caller-installed CLI, PR management, preview, and publication.
- [PR note checks](docs/checks.md): read-only contributor checks.
- [Example workflows](examples/github-actions/): release, project scripts, and external CI.
- [Development](docs/development.md): trusted CLI pin and local checks.
- [Repository migration](docs/migration.md): publication order, new SHA selection, and verification limits.

The CLI source and its crates.io and PyPI publication remain in [changenote/changenote](https://github.com/changenote/changenote).
The CLI and Actions share the same release version. Their commit SHAs are separate.

The project uses the [MIT license](LICENSE).
