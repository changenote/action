#!/usr/bin/env bash
# Shared batch verification and remote inspection; callers own setup and writes.
# shellcheck source=scripts/action/common.sh
source "${BASH_SOURCE[0]%/*}/common.sh"

# Internal worker arguments default to the standalone full-publication contract.
publication_targets() {
  create_releases=${1-true}
  push_tags=${2-true}
  [[ $create_releases == true || $create_releases == false ]] || fail 'create-github-releases must be true or false.'
  [[ $push_tags == true || $push_tags == false ]] || fail 'push-git-tags must be true or false.'
  [[ $create_releases == false || $push_tags == true ]] || fail 'create-github-releases requires push-git-tags.'
}

select_publication_notes() {
  local path
  local -A consumed=()
  # Validate all parent notes before temporarily hiding retained Markdown files.
  "$cli" status > /dev/null
  git diff --no-renames --diff-filter=D --name-only -z "$parent" "$release" -- .changenote > "$temp/deleted-paths"
  while IFS= read -r -d '' path; do consumed[$path]=1; done < "$temp/deleted-paths"
  # Git paths preserve filename bytes that cannot be represented in JSON.
  git ls-files -z -- .changenote > "$temp/parent-paths"
  : > "$temp/pending-note-paths"
  while IFS= read -r -d '' path; do
    if [[ $path == .changenote/*.md && ${path#.changenote/} != */* && -z ${consumed[$path]+present} ]]; then
      printf '%s\0' "$path" >> "$temp/pending-note-paths"
    fi
  done < "$temp/parent-paths"
}

hide_pending_notes() {
  local path
  while IFS= read -r -d '' path; do rm -- "$path"; done < "$temp/pending-note-paths"
}

restore_pending_notes() {
  if [[ -s $temp/pending-note-paths ]]; then
    git --literal-pathspecs restore --source="$parent" --worktree \
      --pathspec-from-file="$temp/pending-note-paths" --pathspec-file-nul
  fi
}

is_release_note() {
  local name=${1#.changenote/}
  [[ $1 == .changenote/*.md && $name != */* && $name != .* ]] || return 1
  case ${name,,} in readme.md|agents.md|claude.md|gemini.md) return 1 ;; esac
}

find_publication_batch() {
  local commit parents path consumed=false mode
  release=''
  parent=''
  file_free=false
  # Keep Git errors separate from an empty candidate set. Paths stay NUL-delimited.
  git rev-list --first-parent "$base_sha" > "$temp/candidate-history" || fail 'Cannot read release history.'
  while IFS= read -r commit; do
    parents=$(git rev-list --parents -n 1 "$commit") || fail 'Cannot read release parents.'
    if [[ $parents == "$commit" ]]; then
      git ls-tree "$commit" -- .changenote/releases.json > "$temp/candidate-entry" || fail 'Cannot inspect root release.'
      [[ ! -s $temp/candidate-entry ]] || fail 'A release batch in a root commit has no verifiable parent.'
      break
    fi
    parent=${parents#* }
    parent=${parent%% *}
    git diff --no-renames --diff-filter=D --name-only -z "$parent" "$commit" -- .changenote \
      > "$temp/candidate-deleted" || fail 'Cannot inspect consumed notes.'
    consumed=false
    while IFS= read -r -d '' path; do
      if is_release_note "$path"; then consumed=true; break; fi
    done < "$temp/candidate-deleted"
    git diff --name-only "$parent" "$commit" -- .changenote/releases.json \
      > "$temp/candidate-batch" || fail 'Cannot inspect historical batch changes.'
    if [[ $consumed == true || -s $temp/candidate-batch ]]; then release=$commit; break; fi
  done < "$temp/candidate-history"
  if [[ -z $release ]]; then parent=''; return 0; fi
  git ls-tree "$release" -- .changenote/releases.json > "$temp/candidate-entry" || fail 'Cannot inspect release batch.'
  if [[ ! -s $temp/candidate-entry ]]; then
    [[ $consumed == true ]] || fail 'Release batch was removed without consumed notes.'
    file_free=true
  else
    read -r mode _ < "$temp/candidate-entry"
    [[ $mode == 100644 ]] || fail 'Release batch must be a regular file.'
    git show "$release:.changenote/releases.json" > "$temp/batch.json" || fail 'Cannot read release batch.'
    jq -e 'type == "array" and length > 0 and all(.[]; type == "object")' "$temp/batch.json" >/dev/null || fail 'Release batch must be a non-empty object array.'
  fi
}

verify_publication_batch() {
  legacy_batch=false
  find_publication_batch
  [[ -n $release ]] || return 0
  checkout_work "$parent"
  # Replay only consumed notes. Newer notes may have reached the base branch
  # before the Release PR merged; restore them before comparing the complete tree.
  select_publication_notes
  hide_pending_notes
  "$cli" status > "$temp/expected.json"
  jq -e 'type == "array" and length > 0' "$temp/expected.json" >/dev/null || fail 'Batch does not match the parent release plan: no active consumed notes.'
  if [[ $file_free == true ]]; then
    jq 'map(del(.notes))' "$temp/expected.json" > "$temp/batch.json"
  fi
  if jq -e --slurpfile expected "$temp/expected.json" '. == ($expected[0] | map(del(.notes)))' "$temp/batch.json" >/dev/null; then
    legacy_batch=false
  elif jq -e --slurpfile expected "$temp/expected.json" '. == $expected[0]' "$temp/batch.json" >/dev/null; then
    legacy_batch=true
  else
    fail 'Batch does not match the parent release plan.'
  fi
  local generated='' profile expected_tree
  local profiles=('' --no-lockfiles) options=()
  if [[ $legacy_batch == true ]]; then profiles+=(--legacy-output); fi
  expected_tree=$(git rev-parse "$release^{tree}")
  for profile in "${profiles[@]}"; do
    # Accept only complete known writer profiles, never mixed release output.
    git reset --hard "$parent"
    hide_pending_notes
    options=()
    if [[ -n $profile ]]; then options+=("$profile"); fi
    if "$cli" version "${options[@]}" > "$temp/applied.json"; then
      # Only the batch-storage format differs between these known profiles.
      # Never copy committed batch bytes into the reconstructed tree.
      if [[ $file_free == true ]]; then
        rm -f -- .changenote/releases.json
      elif [[ $legacy_batch == true ]]; then
        cp -- "$temp/expected.json" .changenote/releases.json
      else
        jq 'map(del(.notes))' "$temp/expected.json" > .changenote/releases.json
      fi
      restore_pending_notes
      stage_release "$temp/batch.json"
      generated=$(git write-tree)
      if [[ $generated == "$expected_tree" ]]; then break; fi
    fi
  done
  [[ $generated == "$expected_tree" ]] || fail 'Release commit contains changes beyond the generated release tree.'
  git reset --hard "$release"
}

# Create annotated local tags from the verified plan, independent of batch storage.
# Preflight the complete set before any tag write, including caller-local refs.
create_publication_tags() {
  local tag existing existing_tags
  local pending=() planned=()
  existing_tags=$(git for-each-ref --format='%(refname:strip=2)' refs/tags)
  while IFS= read -r tag; do
    [[ -n $tag && $tag != -* ]] || fail "Invalid release tag: $tag"
    git check-ref-format "refs/tags/$tag" || fail "Invalid release tag: $tag"
    for existing in "${planned[@]}"; do
      [[ $tag != "$existing" && $tag != "$existing/"* && $existing != "$tag/"* ]] || fail "Release tag namespace conflict: $tag and $existing"
    done
    planned+=("$tag")
    local found=false
    while IFS= read -r existing; do
      [[ -n $existing ]] || continue
      if [[ $existing == "$tag" ]]; then
        [[ $(git rev-parse "refs/tags/$tag^{commit}") == "$release" ]] || fail "Local tag already exists on a different commit: $tag"
        found=true
      elif [[ $existing == "$tag/"* || $tag == "$existing/"* ]]; then
        fail "Local tag namespace conflict: $tag and $existing"
      fi
    done <<< "$existing_tags"
    if [[ $found == false ]]; then pending+=("$tag"); fi
  done < <(jq -r '.[].tag' "$temp/batch.json")
  for tag in "${pending[@]}"; do git tag -a -m "$tag" -- "$tag" "$release"; done
}

# Recheck selection after replay and remote inspection, just before side effects.
require_unchanged_publication_batch() {
  local selected=$release
  remote_git fetch --no-tags "$remote_url" "refs/heads/$base"
  base_sha=$(git rev-parse FETCH_HEAD)
  find_publication_batch
  [[ $release == "$selected" ]] || fail 'Release batch changed before publication; select and validate it again.'
}

prepare_publication_notes() {
  [[ -n $release ]] || return 0
  [[ $create_releases == true || $legacy_batch == true ]] || return 0
  # Validate every body before any remote writes, including later batch members.
  local item package version index=0
  mkdir -p "$temp/notes"
  while IFS= read -r item; do
    index=$((index + 1))
    package=$(jq -r '.package' <<< "$item")
    version=$(jq -r '.version' <<< "$item")
    "$cli" release-notes --package="$package" --version "$version" > "$temp/notes/$index.md"
  done < <(jq -c '.[]' "$temp/batch.json")
}

inspect_publication() {
  local inspect_releases=$create_releases inspect_tags=$push_tags
  if [[ $legacy_batch == true ]]; then inspect_releases=true; inspect_tags=true; fi
  printf '[]\n' > "$temp/publication-plan.json"
  ready=true
  [[ $inspect_tags == true ]] || return 0
  if [[ $inspect_releases == true ]]; then
    gh api --paginate --slurp "repos/$GITHUB_REPOSITORY/releases?per_page=100" > "$temp/releases.json"
    jq -e 'type == "array" and length > 0 and all(.[]; type == "array" and all(.[]; (.tag_name | type == "string" and length > 0) and (.draft | type == "boolean")))' "$temp/releases.json" >/dev/null || fail 'Invalid GitHub release response.'
  fi
  remote_git ls-remote --tags --refs "$remote_url" > "$temp/remote-tag-refs"
  local item tag action conflicts has_release draft other_ref
  while IFS= read -r item; do
    tag=$(jq -r '.tag' <<< "$item")
    remote_tag "$tag"
    has_release=false
    draft=false
    if [[ $inspect_releases == true ]]; then
      has_release=$(jq --arg tag "$tag" 'any(.[][]; .tag_name == $tag)' "$temp/releases.json")
      draft=$(jq --arg tag "$tag" 'any(.[][]; .tag_name == $tag and .draft)' "$temp/releases.json")
    fi
    conflicts='[]'
    while IFS=$'\t' read -r _ other_ref; do
      if [[ $other_ref == "refs/tags/$tag/"* || refs/tags/$tag == "$other_ref/"* ]]; then
        conflicts=$(jq -c --arg reason "Remote tag namespace conflict: $tag and ${other_ref#refs/tags/}" '. + [$reason]' <<< "$conflicts")
      fi
    done < "$temp/remote-tag-refs"
    if [[ -n $tag_sha && $tag_sha != "$release" ]]; then
      conflicts=$(jq -c --arg reason "Remote tag points to another commit: $tag" '. + [$reason]' <<< "$conflicts")
    fi
    if [[ $draft == true ]]; then
      conflicts=$(jq -c --arg reason "Existing release is a draft: $tag" '. + [$reason]' <<< "$conflicts")
    fi
    if [[ $has_release == true && -z $tag_sha ]]; then
      conflicts=$(jq -c --arg reason "Existing release has no remote tag: $tag" '. + [$reason]' <<< "$conflicts")
    fi
    if [[ $conflicts != '[]' ]]; then action=conflict
    elif [[ -z $tag_sha && $inspect_releases == true ]]; then action=create-tag-and-release
    elif [[ -z $tag_sha ]]; then action=create-tag
    elif [[ $inspect_releases == true && $has_release == false ]]; then action=create-release
    else action=none
    fi
    jq --argjson item "$item" --arg action "$action" --argjson conflicts "$conflicts" \
      '. + [{name: $item.package, version: $item.version, tag: $item.tag, action: $action, conflicts: $conflicts}]' \
      "$temp/publication-plan.json" > "$temp/next-plan.json"
    cp -- "$temp/next-plan.json" "$temp/publication-plan.json"
  done < <(jq -c '.[]' "$temp/batch.json")
  ready=$(jq --argjson legacy "$legacy_batch" \
    'all(.[]; .action != "conflict" and ($legacy == false or .action == "none"))' \
    "$temp/publication-plan.json")
}

require_publication_ready() {
  if [[ $ready != true ]]; then
    jq -r '.[].conflicts[]' "$temp/publication-plan.json" >&2
    if [[ $legacy_batch == true ]]; then
      fail 'Legacy note-bearing batches require complete existing publication. Use matching old tooling for missing releases.'
    fi
    fail 'Publication conflicts require manual inspection.'
  fi
}
