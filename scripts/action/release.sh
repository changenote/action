#!/usr/bin/env bash
# Root orchestration. Workers own isolated Git state and management credentials.
set -euo pipefail
# shellcheck source=scripts/action/inputs.sh
source "${BASH_SOURCE[0]%/*}/inputs.sh"

validate_root
export RUSTUP_TOOLCHAIN=${INPUT_RUST_TOOLCHAIN:-stable}
mode=${1:-run}
if [[ $mode == validate ]]; then
  output has-scripts "$has_scripts"
  exit 0
fi
scripts=$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)

run_script() {
  local name=$1
  shift
  : > "$temp/$name.outputs"
  GITHUB_OUTPUT="$temp/$name.outputs" bash "$scripts/$name.sh" "$@"
}

value() {
  local file=$1 key=$2
  awk -v key="$key" 'index($0, key "=") == 1 { value = substr($0, length(key) + 2) } END { print value }' "$temp/$file.outputs"
}

copy_outputs() {
  local file=$1 key
  shift
  for key in "$@"; do output "$key" "$(value "$file" "$key")"; done
}

if [[ $mode == execute ]]; then
  # A fresh process keeps errexit active and the execution directory alive
  # while built-in publication uses a separate, clean verified repository.
  # shellcheck source=scripts/action/lifecycle.sh
  source "$scripts/lifecycle.sh"
  initialize_script_execution "${2:-}"
  run_trusted_script publish-script "${INPUT_PUBLISH_SCRIPT:-}"
  require_unchanged_publication_batch
  if [[ $push_tags == true ]]; then
    result=0
    run_script publish "$selected" "$create_releases" "$push_tags" || result=$?
    copy_outputs publish published published-packages
    [[ $result == 0 ]] || exit "$result"
  fi
  run_trusted_script release-script "${INPUT_RELEASE_SCRIPT:-}"
  require_unchanged_publication_batch
  output ready true
  exit 0
fi
[[ $mode == run || $mode == select ]] || fail 'Unknown root Action entry point.'
temp=$(mktemp -d)
work=''
trap cleanup EXIT

# Either script requires managed-merge authorization before PR writes.
expected=''
if [[ $has_scripts == true && $GITHUB_EVENT_NAME == push ]]; then
  run_script lifecycle route
  expected=$(value lifecycle release-commit)
fi
release_selected=false
if [[ $GITHUB_EVENT_NAME == push ]]; then
  if [[ ( $has_scripts == true && -n $expected ) || ( $has_scripts == false && $push_tags == true ) ]]; then
    release_selected=true
  fi
fi
if [[ $mode == select ]]; then
  scope=manage-pr
  if [[ $release_selected == true ]]; then scope=auto; fi
  output environment-operation "$scope"
  exit 0
fi

output release-commit ''
output releases '[]'
output published false
output published-packages '[]'
output publication-plan '[]'
output publication-needed false
output ready false
output has-notes false
output pr-number ''
output pr-operation none

management_token=${INPUT_GITHUB_TOKEN:?github-token is required}
pr_result=0
if [[ ${INPUT_PR_ENVIRONMENT_READY:-true} == false ]]; then
  printf 'PR environment preparation failed; verified release work will still be attempted.\n' >&2
  pr_result=1
else
  GH_TOKEN=$management_token run_script version || pr_result=$?
  copy_outputs version has-notes pr-number pr-operation
fi
[[ $release_selected == true ]] || exit "$pr_result"
if [[ $has_scripts == true ]]; then
  result=0
  run_script release execute "$expected" || result=$?
  copy_outputs release release-commit releases publication-plan publication-needed
  # A failed stage can still have completed some remote writes.
  for key in published published-packages ready; do
    result_value=$(value release "$key")
    if [[ -n $result_value ]]; then output "$key" "$result_value"; fi
  done
  [[ $result == 0 ]] || exit "$result"
else
  GH_TOKEN=$management_token run_script inspect "$create_releases" "$push_tags"
  copy_outputs inspect release-commit releases publication-plan publication-needed
  selected=$(value inspect release-commit)
  if [[ -n $selected && $(value inspect publication-needed) == true ]]; then
    result=0
    GH_TOKEN=$management_token run_script publish "$selected" "$create_releases" "$push_tags" || result=$?
    copy_outputs publish published published-packages
    [[ $result == 0 ]] || exit "$result"
  fi
  output ready true
fi
exit "$pr_result"
