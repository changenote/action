# README guidance

## Documentation

- Apply these rules when editing `README.md`; do not rewrite it during unrelated work.
- Use the shared conventions below as this repository's writing guide, not as an official GitHub README specification.

### Reference READMEs

Use the three setup actions as primary references and the other actions as supporting examples:

- [actions/setup-python](https://github.com/actions/setup-python/blob/5fda3b95a4ea91299a34e894583c3862153e4b97/README.md)
- [actions/setup-node](https://github.com/actions/setup-node/blob/101b3474143230c3562bd21f0b3c3f8254784571/README.md)
- [actions/setup-go](https://github.com/actions/setup-go/blob/3c1b57c66ace7a7ddc84e191ce910bdc40cdc6a3/README.md)
- [actions/checkout](https://github.com/actions/checkout/blob/f548e57e544e1ff5a4c46bf1e1b8685f8e4a348a/README.md)
- [actions/cache](https://github.com/actions/cache/blob/3edfce9056124e459a23f683a21433670d47daca/README.md)

### Shared structure and style

- Write in English for workflow authors, with short factual sentences and descriptive section headings.
- Start with the action name and a short explanation of its purpose; use a short feature list when it helps explain distinct capabilities.
- Place CI status badges near the title when used, and link each badge to an existing workflow.
- Put relevant new features and breaking changes before usage, with the affected version, required user action, and a link to release notes or migration details.
  - State minimum runner or runtime requirements when an upgrade changes them.
  - Keep the full release history outside the README.
- Provide `Usage` or `Basic usage` before detailed feature guidance, and link to `action.yml` for the action interface.
- Show a minimal working YAML example before advanced scenarios; keep a full input reference separate from the basic example.
- Group additional examples by user task or feature, with one main purpose per example.
- Use an `Advanced usage` section or an equivalent documentation index to link to detailed guides instead of copying them into the README.
- Include explicit recommended workflow permissions and explain any token requirements.
- Put the license link near the end, with contribution and Code of Conduct links only when the corresponding policies exist.
- Preserve the shared information flow without requiring identical section names, exact section order, an inputs table, or a full table of contents.

### Examples and behavior

- Use fenced `yaml` blocks for workflow examples and inline code for input names, output names, paths, commands, and literal values.
- Show `uses: owner/repository[/path]@ref`, necessary `with` inputs, and a relevant following step when needed to demonstrate the result.
  - Include checkout before steps that need repository files.
  - Use a `steps:` fragment for a simple sequence, and include triggers, jobs, and permissions when they affect the example's behavior.
- Keep examples small and use comments to explain defaults, prerequisites, or non-obvious choices rather than repeat the YAML.
- Explain important inputs with their accepted values, defaults, and behavior when omitted; state precedence when inputs overlap.
- For version inputs, document supported syntax and resolution behavior, and quote version strings that YAML could interpret as numbers.
- Describe observable behavior and limits, such as file search locations, download sources, fallback behavior, or authentication boundaries, rather than implementation details.
- Put warnings next to the affected setting or example and state the required action.
- Document optional features only when supported by this action.
  - For caching, state whether it is enabled by default, what it stores, how keys are selected, and how to enable or disable it.
  - For outputs, show their use or link to the output reference.
  - For self-hosted runners, architectures, or GitHub Enterprise Server, state verified limits instead of assuming support.

### Application to this repository

- Verify documented inputs and outputs against `action.yml` or the corresponding subdirectory's `action.yml`, and verify behavior against `scripts/action/` and the existing guides.
- Keep the root README focused on choosing an entry point and running the main workflow; link to the standalone action reference for full interfaces.
- Reuse the existing documentation locations:
  - `docs/github-actions.md` for workflow setup, permissions, and scripts.
  - `docs/github-actions-reference.md` for standalone action interfaces.
  - `docs/checks.md` for PR note checks.
  - `docs/migration.md` for breaking changes and pin updates.
  - `docs/development.md` for contributor checks and Action releases.
  - `examples/github-actions/` for complete workflow templates.
- Preserve the full-commit-SHA pinning policy in `docs/development.md` instead of copying upstream `@vN` examples; clearly mark placeholders when a reviewed SHA is not supplied.
- Distinguish the Action's release version in `VERSION` from the CLI selected by the `version` input, including the fact that an Action SHA does not freeze CLI `latest`.
- State Linux support without implying the cross-platform support of the reference actions.
- Match permissions to the operation instead of copying the setup actions' `contents: read` recommendation into write workflows.
  - The root release workflow needs `contents: write` and `pull-requests: write`.
  - Read-only check and inspection examples use `contents: read`.

## Testing

- For README changes, check relative links and anchors, compare documented interfaces with the relevant action metadata, and check YAML examples against the documented permissions and prerequisites.
- For changes limited to this guide, check source links, instruction consistency, and `git diff --check`; runtime tests are not required.
