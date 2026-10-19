#!/usr/bin/env bash
# Keep the newest $KEEP artifacts per artifact name; delete the rest.
#
# "Generation" = one build's upload of a given name (newsixity-macos,
# newsixity-windows-x64, ...). The build workflows upload on every push, and
# at ~110-280 MB each they filled the repo's artifact quota — after which
# every build failed at its upload step (nothing to do with the code).
#
# Env:
#   GH_TOKEN / GITHUB_REPOSITORY   provided by Actions (needs actions: write)
#   KEEP                           generations to keep per name (default 2)
#   DRY_RUN                        "true" = list what would go, delete nothing
#   PRUNE_INPUT_FILE               test hook: read artifacts JSON from a file
#                                  instead of the API (and never delete)
set -euo pipefail

KEEP="${KEEP:-2}"
DRY_RUN="${DRY_RUN:-false}"

# A bad KEEP must never turn into "delete everything".
if ! [[ "$KEEP" =~ ^[0-9]+$ ]] || [ "$KEEP" -lt 1 ]; then
    echo "KEEP must be an integer >= 1 (got: '$KEEP')" >&2
    exit 1
fi

if [ -n "${PRUNE_INPUT_FILE:-}" ]; then
    artifacts="$(cat "$PRUNE_INPUT_FILE")"
    DRY_RUN=true
else
    : "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
    artifacts="$(gh api --paginate "repos/$GITHUB_REPOSITORY/actions/artifacts?per_page=100" \
        --jq '.artifacts[]' | jq -s '.')"
fi

# Per name: newest first, skip the first $KEEP, emit the rest. Expired
# artifacts are already gone from storage, so they are not candidates.
doomed="$(jq -c --argjson keep "$KEEP" '
    map(select(.expired == false))
    | group_by(.name)
    | map(sort_by(.created_at) | reverse | .[$keep:])
    | add // []
    | .[]
    | {id, name, size_in_bytes, created_at}
' <<<"$artifacts")"

total="$(jq 'map(select(.expired == false)) | length' <<<"$artifacts")"

if [ -z "$doomed" ]; then
    echo "Nothing to prune: $total artifact(s), none beyond the newest $KEEP per name."
    exit 0
fi

count=0
bytes=0
while IFS= read -r row; do
    id="$(jq -r .id <<<"$row")"
    name="$(jq -r .name <<<"$row")"
    size="$(jq -r .size_in_bytes <<<"$row")"
    created="$(jq -r .created_at <<<"$row")"
    if [ "$DRY_RUN" = "true" ]; then
        echo "would delete $id  $name  $((size / 1048576)) MB  $created"
    else
        gh api -X DELETE "repos/$GITHUB_REPOSITORY/actions/artifacts/$id" --silent
        echo "deleted $id  $name  $((size / 1048576)) MB  $created"
    fi
    count=$((count + 1))
    bytes=$((bytes + size))
done <<<"$doomed"

verb="Pruned"; [ "$DRY_RUN" = "true" ] && verb="Would prune"
echo "$verb $count of $total artifact(s), $((bytes / 1048576)) MB (kept newest $KEEP per name)."
