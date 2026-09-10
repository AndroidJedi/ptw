#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 4 || $1 != --release-tag || $3 != --confirm || $4 != "DEPLOY PTW PRESERVING" ]]; then
    echo "usage: $0 --release-tag TAG --confirm 'DEPLOY PTW PRESERVING'" >&2
    exit 2
fi
release_tag=$2
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || {
    echo "invalid or unversioned release tag" >&2; exit 2;
}
revision=$(git rev-parse HEAD)
branch=$(git branch --show-current)
[[ -n $branch && -z $(git status --porcelain) ]] || {
    echo "fast release requires a clean committed branch" >&2; exit 1;
}
git fetch origin "$branch"
[[ $(git rev-parse "origin/$branch") == "$revision" ]] || {
    echo "fast release requires HEAD to equal its tracked origin branch" >&2; exit 1;
}

read -r deployed_ptw_revision deployed_platform_revision < <(
    ssh -i "$HOME/.ssh/ptw_commander" -o IdentitiesOnly=yes root@165.245.212.184 \
        'state=/root/ptw/.local/deployed-revision; deployed=""; if [ -s "$state" ]; then read -r deployed < "$state"; fi; if ! printf "%s" "$deployed" | grep -Eq "^[0-9a-f]{40}$"; then image=$(docker inspect ptw-validation-validation-api-1 --format "{{.Config.Image}}"); tag=${image#ptw-validation:}; short=${tag##*-}; deployed=$(git -C /root/ptw rev-parse "$short^{commit}"); fi; printf "%s %s\n" "$deployed" "$(git -C /opt/ptw/platform rev-parse HEAD)"'
)
[[ $deployed_ptw_revision =~ ^[0-9a-f]{40}$ && $deployed_platform_revision =~ ^[0-9a-f]{40}$ ]] || {
    echo "could not determine deployed revisions" >&2; exit 1;
}

release_directory=".local/releases/$release_tag"
mkdir -p "$release_directory"
started=$(date +%s)
scripts/build_ptw_release_images.sh "$release_tag" "$release_directory" \
    --base-revision "$deployed_ptw_revision"
scripts/publish_ptw_preserving.sh "$release_tag" "$release_directory" \
    "$deployed_platform_revision" "$release_directory" --confirm "DEPLOY PTW PRESERVING"
echo "End-to-end fast release completed in $(($(date +%s) - started))s"
