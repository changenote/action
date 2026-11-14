# README guidance

## Documentation

- Read and follow [docs/README_TEMPLATE.md](docs/README_TEMPLATE.md) when creating or editing an Action README; use its template and instructions for structure, examples, and links.
- Keep a `README.md` next to every public `action.yml`; do not rewrite unrelated READMEs.
- Write concise English technical prose.
- Verify documented inputs, outputs, defaults, and supported behavior against the corresponding `action.yml`, `scripts/action/`, and existing guides.
- Distinguish the Action release version in `VERSION` from the CLI selected by the `version` input.
- Reuse the existing guides linked from [README.md](README.md#advanced-usage) instead of creating duplicate references.

## Testing

- For README changes, check relative links and anchors, and validate YAML examples against required events, permissions, and prerequisites.
- For guidance or template-only changes, check links, instruction consistency, and `git diff --check`; runtime tests are not required.
