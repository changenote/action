# Action repository migration

GitHub Actions move from the CLI repository, `changenote/changenote`, to `changenote/action`.
This migration changes repository ownership of the Action implementation and documentation. It does not require unrelated CLI behavior changes.

## Repository boundaries

The Action repository owns these five entry points. Their paths remain unchanged:

| Previous entry point | New entry point |
| --- | --- |
| `changenote/changenote` | `changenote/action` |
| `changenote/changenote/release` | `changenote/action/release` |
| `changenote/changenote/check` | `changenote/action/check` |
| `changenote/changenote/preview` | `changenote/action/preview` |
| `changenote/changenote/publish` | `changenote/action/publish` |

Use `@<full-action-commit-sha>` from the new repository after review.
Do not put an old CLI repository SHA after `changenote/action@`.
Existing full-SHA references to old Action commits remain valid. The move does not rewrite those commits.

The Action repository also owns shared scripts, Action tests, consumer workflows, and Action guides.
The CLI repository retains Rust code, the Python distribution, CLI guides, and its own release workflow.
Its crates.io helper is now `scripts/publish-crate.py`; crates.io and PyPI publication are not shared Action features.
The CLI and Action have independent versions and commit SHAs.
The Action's first planned release is `v0.0.1`; `version` selects the CLI separately.
See [Action releases](development.md#action-releases) for version PRs and publication.

## CLI version selection

All five Actions now install a changenote wheel from PyPI through uv.
`version` defaults to `latest`, the latest stable PyPI release; exact stable versions require a `v` prefix, such as `v0.9.2`.
The Action repository no longer stores a CLI source pin.
Remove separate CLI installation steps from caller workflows after adopting this implementation.
Use the same exact `version` across release jobs when repeatable replay is required.

Installation uses an isolated runner temporary tool environment, with source builds and project configuration disabled.
Each Action sets up uv. `/release` retains `rust-toolchain` only for configured Cargo lockfiles.
There is no Action-managed executable cache that can retain an outdated `latest` resolution.
CI installs the latest published PyPI CLI; integration tests use that executable on `PATH`.
Registry versions can differ; see [Published CLI compatibility](development.md#published-cli-compatibility) before adoption.
See [Development](development.md#cli-installation) for local setup.

Existing full-SHA references still execute their historical setup, including its old CLI pin.
The repository's own Release workflow uses `./release` from its `${{ github.sha }}` checkout.
This local implementation installs the CLI from PyPI and supports `version`.
Do not add the new `version` input to an old implementation that does not support it.

## Production cutover

Creating migration branches and pull requests does not approve a release, tag creation, or registry upload.
Before cutover, CLI and example workflows use full-SHA references to pre-migration Actions in `changenote/changenote`.
Migration PRs can pin an actual commit from the new Action branch after that branch is pushed.
Merge the Action PR before the CLI and example PRs that use its commit.
Do not use an unpinned `@main` Action reference.

1. Review and publish the new `changenote/action` repository **first**, with separate maintainer authorization.
   - Do not run the CLI's production release workflow against unpublished Action paths.
2. Obtain and review the new Action commit's actual full SHA after publication.
   - Confirm that all five entry points and the shared CLI installer are present.
   - Do not invent a SHA or reuse a SHA from the old repository.
3. Replace the CLI workflow's pre-migration Action references with `changenote/action@<new-sha>`, `changenote/action/preview@<new-sha>`, and `changenote/action/publish@<new-sha>`.
   - Use the same reviewed new Action revision for all three steps, and update the workflow contract tests.
   - Select the CLI through `version`, separately from the Action SHA.
   - Complete this switch before removing the old Action entry points from remote main.
4. Update consumer workflows only after the new SHA exists and is reviewed.
   - Keep consumer PRs dependent on the Action PR until its pinned commit is reviewed and merged.
   - Documentation placeholders are templates, not production pins.
5. With separate authorization, test hosted workflows in a disposable repository.
   - Verify event delivery, installed CLI version, cache behavior, token permissions, branch rules, and publication guards.
   - Obtain explicit approval before any production release or registry upload.

## Verification and recovery

Local verification passed: trusted CLI installation, 212 Action tests, CLI workflow and publication tests, Rust checks, and Python distribution checks.
ShellCheck, actionlint, workflow security checks, and local documentation link checks also passed.
The integration tests isolate local Git configuration and use an installed registry CLI.

Hosted checks remain unverified by this local migration. Local Git/mock tests and link checks do not establish release readiness.
No release is approved.

To stop automation, disable the consumer workflow and cancel active runs separately.
To restore prior Action code, restore the previous reviewed full-SHA references and matching workflow.
Inspect remote publication state before a retry. Do not edit saved release batches, move existing tags, or replace published artifacts.
