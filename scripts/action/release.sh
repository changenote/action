#!/usr/bin/env bash
# Root workflow orchestration. Workers own their isolated Git state and writes.
set -euo pipefail
# shellcheck source=scripts/action/inputs.sh
source "${BASH_SOURCE[0]%/*}/inputs.sh"

validate_root
export RUSTUP_TOOLCHAIN=${INPUT_RUST_TOOLCHAIN:-stable}
if [[ ${1:-run} == validate ]]; then
  output operation "$operation"
  scope=auto
  if [[ $GITHUB_EVENT_NAME == workflow_dispatch ]]; then scope=manage-pr; fi
  output environment-operation "$scope"
  exit 0
fi
[[ ${1:-run} == run ]] || fail 'Unknown root Action entry point.'
scripts=$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)
temp=$(mktemp -d)
work=''
trap cleanup EXIT
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

run_script() {
  local name=$1
  shift
  : > "$temp/$name.outputs"
  GITHUB_OUTPUT="$temp/$name.outputs" bash "$scripts/$name.sh" "$@"
}

value() {
  local file=$1 key=$2
  # Producers can update a scalar or one-line JSON field; keep the last value.
  awk -v key="$key" 'index($0, key "=") == 1 { value = substr($0, length(key) + 2) } END { print value }' "$temp/$file.outputs"
}

copy_outputs() {
  local file=$1 key
  shift
  for key in "$@"; do output "$key" "$(value "$file" "$key")"; done
}

# Routing must fail before PR writes. Keep caller GH_TOKEN unchanged for scripts.
expected=''
if [[ $operation == hooks ]]; then
  run_script lifecycle route
  expected=$(value lifecycle release-commit)
fi

management_token=${INPUT_GITHUB_TOKEN:-${GH_TOKEN:-}}
pr_result=0
if [[ $operation == auto && ${INPUT_PR_ENVIRONMENT_READY:-true} == false ]]; then
  printf 'PR environment preparation failed; publication will still be attempted.\n' >&2
  pr_result=1
else
  GH_TOKEN=$management_token run_script version || pr_result=$?
  copy_outputs version has-notes pr-number pr-operation
fi

if [[ $operation == hooks ]]; then
  if [[ -n $expected ]]; then
    run_script lifecycle run "$expected"
    copy_outputs lifecycle release-commit releases
  fi
  exit "$pr_result"
fi
[[ $GITHUB_EVENT_NAME == push ]] || exit "$pr_result"
GH_TOKEN=$management_token run_script inspect
copy_outputs inspect ready publication-plan publication-needed
selected=$(value inspect release-commit)
if [[ -z $selected || $(value inspect publication-needed) != true ]]; then exit "$pr_result"; fi
copy_outputs inspect release-commit releases
output ready false
GH_TOKEN=$management_token run_script publish "$selected"
copy_outputs publish release-commit releases published published-packages
output ready true
exit "$pr_result"
