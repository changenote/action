# Changenote Inspect

Verify the latest saved release batch and inspect its GitHub tag and Release state on Linux without remote writes.
Completed batches are returned as well as batches with incomplete publication.

## Usage

See [action.yml](action.yml).
Replace the Action placeholder with a reviewed full commit SHA.

```yaml
name: Inspect publication
on: workflow_dispatch
permissions:
  contents: read
jobs:
  inspect:
    runs-on: ubuntu-latest
    steps:
      - uses: changenote/action/inspect@<full-action-commit-sha>
        id: inspect
```

No caller checkout is needed; selection uses the remote base branch in a temporary repository.
If batch replay needs project tools or offline lockfile caches, run [Prepare](../prepare/README.md) with `operation: inspect` first on the selected base branch.

## Configuration

- `base-branch` defaults to the repository default branch.
- `github-token` defaults to the workflow token.
- `version` defaults to CLI `latest`; exact stable versions require a `v` prefix.
- `cli-path` can reuse a trusted [Setup](../setup/README.md) output from this job; an exact `version` must match it.

Use the same exact CLI and project tool versions as PR generation and publication.
An Action SHA does not freeze CLI `latest`; installation uses a prebuilt PyPI wheel without a source-build fallback.

## Outputs

- `release-commit`: the verified batch commit, or empty when no batch exists.
- `releases`: JSON objects with `package`, `version`, and `tag` for every batch member.
- `ready`: whether complete inspection found no conflicts.
- `publication-needed`: whether GitHub publication work is incomplete.
- `publication-plan`: JSON entries with `name`, `version`, `tag`, `action`, and `conflicts`.

Gate automatic work on `publication-needed`, not on the presence of `release-commit`.
No batch returns `ready=true`, `publication-needed=false`, an empty commit, and empty arrays.
Conflicts fail the step with a complete inspected report; other errors are not a ready plan.
Inspection is not a CI result or publication approval, and publication repeats validation because remote state can change.

## Recommended permissions

Use `contents: read`.
The default `github-token` is sufficient when it can read repository contents and Releases.
Inspection does not check registries.

## Advanced usage

- [Plan actions, failure reports, and verification](../docs/github-actions-reference.md#publication-inspection).
- [External CI and guarded publication](../docs/github-actions.md#external-ci-and-artifacts).
- [Publish the verified batch](../publish/README.md).
- [All Actions](../README.md).

## License

[MIT](../LICENSE).
