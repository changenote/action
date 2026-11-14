# Action README template

Copy the Markdown block below into `README.md` next to the Action's `action.yml`.
Replace `{{...}}` placeholders and remove unused sections and template comments.

- Set `{{root}}` to an empty string for the root README or `../` for a sub-Action README.
- Set `{{action-path}}` to `changenote/action` or `changenote/action/<name>`.
- Adapt the example to the Action's supported events, required inputs, and least token permissions; use a `steps:` fragment when a full workflow is not needed.
  - Add checkout before steps that need repository files, pin it to a reviewed full SHA, and set `persist-credentials: false`.
  - Add branch restrictions, Git history, preparation, or concurrency when the operation requires them.
- Keep only the purpose, basic usage, important settings, outputs, permissions, and limits needed to use the Action.
  - Put complete interfaces, cache details, compatibility notes, and recovery procedures in `docs/`, and link to the relevant sections.
- Add versioned upgrade notices before usage only when applicable, with the required user action and a migration or release-notes link.
- For the root README, add a linked entry-point overview and leave standalone interface details in the individual guides.

````markdown
# {{action-name}}

{{One or two sentences that explain the purpose and main result.}}
Supports Linux runners.

<!-- Optional: add relevant CI badges near the title and upgrade notices before Usage. -->

## Usage

See [action.yml](action.yml).
Replace SHA placeholders with reviewed full commit SHAs from the correct repositories.

```yaml
name: Action example
on: "{{event}}"
permissions: {} # Set the permissions required by this workflow.
jobs:
  example:
    runs-on: ubuntu-latest
    steps:
      - uses: "{{action-path}}@<full-action-commit-sha>"
        with:
          version: 'v0.13.0'
          # Add required inputs from action.yml.
```

{{Prerequisites or warnings needed for this example.}}

## Configuration

- `version` defaults to `latest`, the latest stable PyPI CLI; exact stable versions require a `v` prefix.
- `{{input-name}}`: {{Accepted values, default, and behavior when omitted.}}

An Action SHA pins the Action code, not CLI `latest`.

<!-- Optional: summarize useful outputs, or link to their reference under Advanced usage. -->
## Outputs

- `{{output-name}}`: {{Meaning and conditions under which it is available.}}

## Recommended permissions

{{Required token permissions and any repository settings or authentication limits.}}

## Advanced usage

<!-- Link to the relevant sections, not a duplicate guide; use docs/checks.md for PR checks. -->
- [Complete interface and behavior]({{root}}docs/github-actions-reference.md).
- [Workflow examples]({{root}}examples/github-actions/).

## License

[MIT]({{root}}LICENSE).
````

## References

- [actions/setup-python](https://github.com/actions/setup-python/blob/5fda3b95a4ea91299a34e894583c3862153e4b97/README.md).
- [actions/setup-node](https://github.com/actions/setup-node/blob/101b3474143230c3562bd21f0b3c3f8254784571/README.md).
- [actions/setup-go](https://github.com/actions/setup-go/blob/3c1b57c66ace7a7ddc84e191ce910bdc40cdc6a3/README.md).
