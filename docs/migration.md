# Action repository migration

The Action implementation belongs to `changenote/action`.
The Rust CLI and its crates.io and PyPI publication belong to `changenote/changenote`.
The repositories have independent versions and commit SHAs.
The Action `version` input selects a published CLI, not the Action release.

## Composable Action interfaces

This revision has exactly seven public entry points: root, `setup`, `prepare`, `check`, `manage-pr`, `inspect`, and `publish`.
There are no compatibility aliases.

| Previous interface | Replacement |
| --- | --- |
| `changenote/action/release` | Root with explicit `operation: auto` for a complete built-in workflow |
| `changenote/action/select` or `changenote/action/preview` | `changenote/action/inspect` |
| Root `operation: manage-pr` | `changenote/action/manage-pr` |
| Root `operation: select` | `changenote/action/inspect` |
| Root `operation: publish` | `changenote/action/publish` |
| Root `operation: retry-publication` | Inspect, then publish with the inspected commit |
| Root `retry` input | Remove it; inspection always includes completed batches |
| Root `expected-release-commit` input | Pass the guard to standalone `publish` |
| Preparation scope `select` | Preparation scope `inspect` |
| Preparation scope `retry-publication` | Use `inspect`, then inspect and publish explicitly |

Root still defaults to `hooks`. Replacing the old built-in workflow with root without setting `auto` does not enable built-in publication.
Both root modes only manage the PR on manual events.
Do not pass a manual workflow menu choice directly into root.
Use standalone Actions for manual PR work and publication retries, as the [release template](../examples/github-actions/release.yml) does.

Standalone Actions do not implicitly prepare project package-manager tools and caches.
When replacing a root operation, use `/prepare` first or retain caller-owned preparation.
Keep the same tool versions for preparation and the standalone operation. For Rust, set `RUSTUP_TOOLCHAIN` in the caller when it must override a checked-in toolchain file; root `auto` still selects `rust-toolchain` itself.
The `/prepare` input `operation` is an environment scope: `manage-pr`, `inspect`, `publish`, or `auto`.
The `publish` scope requires the exact `expected-release-commit`; the other scopes reject this guard.
`/prepare` does not run that release operation.

Inspection returns verified completed batches as well as incomplete batches.
Gate automatic GitHub work with `publication-needed`, not a nonempty `release-commit`.
Keep manual downstream retries explicit. GitHub completion does not describe registry or artifact completion.
Standalone `publish` preserves optional latest-batch publication; after CI, supply `expected-release-commit` to lock the target.

## CLI version selection

Use `latest` or an exact stable PyPI CLI version with a required `v` prefix.
Each operation installs a prebuilt wheel unless it receives a trusted `cli-path` from same-job `/setup`.
Use the same exact compatible CLI and project tool versions across PR generation, inspection, and publication.
Do not transfer executable paths between jobs.

The installer disables project configuration, source overrides, and source builds.
It does not fall back to Cargo or a caller-installed executable after failure.
See [CLI compatibility](development.md#published-cli-compatibility).

## Production cutover

Existing full-SHA pins keep executing their historical code.
A new revision cannot execute a removed entry point or root operation.
Migrate the workflow and Action SHA together.

1. Have a maintainer review and make the new Action revision available before downstream cutover.
2. Obtain the actual reviewed full Action SHA. Do not invent a SHA or use an old CLI repository SHA.
3. Update downstream Action paths, preparation scopes, operation calls, and contract tests together.
   - The CLI repository currently has a pinned inspection call under the former name.
   - The example repository also has templates that use removed paths and root operations.
   - These sibling repositories are not changed by this refactor.
4. Preserve the external-CI commit guard, permission boundaries, concurrency, and manual retry policy.
5. Test hosted behavior in an authorized disposable repository before production adoption.

Documentation SHA placeholders are templates, not production pins.
Creating a branch or PR does not authorize package publication, version tags, a production Release run, or registry uploads.

## Verification and hosted handoff

Local Git and mocked GitHub tests do not establish hosted release readiness.
Current local verification evidence belongs in the implementation PR; historical CI results are not evidence for a changed revision.

| Responsible role | Prerequisite and action | Expected result and unverified behavior | Restriction |
| --- | --- | --- | --- |
| Repository maintainer | After separate authorization, use a disposable repository and reviewed Action SHA to exercise push, manual PR management, and exact-commit publication retries. | Confirm event delivery, wheel/tool installation, dependency caches, token scopes, branch rules, merge association, script order, and partial-publication recovery. | No production release is authorized by local completion. |
| Repository maintainer | Configure an approved App token if Release PR CI must run. | Confirm PR workflow delivery and permission boundaries, which local mocks cannot prove. | Do not grant extra token scopes without review. |
| CLI and example maintainers | After the new SHA is available and reviewed, update their workflows and contract tests together. | Confirm the seven-entry API and CI-selected commit guards work with the selected CLI. | Keep current production pins until coordinated migration is ready. |
| Registry/project owner | Review artifacts and obtain specific upload authorization before testing registry publication. | Confirm credentials, OIDC, registry ownership, and deployment approvals. | Dummy-command tests authorize no upload. Never send secrets through chat. |

## Rollback and recovery

Disable affected workflows and cancel active runs separately before unsafe automation continues.
Restore the previous reviewed full Action SHA and its matching workflow, including historical paths and inputs.
Code rollback does not undo remote tags, GitHub Releases, or registry uploads.

Inspect remote publication state before retrying a partial failure.
Do not edit saved release batches, move existing tags, or replace published artifacts.
Discovery covers the latest batch only; complete that batch before merging another Release PR.
Use a new release to correct a faulty published version.
