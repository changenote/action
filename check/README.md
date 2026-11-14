# Changenote PR Check

Check committed PR changes for release notes on Linux and report the complete pending release plan without repository writes or PR comments.

## Usage

See [action.yml](action.yml).
Replace both placeholders with reviewed full commit SHAs from the correct repositories.

```yaml
name: Check release notes
on: pull_request
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-checkout-commit-sha>
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: changenote/action/check@<full-action-commit-sha>
        with:
          since: refs/remotes/origin/${{ github.base_ref }}
```

Use `pull_request`, not a privileged event that executes contributor code.
The Action needs a clean repository root and sufficient local Git history; it does not fetch missing history.

## Configuration

- `since` is required and must name an available Git base ref for the PR comparison.
- `coverage` defaults to `package`; set `pr` for PR-level coverage.
- `skip-release` defaults to `'false'`; `'true'` requires a nonempty `reason` from your repository's review policy.
- `reason` must be empty unless `skip-release` is enabled; exemptions are not inferred from labels or commit types.
- `version` defaults to CLI `latest`; exact stable versions require a `v` prefix.
- `cli-path` can reuse a trusted [Setup](../setup/README.md) output from this job; an exact `version` must match it.

An Action SHA does not freeze CLI `latest`.
The Action installs a prebuilt PyPI wheel, not code from the PR, and does not build contributor code or run project package managers.

## Outputs

- `check-report`: validated JSON for the PR comparison.
- `release-plan`: JSON for all pending notes, including older notes and fixed-group releases.
- `passed`: `true` or `false` for PR note coverage, not publication readiness.

Missing notes fail the step but still return validated reports.
Configuration, history, CLI, or report-validation errors fail without report outputs.
The job summary keeps the PR comparison separate from the complete pending plan.

## Recommended permissions

Use `contents: read` for checkout.
The reporting script uses no GitHub token and needs no write permission.

## Advanced usage

- [Coverage, exemptions, reports, and verification limits](../docs/checks.md#github-action-report).
- [CLI check rules and file patterns](https://github.com/changenote/changenote/blob/main/docs/checks.md).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
