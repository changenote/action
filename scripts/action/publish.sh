#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=scripts/action/publication.sh
source "${BASH_SOURCE[0]%/*}/publication.sh"
publication_targets "${2:-true}" "${3:-true}"
if [[ $# -gt 1 ]]; then
  setup_readonly
  git -C "$root" config user.name 'github-actions[bot]'
  git -C "$root" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
else
  setup
fi
output published false
output published-packages '[]'
output release-commit ''
output releases '[]'
expected=${INPUT_EXPECTED_RELEASE_COMMIT:-}
if [[ -n $expected ]]; then
  [[ $expected =~ ^[0-9a-f]{40}$ ]] || fail 'expected-release-commit must be a lowercase 40-hex commit.'
  if [[ $# -gt 0 && $1 != "$expected" ]]; then
    fail 'Conflicting positional and input expected release commits.'
  fi
fi
verify_publication_batch
prepare_publication_notes
# Preserve the positional guard, including an explicitly empty argument.
if [[ ( $# -gt 0 && $release != "$1" ) || ( -n $expected && $release != "$expected" ) ]]; then
  fail 'Release batch changed after preview; use an explicit retry.'
fi
[[ -n $release ]] || exit 0
output release-commit "$release"
output releases "$(jq -c 'map({package, version, tag})' "$temp/batch.json")"
# Inspect all remote objects before creating anything. API failure is not absence.
inspect_publication
require_publication_ready
if [[ $legacy_batch == true ]]; then
  printf 'Legacy batch is already fully published; no remote writes are required.\n'
  exit 0
fi
require_unchanged_publication_batch
[[ $push_tags == true ]] || exit 0
"$cli" tag
changed='[]'
record_publication() {
  [[ $did_publish == true && $recorded == false ]] || return 0
  changed=$(jq -c --argjson item "$item" '. + [{name: $item.package, version: $item.version}]' <<< "$changed")
  output published true
  output published-packages "$changed"
  recorded=true
}
index=0
while IFS= read -r item; do
  index=$((index + 1))
  tag=$(jq -r '.tag' <<< "$item")
  did_publish=false
  recorded=false
  remote_tag "$tag"
  [[ -z $tag_sha || $tag_sha == "$release" ]] || fail "Remote tag changed during publication: $tag"
  if [[ -z $tag_sha ]]; then
    if remote_git push "$remote_url" "refs/tags/$tag:refs/tags/$tag"; then
      did_publish=true
    else
      remote_tag "$tag"
      [[ $tag_sha == "$release" ]] || fail "Tag push failed: $tag"
    fi
  fi
  # Always recheck the remote identity, including after successful pushes.
  remote_tag "$tag"
  [[ $tag_sha == "$release" ]] || fail "Remote tag identity changed: $tag"
  record_publication
  if [[ $create_releases == true ]] && ! jq -e --arg tag "$tag" 'any(.[][]; .tag_name == $tag)' "$temp/releases.json" >/dev/null; then
    if gh release create "$tag" --repo "$GITHUB_REPOSITORY" --verify-tag --title "$tag" --notes-file "$temp/notes/$index.md"; then
      did_publish=true
    else
      # Only a verified existing release is an acceptable race result.
      gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases?per_page=100" > "$temp/rechecked.json"
      jq -e --arg tag "$tag" 'any(.[][]; .tag_name == $tag and .draft == false)' "$temp/rechecked.json" >/dev/null || fail "Release creation failed: $tag"
      remote_tag "$tag"
      [[ $tag_sha == "$release" ]] || fail "Release tag conflict: $tag"
    fi
  fi
  remote_tag "$tag"
  [[ $tag_sha == "$release" ]] || fail "Remote tag changed while creating the release: $tag"
  record_publication
done < <(jq -c '.[]' "$temp/batch.json")
