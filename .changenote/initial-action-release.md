---
action: patch
---

Publish the root, release, check, preview, and publish GitHub Actions from the dedicated action repository.
All five Actions install changenote from crates.io using the new `version` input, which defaults to `latest`.
Set an exact CLI version for reproducible runs; the repository no longer pins CLI source.
Separate CLI installation steps are no longer required.
