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

revision=${PTW_RELEASE_TARGET_REVISION:-$(git rev-parse HEAD)}
[[ $revision =~ ^[0-9a-f]{40}$ && -z $(git status --porcelain) ]] || {
    echo "mobile release requires a clean committed candidate" >&2; exit 1;
}
release_directory=".local/releases/$release_tag"
plan="$release_directory/release-plan.json"
python3 - "$release_directory" "$revision" <<'PY'
import hashlib, json, pathlib, sys
directory = pathlib.Path(sys.argv[1])
manifest = json.loads((directory / 'artifact-digests.json').read_text())
allowed = {'release-plan.json','commander.tar','validation.tar','owner-gateway.tar','commander-god.tar','owner-console.tar.gz','public-landings.tar.gz'}
assert manifest['revision'] == sys.argv[2] and set(manifest['sha256']) <= allowed
assert 'release-plan.json' in manifest['sha256']
for name, digest in manifest['sha256'].items():
    path = directory / name
    assert not path.is_symlink()
    with path.open('rb') as source:
        assert hashlib.file_digest(source, 'sha256').hexdigest() == digest, 'Artifact digest mismatch'
plan = json.loads((directory / 'release-plan.json').read_text())
for component, changed in plan['build'].items():
    assert not changed or component + '.tar' in manifest['sha256']
for target, changed in plan['hosting'].items():
    assert not changed or target + '.tar.gz' in manifest['sha256']
print('Candidate revision and artifact digests verified')
PY
python3 scripts/plan_ptw_release.py --validate "$plan" --target "$revision" \
    --release-tag "$release_tag" >/dev/null

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

transport_heartbeat_pid=
stop_transport_heartbeat() {
    if [[ -n ${transport_heartbeat_pid:-} ]]; then
        kill "$transport_heartbeat_pid" 2>/dev/null || true
        wait "$transport_heartbeat_pid" 2>/dev/null || true
        transport_heartbeat_pid=
    fi
}
trap stop_transport_heartbeat EXIT
(
    while sleep 20; do
        echo "PTW release transport is still active" >&2
    done
) &
transport_heartbeat_pid=$!
if {
    printf 'PTW-MOBILE-RELEASE 2 %s %s %s\n' "$release_tag" "$revision" "$branch"
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
    -o ServerAliveInterval=15 -o ServerAliveCountMax=40 -o TCPKeepAlive=yes \
    ptw-release@165.245.212.184; then
    publish_status=0
else
    publish_status=$?
fi
stop_transport_heartbeat
trap - EXIT
[[ $publish_status -eq 0 ]] || exit "$publish_status"

echo "Mobile preserving release $release_tag completed"
