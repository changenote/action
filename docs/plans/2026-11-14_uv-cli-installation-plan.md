# uv CLI installation and v-prefixed versions

## Goal

Install changenote through uv from PyPI on all five Actions. Accept only `latest` or exact stable versions with a required `v` prefix. Update the existing PR #3 after local verification, without releases.

## Context

- The current PR installs via Cargo and accepts versions with or without `v`.
- PyPI currently publishes 0.9.2; crates.io publishes 0.11.0. The existing three Swift xcconfig tests fail with published PyPI 0.9.2 before this implementation change.
- Keep all regression tests. Publishing a newer CLI wheel is an external release action and is not authorized here.

## Plan

- [x] Inspect PyPI availability and confirm the compatibility difference; the three Swift tests fail with 0.9.2 on xcconfig parsing.
- [x] Replace the installer with isolated uv tool installation from PyPI, require `vX.Y.Z`, and verify the executable before PATH activation; cover failure and input cases with stubs.
- [x] Set up uv in every Action; prepare Rust only when `/release` discovers configured Cargo work; verify metadata and runtime ordering.
- [x] Update docs, examples, initial release note, and PR description for uv, the required prefix, and registry compatibility limits; verify status still plans v0.0.1.
- [x] Run live latest/exact installation checks, complete metadata/integration suites, and workflow checks; preserve any failing gate and its evidence.
  - Latest resolves to 0.9.2; `v0.9.1` resolves to 0.9.1. All 42 metadata tests pass. The full integration suite has 178 passing tests and 3 xcconfig failures.
  - Shell syntax, ShellCheck, actionlint, zizmor, whitespace checks, and 44 documentation link targets pass.
- [ ] Commit and push only intended Action paths to PR #3, with actual validation results and any external blocker recorded.

## Completion Checklist

- [x] Runtime CLI installation uses uv/PyPI, without Cargo builds or consumer project configuration.
- [x] Bare versions fail before installation; `latest` and `vX.Y.Z` resolve the expected requirements.
- [x] All five Action entry points use the installer; uv is unconditional and Rust setup remains limited to configured Cargo work.
- [ ] Blocked: the complete integration gate must pass after compatible PyPI wheels are published. The existing three Swift tests currently fail; no tests were skipped.
- [ ] PR #3 reflects the implemented behavior and actual checks; no release commands or settings changes occur.

## Rollback / Recovery

Keep or restore the prior reviewed Action SHA to retain earlier setup. Select a published exact PyPI version when `latest` changes unexpectedly. Do not change tags, release batches, or registry artifacts to work around missing distributions.

## External Handoff

If full integration remains blocked by missing xcconfig support in PyPI, the CLI maintainer must separately authorize and publish compatible CLI wheels. Then CI can rerun against the published release. No skipping regression tests or permission to publish follows from this task. Hosted setup-uv, fork permissions, and production release behavior remain unverified.
