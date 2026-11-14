## 0.2.0

### Minor Changes

- Breaking Action API: remove root `operation` and manage Release PRs by default. Previous `auto` callers must remove `operation` and explicitly enable both `push-git-tags` and `create-github-releases`. Previous `hooks` callers retain scripts and must set `prepare: 'false'` to keep caller-owned project preparation. Add tags-only publication, ordered registry and GitHub publication steps, stable selected-batch identity outputs, and `pr-draft` controls on root and `/manage-pr`. The CLI selected by `version` remains independent. See `docs/migration.md` for migration and recovery.

## 0.1.0

### Minor Changes

- Add complete root operations and reusable setup, preparation, PR management, and batch selection Actions.
  Reuse a trusted same-job CLI path without another installation.
  Fix publication environment scope and recheck the remote batch before writes.
  Selection now returns completed batches; gate automatic GitHub work with publication-needed.
  The root keeps its hooks default; select auto explicitly for built-in publication.

- Use seven Action entry points with separate CLI setup, environment preparation, PR checks, PR management, inspection, and GitHub publication.
  Replace select and preview with inspect; remove the release entry point and root's single-operation modes without aliases.
  Use root hooks or auto for complete workflows, and use standalone Actions for individual operations and publication retries.
  Replace the select preparation scope with inspect and remove the retry input.
  Keep the hooks default, exact-commit publication guards, historical batch verification, and managed-merge script policy.

## 0.0.1

### Patch Changes

- Publish the root, release, check, preview, and publish GitHub Actions from the dedicated action repository.
  All five Actions use uv to install a prebuilt changenote wheel from PyPI through the new `version` input, which defaults to `latest`.
  Exact CLI versions require a `v` prefix, such as `v0.9.2`; the repository no longer pins CLI source.
  Separate CLI installation steps are no longer required.

