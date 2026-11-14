---
action: minor
---

Breaking Action API: remove root `operation` and manage Release PRs by default. Previous `auto` callers must remove `operation` and explicitly enable both `push-git-tags` and `create-github-releases`. Previous `hooks` callers retain scripts and must set `prepare: 'false'` to keep caller-owned project preparation. Add tags-only publication, ordered registry and GitHub publication steps, stable selected-batch identity outputs, and `pr-draft` controls on root and `/manage-pr`. The CLI selected by `version` remains independent. See `docs/migration.md` for migration and recovery.
