#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 6 || $5 != --confirm || $6 != "RESET PTW PRODUCTION" ]]; then
    echo "usage: $0 RELEASE_TAG IMAGE_DIRECTORY PLATFORM_GIT_REVISION PLATFORM_IMAGE_DIRECTORY --confirm 'RESET PTW PRODUCTION'" >&2
    exit 2
fi
release_tag=$1
image_directory=$2
platform_revision=$3
platform_image_directory=$4
confirmation=$6
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || { echo "invalid release tag" >&2; exit 2; }
[[ $platform_revision =~ ^[0-9a-f]{40}$ ]] || { echo "PLATFORM_GIT_REVISION must be a full commit SHA" >&2; exit 2; }
revision=$(git rev-parse HEAD)
[[ -z $(git status --porcelain --untracked-files=no) ]] || { echo "tracked local changes must be committed" >&2; exit 1; }
stream_file=$(mktemp /tmp/ptw-release-stream.XXXXXX)
trap 'rm -f -- "$stream_file"' EXIT

sha256_file() {
    local line
    if command -v sha256sum >/dev/null 2>&1; then line=$(sha256sum "$1"); else line=$(shasum -a 256 "$1"); fi
    printf '%s\n' "${line%% *}"
}
emit_image() {
    local name=$1 path=$2 size blocks padding digest padded
    [[ -f $path ]] || { echo "missing image archive: $path" >&2; exit 1; }
    size=$(stat -f %z "$path" 2>/dev/null || stat -c %s "$path")
    blocks=$(( (size + 1048575) / 1048576 )); padding=$(( blocks * 1048576 - size )); digest=$(sha256_file "$path")
    if [[ $padding -gt 0 ]]; then
        padded=$(mktemp "/tmp/ptw-$name.XXXXXX.tar"); cp "$path" "$padded"
        dd if=/dev/zero bs=1 count="$padding" >> "$padded" 2>/dev/null; digest=$(sha256_file "$padded")
        printf 'IMAGE %s %s %s\n' "$name" "$blocks" "$digest"; command cat "$padded"; rm -f -- "$padded"
    else
        printf 'IMAGE %s %s %s\n' "$name" "$blocks" "$digest"; command cat "$path"
    fi
    printf '\n'
}
emit_file() {
    local name=$1 path=$2 size blocks padding digest padded
    [[ -f $path ]] || { echo "missing release artifact: $path" >&2; exit 1; }
    size=$(stat -f %z "$path" 2>/dev/null || stat -c %s "$path")
    blocks=$(( (size + 1048575) / 1048576 )); padding=$(( blocks * 1048576 - size )); digest=$(sha256_file "$path")
    if [[ $padding -gt 0 ]]; then
        padded=$(mktemp "/tmp/ptw-$name.XXXXXX"); cp "$path" "$padded"
        dd if=/dev/zero bs=1 count="$padding" >> "$padded" 2>/dev/null
        printf 'FILE %s %s %s %s\n' "$name" "$blocks" "$size" "$digest"; command cat "$padded"; rm -f -- "$padded"
    else
        printf 'FILE %s %s %s %s\n' "$name" "$blocks" "$size" "$digest"; command cat "$path"
    fi
    printf '\n'
}

emit_image commander "$image_directory/commander.tar" >> "$stream_file"
emit_image validation "$image_directory/validation.tar" >> "$stream_file"
emit_image owner-gateway "$image_directory/owner-gateway.tar" >> "$stream_file"
emit_image platform-commander-api "$platform_image_directory/commander-api.tar" >> "$stream_file"
emit_image platform-commander-worker "$platform_image_directory/commander-worker.tar" >> "$stream_file"
emit_file platform-revision "$platform_image_directory/platform-revision.bundle" >> "$stream_file"
printf 'END\n' >> "$stream_file"

ssh -i "$HOME/.ssh/ptw_commander" -o IdentitiesOnly=yes root@165.245.212.184 \
    "set -e; exec 9>/run/lock/ptw-maintenance.lock; flock -n 9 || exit 73; git -C /root/ptw diff --quiet; git -C /root/ptw diff --cached --quiet; export PTW_MAINTENANCE_LOCK_HELD=1; git -C /root/ptw fetch origin '$revision'; git -C /root/ptw merge --ff-only '$revision'; exec /root/ptw/scripts/deploy_ptw_serial.sh '$release_tag' '$revision' '$platform_revision' '$confirmation'" \
    < "$stream_file"

npm --prefix apps/commander-web run check
firebase deploy --only hosting --config firebase.natal-placeholder.json
firebase deploy --only hosting
python3 skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py
