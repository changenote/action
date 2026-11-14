#!/usr/bin/env bash
# Input validation shared by root, preparation, and PR management.
# shellcheck source=scripts/action/common.sh
source "${BASH_SOURCE[0]%/*}/common.sh"

validate_event() {
  [[ $(uname -s) == Linux ]] || fail 'Only Linux runners are supported.'
  case ${GITHUB_EVENT_NAME:-} in
    push|workflow_dispatch) ;;
    *) fail 'Use this Action on push or workflow_dispatch, not contributor PR events.' ;;
  esac
  if [[ $GITHUB_EVENT_NAME == push ]]; then
    jq -e '.forced == false and .deleted == false' "${GITHUB_EVENT_PATH:?Event path is required}" >/dev/null || fail 'Forced or deleted pushes cannot run this Action.'
  fi
}

validate_tools() {
  [[ -z ${INPUT_NPM_VERSION:-} || ${INPUT_NPM_VERSION:-} =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'npm-version must be an exact stable version.'
  [[ ${INPUT_RUST_TOOLCHAIN:-stable} =~ ^[A-Za-z0-9._-]+$ ]] || fail 'Invalid rust-toolchain.'
}

validate_root() {
  validate_event
  validate_tools
  operation=${INPUT_OPERATION:-hooks}
  case $operation in hooks|auto) ;; *) fail 'operation must be hooks or auto. Use the standalone Actions for individual operations.' ;; esac
  [[ ${INPUT_PREPARE:-true} == false || ${INPUT_PREPARE:-true} == true ]] || fail 'prepare must be true or false.'
  [[ -z ${INPUT_RETRY:-} && -z ${INPUT_EXPECTED_RELEASE_COMMIT:-} ]] || fail 'retry and expected-release-commit are not root inputs. Use inspect and publish.'
  if [[ $operation != hooks && ( ${INPUT_PUBLISH_SCRIPT:-} =~ [^[:space:]] || ${INPUT_RELEASE_SCRIPT:-} =~ [^[:space:]] ) ]]; then
    fail 'Custom scripts require operation=hooks.'
  fi
}

validate_preparation() {
  validate_event
  validate_tools
  operation=${INPUT_OPERATION:-manage-pr}
  case $operation in
    auto|manage-pr|inspect|publish) ;;
    *) fail 'Preparation scope must be manage-pr, inspect, publish, or auto.' ;;
  esac
  if [[ $operation == publish ]]; then
    [[ ${INPUT_EXPECTED_RELEASE_COMMIT:-} =~ ^[0-9a-f]{40}$ ]] || fail 'publish preparation requires expected-release-commit with a full lowercase commit SHA.'
  else
    [[ -z ${INPUT_EXPECTED_RELEASE_COMMIT:-} ]] || fail 'expected-release-commit is only valid with publish preparation.'
  fi
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  case ${1:-} in
    prepare) validate_preparation; output operation "$operation" ;;
    manage-pr) validate_event ;;
    *) fail 'Unknown input validation entry point.' ;;
  esac
fi
