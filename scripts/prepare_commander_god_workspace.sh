#!/bin/bash
set -Eeuo pipefail

repository=${PTW_REPOSITORY:-/root/ptw}
workspace=${PTW_COMMANDER_WORKSPACE:-/opt/ptw/commander-workspace}
revision=${1:-HEAD}

git -C "$repository" rev-parse --verify "$revision^{commit}" >/dev/null
mkdir -p "$(dirname "$workspace")"

if [[ ! -d "$workspace/.git" ]]; then
    [[ ! -e $workspace || -z $(find "$workspace" -mindepth 1 -maxdepth 1 -print -quit) ]] || {
        echo "Commander hosted workspace exists but is not an isolated Git clone" >&2
        exit 1
    }
    git clone --depth 1 --no-checkout "file://$repository" "$workspace"
    git -C "$workspace" remote remove origin
    git -C "$workspace" checkout --detach "$revision"
elif [[ -z $(git -C "$workspace" status --porcelain) ]]; then
    git -C "$workspace" fetch --depth 1 "$repository" "$revision"
    git -C "$workspace" checkout --detach FETCH_HEAD
else
    echo "Commander hosted workspace has owner changes; preserving its current revision" >&2
fi

for secret in .env .env.commander .env.owner-gateway; do
    [[ ! -e "$workspace/$secret" ]] || {
        echo "Commander hosted workspace contains a forbidden runtime environment file" >&2
        exit 1
    }
done
