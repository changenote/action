# Action repository migration

The Action implementation belongs to `changenote/action`.
The Rust CLI and its crates.io and PyPI publication belong to `changenote/changenote`.
The repositories have independent versions and commit SHAs.
The Action `version` input selects a published CLI, not the Action release.

## Release PR branch names

New Release PRs use `changenote-release/<base-branch>` instead of `narumi/chore/changenote-release-<base-branch>`.
The suffix is the selected `base-branch`, or the repository default branch when that input is empty.
This applies to root and `/manage-pr`.

1. Update branch rules and workflow head-branch filters to allow the new name.
2. Before upgrading, merge and finish publication for the existing Release PR, or close it without merging.
   - The next PR-management run creates a PR from the new branch when notes remain.
   - The Action does not rename, close, or delete PRs and branches that use the previous name.
3. Update repository-owned managed-merge routing to recognize the new head name when updating Action pins.
   - The Action and CLI repository routers accept both names so existing managed merges and older pinned Actions remain valid.
   - Base branch, repository identity, merged commit, and body-marker checks remain required.

## Root release controls

This is a breaking Action API change under the pre-1.0 minor-release policy.
The CLI selected by `version` remains independent of the Action release in `VERSION`.
Root no longer supports `operation`, `hooks`, or `auto`. There is no alias or replacement mode selector.
GitHub may only warn about undeclared `with` inputs; do not expect a hard failure for `operation`.

1. Previous `operation: hooks` callers: remove `operation` and retain the scripts.
   - Built-in tags and Releases remain disabled unless explicitly enabled.
   - Set `prepare: 'false'` to retain caller-owned preparation. The old mode skipped preparation regardless of the input default.
2. Previous `operation: auto` callers: remove `operation` and set both `push-git-tags: 'true'` and `create-github-releases: 'true'`.
   - Without scripts, this retains publication of the latest saved batch on later pushes.
3. No-input callers: PR-only writes remain the default.
   - `prepare: 'true'` now applies consistently. PR-only calls return an empty `release-commit`, `releases: '[]'`, and `ready: 'false'`.
   - Selected batches retain identity even when requested GitHub work is already complete.

Either script requires a qualifying new managed merge in the triggering push range.
It disables script-free catch-up of older batches; unrelated pushes only manage the PR.
Steps run in order: `publish-script`, selected built-in tags and Releases, `release-script`.
A final script does not select publication targets. Keep both controls false when it owns tags or Releases.
Releases require explicit tags, including when tags already exist.
Publication controls accept only literal `true` or `false`.

`published` and `published-packages` describe built-in remote tag/Release changes only.
Script-only success returns verified identity but reports no built-in publication.
`publication-needed` is not registry state or a script-execution gate.
See [examples and draft PR behavior](github-actions.md#small-root-examples).

Manual root invocations remain PR-only. Workflow menu choices, `/prepare` environment scopes, `pr-operation` outputs, and all seven entry points are unchanged.
Standalone `/publish` still performs full publication, not a selective retry.
For script-only or tags-only recovery, re-run the original eligible root invocation with the same inputs.
Scripts repeat on retries, including completed GitHub work; make them safe for partial and completed uploads.
A newer batch must fail the retry, not switch versions.

Repository-owned root calls migrate in this change. External consumer pins and inputs require separate authorization and must change together.

## Composable Action interfaces

This revision has exactly seven public entry points: root, `setup`, `prepare`, `check`, `manage-pr`, `inspect`, and `publish`.
There are no compatibility aliases.

| Previous interface | Replacement |
| --- | --- |
| `changenote/action/release` | Root with explicit `push-git-tags: 'true'` and `create-github-releases: 'true'` |
| `changenote/action/select` or `changenote/action/preview` | `changenote/action/inspect` |
| Root `operation: manage-pr` | `changenote/action/manage-pr` |
| Root `operation: select` | `changenote/action/inspect` |
| Root `operation: publish` | `changenote/action/publish` |
| Root `operation: retry-publication` | Inspect, then publish with the inspected commit |
| Root `retry` input | Remove it; inspection always includes completed batches |
| Root `expected-release-commit` input | Pass the guard to standalone `publish` |
| Preparation scope `select` | Preparation scope `inspect` |
| Preparation scope `retry-publication` | Use `inspect`, then inspect and publish explicitly |

Root defaults to PR-only work. Replacing the old built-in workflow without both publication controls does not enable built-in publication.
Root only manages the PR on manual events.
Do not pass a manual workflow menu choice directly into root.
Use standalone Actions for manual PR work and publication retries, as the [composed workflow](https://github.com/changenote/example/blob/main/examples/actions/composed.yml) does.

Standalone Actions do not implicitly prepare project package-manager tools and caches.
When replacing a root operation, use `/prepare` first or retain caller-owned preparation.
Keep the same tool versions for preparation and the standalone operation. For Rust, set `RUSTUP_TOOLCHAIN` in the caller when it must override a checked-in toolchain file; root selects `rust-toolchain` itself.
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
Before rollout, record the previous reviewed full Action SHA, root mode, preparation setup, and inputs.
Restore that SHA and its matching workflow, including historical paths and `operation`; remove inputs the old Action does not support.
If the old interface cannot represent registry-script plus built-in publication, disable automation and recover explicitly. Never omit a publication step silently.
Code rollback does not undo remote tags, GitHub Releases, or registry uploads.

Inspect remote publication state before retrying a partial failure.
Do not edit saved release batches, move existing tags, or replace published artifacts.
Discovery covers the latest batch only; complete that batch before merging another Release PR.
Use a new release to correct a faulty published version.
