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
The CLI and Action share the same release version, but have separate commit SHAs.

## Trusted CLI source

The `/release` Action installs the CLI from the reviewed metadata in [`cli-source.env`](../cli-source.env):

- Repository: `https://github.com/changenote/changenote`.
- Full revision: `c644511a48a4c09a72b1d7a7b58dc6d6d8f374f5`.
- Expected CLI version: `0.11.0`.

Installation uses `cargo install --git "$CLI_REPOSITORY" --rev "$CLI_REVISION" --locked`.
Rust toolchain selection and executable caching remain supported.
The CLI is not compiled from the Action checkout or consumer source.
CI installs the same pin; integration tests use the installed CLI on `PATH`.
The root, `/check`, `/preview`, and `/publish` still require a caller-installed compatible CLI.
See [Development](development.md#trusted-cli-installation) for local setup.

## Production cutover

Creating migration branches and pull requests does not approve a release, tag creation, or registry upload.
Before cutover, CLI and example workflows use full-SHA references to pre-migration Actions in `changenote/changenote`.
Migration PRs can pin an actual commit from the new Action branch after that branch is pushed.
Merge the Action PR before the CLI and example PRs that use its commit.
Do not use an unpinned `@main` Action reference.

1. Review and publish the new `changenote/action` repository **first**, with separate maintainer authorization.
   - Do not run the CLI's production release workflow against unpublished Action paths.
2. Obtain and review the new Action commit's actual full SHA after publication.
   - Confirm that all five entry points and the trusted CLI metadata are present.
   - Do not invent a SHA or reuse a SHA from the old repository.
3. Replace the CLI workflow's pre-migration Action references with `changenote/action@<new-sha>`, `changenote/action/preview@<new-sha>`, and `changenote/action/publish@<new-sha>`.
   - Use the same reviewed new Action revision for all three steps, and update the workflow contract tests.
   - Keep the CLI source pin separate from the Action pin.
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
The integration tests isolate local Git configuration and use the reviewed CLI pin.

Hosted checks remain unverified by this local migration. Local Git/mock tests and link checks do not establish release readiness.
No release is approved.

To stop automation, disable the consumer workflow and cancel active runs separately.
To restore prior Action code, restore the previous reviewed full-SHA references and matching workflow.
Inspect remote publication state before a retry. Do not edit saved release batches, move existing tags, or replace published artifacts.
