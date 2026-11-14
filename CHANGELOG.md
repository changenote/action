## 0.0.1

### Patch Changes

- Publish the root, release, check, preview, and publish GitHub Actions from the dedicated action repository.
  All five Actions use uv to install a prebuilt changenote wheel from PyPI through the new `version` input, which defaults to `latest`.
  Exact CLI versions require a `v` prefix, such as `v0.9.2`; the repository no longer pins CLI source.
  Separate CLI installation steps are no longer required.

