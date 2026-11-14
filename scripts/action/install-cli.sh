#!/usr/bin/env bash
# Build only the pinned trusted CLI. Never build the consumer's source.
set -euo pipefail
export RUSTUP_TOOLCHAIN=${INPUT_RUST_TOOLCHAIN:-stable}
action_dir=$(cd -- "${ACTION_PATH:?Action path is required}/.." && pwd)
# shellcheck source=cli-source.env
source "$action_dir/cli-source.env"
: "${CLI_REPOSITORY:?CLI repository is required}" "${GITHUB_OUTPUT:?Output file is required}" "${RUNNER_TEMP:?Runner temporary directory is required}"
[[ $CLI_REVISION =~ ^[0-9a-f]{40}$ ]] || { echo 'CLI revision must be a full commit SHA.' >&2; exit 1; }
[[ $CLI_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'CLI version must be stable SemVer.' >&2; exit 1; }
fingerprint=$(
  printf '%s\n' "$CLI_REPOSITORY" "$CLI_REVISION" "$CLI_VERSION" "$RUSTUP_TOOLCHAIN" | sha256sum | cut -d ' ' -f 1
)
directory="$RUNNER_TEMP/changenote-cli/$fingerprint"
case ${1:?Expected key, install, or activate} in
  key)
    printf 'directory=%s\nkey=changenote-%s-%s-%s\n' "$directory" "$(uname -s)" "$(uname -m)" "$fingerprint" >> "$GITHUB_OUTPUT"
    ;;
  install)
    # Do not load Cargo configuration from the consumer checkout.
    cd "$action_dir"
    cargo install --git "$CLI_REPOSITORY" --rev "$CLI_REVISION" --locked --root "$directory"
    ;;
  activate)
    [[ -f $directory/bin/changenote && ! -L $directory/bin/changenote ]] || { echo 'Cached CLI must be a regular file.' >&2; exit 1; }
    [[ $("$directory/bin/changenote" --version) == "changenote $CLI_VERSION" ]] || { echo 'Cached CLI version differs from the trusted CLI pin.' >&2; exit 1; }
    printf '%s\n' "$directory/bin" >> "${GITHUB_PATH:?Path file is required}"
    ;;
  *) echo 'Unknown CLI setup operation.' >&2; exit 1 ;;
esac
