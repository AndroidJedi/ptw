#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 4 || $1 != --release-tag || $3 != --branch ]]; then
    echo "usage: $0 --release-tag TAG --branch god-deploy/ID" >&2
    exit 2
fi
release_tag=$2
branch=$4
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || exit 2
[[ $branch =~ ^god-deploy/[0-9a-f-]{36}$ ]] || exit 2
: "${PTW_MOBILE_DEPLOY_SSH_KEY:?set PTW_MOBILE_DEPLOY_SSH_KEY}"
: "${PTW_MOBILE_DEPLOY_KNOWN_HOSTS:?set PTW_MOBILE_DEPLOY_KNOWN_HOSTS}"

revision=$(git rev-parse HEAD)
[[ $revision =~ ^[0-9a-f]{40}$ && -z $(git status --porcelain) ]] || {
    echo "mobile release requires a clean committed candidate" >&2; exit 1;
}
release_directory=".local/releases/$release_tag"
plan="$release_directory/release-plan.json"
python3 scripts/plan_ptw_release.py --validate "$plan" --target "$revision" \
    --release-tag "$release_tag" >/dev/null
[[ $(python3 -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["migrations"]))' "$plan") == 0 ]] || {
    echo "mobile release does not accept migrations" >&2; exit 1;
}

sha256_file() {
    local line
    line=$(sha256sum "$1")
    printf '%s\n' "${line%% *}"
}
emit_artifact() {
    local kind=$1 name=$2 path=$3 size blocks padding digest
    size=$(stat -c %s "$path")
    blocks=$(( (size + 1048575) / 1048576 ))
    padding=$(( blocks * 1048576 - size ))
    digest=$(sha256_file "$path")
    printf '%s %s %s %s %s\n' "$kind" "$name" "$blocks" "$size" "$digest"
    command cat "$path"
    [[ $padding -eq 0 ]] || dd if=/dev/zero bs="$padding" count=1 status=none
    printf '\n'
}
plan_value() {
    python3 - "$plan" "$1" "$2" <<'PY'
import json, sys
print("1" if json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]][sys.argv[3]] else "0")
PY
}
emit_image() {
    local component=$1 archive=$2
    if [[ $(plan_value build "$component") == 1 ]]; then
        [[ -f $release_directory/$archive ]] || { echo "missing $component image" >&2; exit 1; }
        emit_artifact IMAGE "$component" "$release_directory/$archive"
    else
        printf 'REUSE %s\n' "$component"
    fi
}
emit_web() {
    local target=$1 archive=$2
    if [[ $(plan_value hosting "$target") == 1 ]]; then
        [[ -f $release_directory/$archive ]] || { echo "missing $target web archive" >&2; exit 1; }
        emit_artifact WEB "$target" "$release_directory/$archive"
    else
        printf 'REUSE %s\n' "$target"
    fi
}

{
    printf 'PTW-MOBILE-RELEASE 1 %s %s %s\n' "$release_tag" "$revision" "$branch"
    emit_web owner-console owner-console.tar.gz
    emit_web public-landings public-landings.tar.gz
    printf 'PTW-PRESERVING-STREAM 1\n'
    emit_image commander commander.tar
    emit_image validation validation.tar
    emit_image owner-gateway owner-gateway.tar
    emit_image commander-god commander-god.tar
    printf 'REUSE platform-commander-api\n'
    printf 'REUSE platform-commander-worker\n'
    printf 'REUSE platform-codex-auth\n'
    printf 'REUSE platform-revision\n'
    emit_artifact FILE release-plan "$plan"
    printf 'END\n'
} | ssh -i "$PTW_MOBILE_DEPLOY_SSH_KEY" -o IdentitiesOnly=yes \
    -o UserKnownHostsFile="$PTW_MOBILE_DEPLOY_KNOWN_HOSTS" -o StrictHostKeyChecking=yes \
    ptw-release@165.245.212.184

echo "Mobile preserving release $release_tag completed"
