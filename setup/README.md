# Changenote Setup

Install the changenote CLI from PyPI on Linux and return its exact version and executable path for reuse in the same job.
This Action does not need a repository checkout.

## Usage

See [action.yml](action.yml).
Replace the Action placeholder with a reviewed full commit SHA.

```yaml
name: Changenote CLI
on: workflow_dispatch
permissions: {}
jobs:
  setup:
    runs-on: ubuntu-latest
    steps:
      - uses: changenote/action/setup@<full-action-commit-sha>
        with:
          version: 'v0.13.0'
      - run: changenote --version
```

## Configuration

- `version` defaults to `latest`, the latest stable PyPI CLI release; exact stable versions require a `v` prefix, such as `v0.13.0`.
- `uv-version` is optional; when empty, it uses the setup-uv default.

An Action SHA selects the Action code, not the CLI version.
Use an exact `version` for repeatable runs.
Installation needs network access and a compatible prebuilt wheel; there is no Rust or source-build fallback.

## Outputs

- `cli-path`: the absolute trusted CLI path, valid only in this job.
- `version`: the installed exact CLI version, including its `v` prefix.

Pass `cli-path` to later changenote Actions to reuse the installation.
Do not pass paths from contributor data or another job.
An exact `version` on a later Action must match the reused executable.
With `latest` and a trusted path, the Action validates the installed stable version without resolving PyPI again.

## Recommended permissions

This Action needs no GitHub token permissions; `permissions: {}` is sufficient for the example.
Add only the permissions required by later steps.

## Advanced usage

- [Complete setup interface](../docs/github-actions-reference.md#cli-setup).
- [CLI isolation and version selection](../docs/development.md#cli-installation).
- [Project tool and cache preparation](../prepare/README.md).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
