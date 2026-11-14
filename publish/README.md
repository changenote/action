# Changenote Publish

Revalidate the latest saved release batch on Linux and create missing annotated Git tags and GitHub Releases.
This Action does not upload packages to registries or replace existing release text.

## Usage

See [action.yml](action.yml).
Replace both placeholders with reviewed full commit SHAs from the correct repositories.
Change `main` to your release branch throughout the workflow.

```yaml
name: Publish GitHub Releases
on: workflow_dispatch
permissions:
  contents: write
concurrency:
  group: changenote-release-main
  cancel-in-progress: false
jobs:
  publish:
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
          operation: inspect
      - uses: changenote/action/publish@<full-action-commit-sha>
        with:
          base-branch: main
          version: 'v0.13.0'
```

This manual workflow publishes the latest validated batch, including incomplete work from an earlier push.
The Action requires a clean checkout; [Prepare](../prepare/README.md) supplies project tools and offline caches for batch replay.
The example uses the unguarded `inspect` preparation scope because the batch commit has not been selected in an earlier step.
For CI or approval between selection and publication, use the [guarded workflow](../docs/github-actions.md#external-ci-and-artifacts-logice-example) instead.

## Configuration

- `base-branch` defaults to the repository default branch.
- `github-token` defaults to the workflow token.
- `expected-release-commit` is optional; set the full lowercase 40-character SHA returned by [Inspect](../inspect/README.md) to reject a changed batch before remote writes.
- `version` defaults to CLI `latest`; exact stable versions require a `v` prefix.
- `cli-path` can reuse a trusted [Setup](../setup/README.md) output from this job; an exact `version` must match it.

Use the same CLI and project tool versions for PR generation, preparation, inspection, and publication.
An Action SHA does not freeze CLI `latest`; installation uses a prebuilt PyPI wheel without a source-build fallback.

## Outputs

- `release-commit`: the verified batch commit, or empty when no batch exists.
- `releases`: JSON objects with `package`, `version`, and `tag` for all batch members, including a completed retry.
- `published`: whether this run created any remote tag or GitHub Release.
- `published-packages`: JSON objects with `name` and `version` for packages changed remotely by this run.

Read outputs only after success.
No batch is a successful no-op; conflicts fail instead of moving tags or replacing Releases.

## Recommended permissions

Use `contents: write`; PR write permission is not required.
The token and repository rules must permit tag pushes and GitHub Release creation.
Project CI and deployment approval remain the caller's responsibility.

## Advanced usage

- [Release-tree, changelog, and remote-state verification](../docs/github-actions-reference.md#publication-workflow).
- [Complete inputs and outputs](../docs/github-actions-reference.md#inputs-and-outputs).
- [Partial failures and recovery](../docs/github-actions-reference.md#recovery-and-limits).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
