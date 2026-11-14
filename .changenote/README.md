# Action change notes

This directory manages the `action` package, not the changenote CLI.
`VERSION` is the Action version source.
The initial `0.0.0` value is an unreleased baseline; the initial patch note plans `v0.0.1`.

Add a note for changes to Action behavior, inputs, outputs, or the bundled CLI pin.
Documentation-only and test-only changes with no release effect need no note.
Do not create empty notes.

From the repository root, with the trusted CLI installed:

```sh
changenote add fix-release --package action --bump patch --message "Fix release behavior"
changenote status
```

Use `patch` for compatible fixes and CLI pin updates, and `minor` for compatible features.
Until version `1.0.0`, use `minor` for breaking changes and describe the required migration.
Keep the initial release at `0.0.1`.

Commit the note with the implementation.
Do not run `changenote version`, `changenote tag`, or the Release workflow without explicit authorization.
The Release workflow creates a version PR and publishes version tags and GitHub Releases after its merge.
It never merges its own PR.

The Action and CLI have independent versions.
`cli-source.env` fixes the CLI version and source revision; it is not an Action version file.
See [Action releases](../docs/development.md#action-releases) for permissions, publication, and recovery.
