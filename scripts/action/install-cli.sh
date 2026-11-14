#!/usr/bin/env bash
# Install a published CLI without building or loading configuration from the consumer.
set -euo pipefail
version=${INPUT_VERSION:-latest}
semver='(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
if [[ $version != latest ]]; then
  version=${version#v}
  [[ $version =~ ^$semver$ ]] || { echo 'version must be latest or an exact stable version such as 0.11.0.' >&2; exit 1; }
fi
: "${GITHUB_PATH:?Path file is required}" "${RUNNER_TEMP:?Runner temporary directory is required}"
export RUSTUP_TOOLCHAIN=${INPUT_RUST_TOOLCHAIN:-stable}
directory=$(mktemp -d "$RUNNER_TEMP/changenote-cli.XXXXXX")
args=(install --registry crates-io --locked --root "$directory")
if [[ $version != latest ]]; then args+=(--version "=$version"); fi
(
  # Do not load Cargo configuration or build code from the consumer checkout.
  cd "$directory"
  unset GH_TOKEN GITHUB_TOKEN INPUT_GITHUB_TOKEN
  cargo "${args[@]}" changenote
)
binary="$directory/bin/changenote"
[[ -f $binary && -x $binary && ! -L $binary ]] || { echo 'Installed CLI must be a regular executable file.' >&2; exit 1; }
actual=$("$binary" --version)
installed=${actual#changenote }
[[ $actual == "changenote $installed" && $installed =~ ^$semver$ ]] || { echo 'Installed CLI did not report a stable changenote version.' >&2; exit 1; }
[[ $version == latest || $installed == "$version" ]] || { echo 'Installed CLI version differs from the requested version.' >&2; exit 1; }
printf '%s\n' "$directory/bin" >> "$GITHUB_PATH"
printf 'Installed %s from crates.io.\n' "$actual"
