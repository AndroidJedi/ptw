#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 6 || $5 != --confirm || $6 != "DEPLOY PTW PRESERVING" ]]; then
    echo "usage: $0 RELEASE_TAG IMAGE_DIRECTORY PLATFORM_GIT_REVISION PLATFORM_IMAGE_DIRECTORY --confirm 'DEPLOY PTW PRESERVING'" >&2
    exit 2
fi
release_tag=$1
image_directory=$2
platform_revision=$3
platform_image_directory=$4
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || {
    echo "invalid or unversioned release tag" >&2; exit 2;
}
[[ $platform_revision =~ ^[0-9a-f]{40}$ ]] || {
    echo "PLATFORM_GIT_REVISION must be a full commit SHA" >&2; exit 2;
}
revision=$(git rev-parse HEAD)
branch=$(git branch --show-current)
[[ -n $branch && -z $(git status --porcelain) ]] || {
    echo "tracked PTW changes must be committed before publishing" >&2; exit 1;
}
git fetch origin "$branch"
[[ $(git rev-parse "origin/$branch") == "$revision" ]] || {
    echo "PTW release commit must equal its tracked origin branch" >&2; exit 1;
}
plan="$image_directory/release-plan.json"
python3 scripts/plan_ptw_release.py --validate "$plan" --target "$revision" \
    --release-tag "$release_tag" >/dev/null
has_migrations=$(python3 -c 'import json,sys; print("1" if json.load(open(sys.argv[1]))["migrations"] else "0")' "$plan")
[[ $has_migrations == 0 ]] || {
    echo "migration-bearing releases require publish_ptw_in_place_serial.sh" >&2; exit 1;
}

plan_value() {
    python3 - "$plan" "$1" "$2" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]][sys.argv[3]]
print("1" if value else "0")
PY
}
require_planned_archive() {
    local component=$1 archive=$2 expected
    expected=$(plan_value build "$component")
    if [[ $expected == 1 && ! -f $archive ]]; then
        echo "release plan requires missing $component image archive" >&2; exit 1
    fi
    if [[ $expected == 0 && -f $archive ]]; then
        echo "release plan reuses $component but an unexpected archive exists" >&2; exit 1
    fi
}
require_planned_archive commander "$image_directory/commander.tar"
require_planned_archive validation "$image_directory/validation.tar"
require_planned_archive owner-gateway "$image_directory/owner-gateway.tar"
require_planned_archive commander-god "$image_directory/commander-god.tar"

platform_artifact_count=0
for archive in commander-api.tar commander-worker.tar codex-auth.tar; do
    [[ ! -f $platform_image_directory/$archive ]] || ((platform_artifact_count += 1))
done
[[ $platform_artifact_count -eq 0 || $platform_artifact_count -eq 3 ]] || {
    echo "platform API, worker, and Codex auth images must be reused or published together" >&2; exit 1;
}
if [[ $platform_artifact_count -eq 3 && ! -f $platform_image_directory/platform-revision.bundle ]]; then
    echo "a changed platform release requires its exact revision bundle" >&2; exit 1
fi

sha256_file() {
    local line
    if command -v sha256sum >/dev/null 2>&1; then line=$(sha256sum "$1"); else line=$(shasum -a 256 "$1"); fi
    printf '%s\n' "${line%% *}"
}
emit_artifact() {
    local kind=$1 name=$2 path=$3 size blocks padding digest
    size=$(stat -f %z "$path" 2>/dev/null || stat -c %s "$path")
    blocks=$(( (size + 1048575) / 1048576 ))
    padding=$(( blocks * 1048576 - size ))
    digest=$(sha256_file "$path")
    printf '%s %s %s %s %s\n' "$kind" "$name" "$blocks" "$size" "$digest"
    command cat "$path"
    [[ $padding -eq 0 ]] || dd if=/dev/zero bs="$padding" count=1 2>/dev/null
    printf '\n'
}
emit_optional_image() {
    local name=$1 path=$2
    if [[ ! -f $path ]]; then
        printf 'REUSE %s\n' "$name"
    elif [[ " $remote_present_images " == *" $name "* ]]; then
        printf 'PRESENT %s\n' "$name"
    else
        emit_artifact IMAGE "$name" "$path"
    fi
}

owner_web=$(plan_value hosting owner-console)
public_web=$(plan_value hosting public-landings)
if [[ $public_web == 1 ]]; then
    npm --prefix apps/landing-web run check
    firebase deploy --only hosting:public-landings
    scripts/audit_public_landing.sh https://natal-landings-86123.web.app
    scripts/archive_natal_dashboard.sh
fi

remote_present_images=$(ssh -i "$HOME/.ssh/ptw_commander" -o IdentitiesOnly=yes \
    root@165.245.212.184 "bash -s -- '$release_tag' '$revision' '$platform_revision'" <<'REMOTE'
set -Eeuo pipefail
release_tag=$1
ptw_revision=$2
platform_revision=$3
inspect_candidate() {
    local name=$1 image=$2 revision=$3 metadata architecture label
    metadata=$(docker image inspect "$image:$release_tag" \
        --format '{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}' \
        2>/dev/null) || return 0
    read -r architecture label <<< "$metadata"
    if [[ $architecture == amd64 && $label == "$revision" ]]; then
        printf '%s\n' "$name"
    fi
}
inspect_candidate commander ptw-commander "$ptw_revision"
inspect_candidate validation ptw-validation "$ptw_revision"
inspect_candidate owner-gateway ptw-owner-gateway "$ptw_revision"
inspect_candidate commander-god ptw-commander-god "$ptw_revision"
inspect_candidate platform-commander-api ptw-agent-platform-commander-api "$platform_revision"
inspect_candidate platform-commander-worker ptw-agent-platform-commander-worker "$platform_revision"
inspect_candidate platform-codex-auth ptw-agent-platform-codex-auth "$platform_revision"
REMOTE
)
remote_present_images=${remote_present_images//$'\n'/ }

publish_started=$(date +%s)
{
    printf 'PTW-PRESERVING-STREAM 1\n'
    emit_optional_image commander "$image_directory/commander.tar"
    emit_optional_image validation "$image_directory/validation.tar"
    emit_optional_image owner-gateway "$image_directory/owner-gateway.tar"
    emit_optional_image commander-god "$image_directory/commander-god.tar"
    emit_optional_image platform-commander-api "$platform_image_directory/commander-api.tar"
    emit_optional_image platform-commander-worker "$platform_image_directory/commander-worker.tar"
    emit_optional_image platform-codex-auth "$platform_image_directory/codex-auth.tar"
    if [[ $platform_artifact_count -eq 3 ]]; then
        emit_artifact FILE platform-revision "$platform_image_directory/platform-revision.bundle"
    else
        printf 'REUSE platform-revision\n'
    fi
    emit_artifact FILE release-plan "$plan"
    printf 'END\n'
} | ssh -i "$HOME/.ssh/ptw_commander" -o IdentitiesOnly=yes root@165.245.212.184 \
    "set -e; exec 9>/run/lock/ptw-maintenance.lock; flock -n 9 || exit 73; git -C /root/ptw diff --quiet; git -C /root/ptw diff --cached --quiet; export PTW_MAINTENANCE_LOCK_HELD=1; git -C /root/ptw fetch origin '$revision'; git -C /root/ptw merge --ff-only '$revision'; exec /root/ptw/scripts/receive_ptw_preserving_release.sh '$release_tag' '$revision' '$platform_revision'"

if [[ $owner_web == 1 ]]; then
    npm --prefix apps/commander-web run check
    npm --prefix apps/commander-web run test:e2e
    firebase deploy --only hosting:owner-console
fi
python3 skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py
echo "Selective PTW release $release_tag published in $(($(date +%s) - publish_started))s"
