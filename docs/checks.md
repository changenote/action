# Check PR notes with GitHub Actions

Use `changenote/action/check@<full-action-commit-sha>` for read-only contributor PR checks.
It installs the CLI selected by `version` and defaults to package coverage.
The CLI defaults to PR-level coverage. See [CLI checks and file patterns](https://github.com/changenote/changenote/blob/main/docs/checks.md) for coverage rules and exemptions.

## CLI-only CI example

A workflow can run the CLI directly without the check Action.
Replace the placeholder with a reviewed compatible full CLI revision from `changenote/changenote`.
Exempt PRs must use an explicit repository review policy; this job does not infer exemptions.

```yaml
permissions:
  contents: read
steps:
  - uses: actions/checkout@v7
    with:
      fetch-depth: 0
      persist-credentials: false
  - uses: dtolnay/rust-toolchain@stable
  - name: Install changenote
    run: cargo install --git https://github.com/changenote/changenote --rev <full-cli-commit-sha> --locked
  - name: Check notes
    env:
      BASE_BRANCH: ${{ github.base_ref }}
    run: changenote check --since "refs/remotes/origin/$BASE_BRANCH"
```

Use these steps in a `pull_request` job. The checkout must contain `refs/remotes/origin/<base branch>` and a clean tree.
Branch names enter the shell through an environment variable, not inline expression substitution.

## GitHub Action report

Use the check Action after checkout. It sets up uv and installs a prebuilt changenote wheel from PyPI.
Replace the Action placeholder with a reviewed full SHA.
`version` defaults to `latest`, the latest stable PyPI CLI; use an exact version with the required `v` prefix for repeatable checks.

```yaml
permissions:
  contents: read
steps:
  - uses: actions/checkout@v7
    with:
      fetch-depth: 0
      persist-credentials: false
  - uses: changenote/action/check@<full-action-commit-sha>
    with:
      since: refs/remotes/origin/${{ github.base_ref }}
      coverage: package
```

Run this job on `pull_request`, not a privileged event that executes contributor code.
The Action requires Linux, Bash, Git, `jq`, a clean repository root, and sufficient local history.
CLI installation needs network access to uv distribution servers and PyPI. A compatible wheel must be published; no Rust or source build is used.
After setup, the check does not fetch, build contributor code, run project package managers, post comments, or require a write token.
Do not install the CLI from the PR revision. The checkout step needs read permission; the reporting script uses no GitHub token.

The required `since` input names an available Git ref. `coverage` defaults to `package`; set `pr` for the original policy.
An optional `skip-release: 'true'` requires a nonempty `reason` from the repository's review policy.
A reason is invalid without that exemption. The Action does not infer exemptions from labels or commit types.

Outputs are `check-report` (PR comparison JSON), `release-plan` (all pending release JSON), and `passed` (`true` or `false`).
The job summary and annotations distinguish the PR check from the complete pending plan, which can include older notes and fixed-group releases.
A missing-note failure emits validated reports and fails the step. Configuration, history, CLI, or report-validation errors fail without report outputs.
No output is a publication-readiness result. Summary text is escaped, including line breaks in paths and exemption reasons; note text is never evaluated as a command.

Local fixtures cover the report and permission contract. Hosted fork events and repository branch rules remain unverified for this Action.
A maintainer must configure and test those settings in an authorized disposable repository before relying on the hosted workflow.
No hosted test, tag creation, or publication is authorized by the local checks.
