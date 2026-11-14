# Changenote Prepare

Prepare project tools and offline lockfile caches on Linux without managing PRs or publishing tags or GitHub Releases.
The `operation` input selects an environment scope, not an operation to execute.

## Usage

See [action.yml](action.yml).
Replace the Action placeholder with a reviewed full commit SHA.
Change `main` to your release branch in both locations.

```yaml
name: Prepare release tools
on: workflow_dispatch
permissions:
  contents: read
jobs:
  prepare:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: changenote/action/prepare@<full-action-commit-sha>
        with:
          base-branch: main
          version: 'v0.13.0'
          operation: manage-pr
```

The Action reads the selected remote branch in temporary checkouts; no caller checkout is needed.
Run it on that branch with `push` or `workflow_dispatch`, not a contributor PR event.

## Configuration

- `operation` defaults to `manage-pr` for pending notes; `inspect` and `publish` select the saved batch, and `auto` prepares both scopes.
- `expected-release-commit` is required for `publish` preparation and rejected for all other scopes; use the exact lowercase 40-character batch SHA returned by inspection.
- `base-branch` defaults to the repository default branch; `github-token` defaults to the workflow token.
- `version` defaults to CLI `latest`; exact stable versions require a `v` prefix.
- `cli-path` can reuse a trusted [Setup](../setup/README.md) output from this job; an exact `version` must match it.
- `node-version`, `npm-version`, `rust-toolchain`, and `uv-version` select project tools; see the [complete input reference](../docs/github-actions-reference.md#environment-preparation) for defaults.

Pin the CLI with `version` as well as the Action SHA for repeatable runs.
CLI installation uses a PyPI wheel with no source-build fallback.
Preparation discovers supported existing lockfiles from configured version files and downloads dependencies for later offline operations.
It does not build project artifacts or restore an Action-managed executable cache.
Use the same CLI and project tool versions in later release operations.

## Outputs

`cargo`, `npm`, and `uv` report whether the selected environment needs each tool.
`pr-environment-ready` reports whether current PR environment preparation succeeded; in `auto`, a PR preparation failure can leave historical publication preparation available.

## Recommended permissions

Use `contents: read` for every preparation scope.
The default `github-token` is sufficient when it can read the repository.
Dependency downloads do not receive that token; configure private package credentials separately.

## Advanced usage

- [Scopes, cache behavior, inputs, and outputs](../docs/github-actions-reference.md#environment-preparation).
- [Tool setup and lockfile restrictions](../docs/github-actions.md#tool-setup).
- [Release PR management](../manage-pr/README.md) and [publication](../publish/README.md).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
