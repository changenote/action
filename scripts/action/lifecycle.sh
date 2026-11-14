#!/usr/bin/env bash
# Managed-merge routing and the trusted-script execution directory.
# Root release.sh owns the order of scripts and built-in publication.
set -euo pipefail
# shellcheck source=scripts/action/publication.sh
source "${BASH_SOURCE[0]%/*}/publication.sh"

route_managed_release() {
  export GH_TOKEN=${INPUT_GITHUB_TOKEN:?github-token is required}
  setup_readonly
  [[ ${GITHUB_REF:-} == "refs/heads/$base" ]] || fail 'Run the root Action on its selected base branch.'
  local scripts expected after
  scripts=$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)
  for tool in uv python3; do command -v "$tool" >/dev/null || fail "Missing prerequisite: $tool"; done
  export INPUT_BASE_BRANCH=$base
  GITHUB_OUTPUT="$temp/route.outputs" UV_PYTHON_DOWNLOADS=never \
    uv run --no-project --no-config --python "$(command -v python3)" \
    python "$scripts/route-release.py" managed-merge
  expected=$(awk -F= '$1 == "release-commit" {print $2}' "$temp/route.outputs")
  if [[ $GITHUB_EVENT_NAME == push ]]; then
    after=$(jq -er '.after' "$GITHUB_EVENT_PATH")
    [[ ${GITHUB_SHA:-} == "$after" ]] || fail 'Push event does not match the triggering commit.'
    git merge-base --is-ancestor "$after" "$base_sha" || fail 'Triggering commit is not on the remote base branch.'
  fi
  output release-commit "$expected"
}

initialize_script_execution() {
  local expected=$1
  caller_token_set=${GH_TOKEN+x}
  caller_token=${GH_TOKEN-}
  export GH_TOKEN=${INPUT_GITHUB_TOKEN:?github-token is required}
  setup_readonly
  [[ $expected =~ ^[0-9a-f]{40}$ ]] || fail 'A routed full release commit is required.'
  verify_publication_batch
  [[ $release == "$expected" ]] || fail 'Release batch changed after routing; re-run the selected release workflow.'
  [[ $legacy_batch == false ]] || fail 'Custom commands cannot publish historical note-bearing batches. Use matching old tooling.'
  prepare_publication_notes
  inspect_publication
  require_publication_ready
  selected=$release
  releases=$(jq -c 'map({package, version, tag})' "$temp/batch.json")
  output release-commit "$selected"
  output releases "$releases"
  output publication-plan "$(jq -c . "$temp/publication-plan.json")"
  output publication-needed "$(jq -r 'any(.[]; .action != "none")' "$temp/publication-plan.json")"
  # These settings affect only the temporary repository, never caller Git identity.
  git -C "$root" remote add origin "$remote_url"
  git -C "$root" config user.name 'github-actions[bot]'
  git -C "$root" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  git -C "$root" config core.hooksPath /dev/null
  require_unchanged_publication_batch
}

run_trusted_script() {
  local name=$1 script_text=$2
  [[ $script_text =~ [^[:space:]] ]] || return 0
  [[ $(git -C "$work" rev-parse HEAD) == "$selected" ]] || fail 'A command changed the selected release HEAD; stop and inspect publication state.'
  require_unchanged_publication_batch
  printf 'Running %s.\n' "$name"
  printf '%s\n' "$script_text" > "$temp/$name.sh"
  (
    # Strip the management token, but preserve explicit caller credentials.
    unset GH_TOKEN INPUT_GITHUB_TOKEN INPUT_PUBLISH_SCRIPT INPUT_RELEASE_SCRIPT BASH_ENV
    if [[ $caller_token_set == x ]]; then export GH_TOKEN="$caller_token"; fi
    export CHANGENOTE_RELEASE_COMMIT=$selected CHANGENOTE_RELEASES=$releases
    cd -- "$work"
    bash --noprofile --norc -e -o pipefail "$temp/$name.sh"
  )
  [[ $(git -C "$work" rev-parse HEAD) == "$selected" ]] || fail 'A command changed the selected release HEAD; stop and inspect publication state.'
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  [[ ${1:-} == route ]] || fail 'Unknown lifecycle operation.'
  route_managed_release
fi
