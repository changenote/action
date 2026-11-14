#!/usr/bin/env bash
# Install a published CLI wheel without loading or building the consumer project.
set -euo pipefail
version=${INPUT_VERSION:-latest}
semver='(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
requirement=changenote
if [[ $version != latest ]]; then
  [[ $version =~ ^v$semver$ ]] || { echo 'version must be latest or an exact stable version with a v prefix, such as v0.1.0.' >&2; exit 1; }
  version=${version#v}
  requirement="changenote==$version"
fi
: "${GITHUB_PATH:?Path file is required}" "${RUNNER_TEMP:?Runner temporary directory is required}"
directory=$(mktemp -d "$RUNNER_TEMP/changenote-cli.XXXXXX")
(
  cd "$directory"
  unset GH_TOKEN GITHUB_TOKEN INPUT_GITHUB_TOKEN
  export UV_TOOL_DIR="$directory/tools" UV_TOOL_BIN_DIR="$directory/bin"
  uv tool install --no-config --no-sources --no-cache --no-build \
    --default-index https://pypi.org/simple --resolution highest --prerelease disallow "$requirement"
)
binary="$directory/bin/changenote"
# uv links the executable into bin; accept only links within this installation.
[[ -f $binary && -x $binary ]] || { echo 'Installed CLI must be an executable file.' >&2; exit 1; }
[[ $(realpath -- "$binary") == "$directory/"* ]] || { echo 'Installed CLI must stay inside its tool environment.' >&2; exit 1; }
actual=$("$binary" --version)
installed=${actual#changenote }
[[ $actual == "changenote $installed" && $installed =~ ^$semver$ ]] || { echo 'Installed CLI did not report a stable changenote version.' >&2; exit 1; }
[[ $version == latest || $installed == "$version" ]] || { echo 'Installed CLI version differs from the requested version.' >&2; exit 1; }
printf '%s\n' "$directory/bin" >> "$GITHUB_PATH"
printf 'Installed %s from PyPI with uv.\n' "$actual"
