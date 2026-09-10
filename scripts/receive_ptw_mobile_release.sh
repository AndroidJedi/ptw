#!/bin/bash
set -Eeuo pipefail

[[ $(id -u) -eq 0 ]] || { echo "mobile release receiver must run as root" >&2; exit 1; }
IFS= read -r header
read -r protocol version release_tag revision branch extra <<< "$header"
[[ $protocol == PTW-MOBILE-RELEASE && $version == 1 && -z ${extra:-} ]] || exit 2
[[ $release_tag =~ ^god-mobile-[0-9]{8}-[0-9a-f]{12}$ ]] || exit 2
[[ $revision =~ ^[0-9a-f]{40}$ && $branch =~ ^god-deploy/[0-9a-f-]{36}$ ]] || exit 2

release_directory=$(mktemp -d /var/tmp/ptw-mobile-release.XXXXXX)
cleanup() { rm -rf -- "$release_directory"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

receive_web() {
    local expected=$1 header kind name blocks size digest archive checksum actual
    IFS= read -r header
    if [[ $header == "REUSE $expected" ]]; then
        printf -v "web_${expected//-/_}" '%s' reuse
        return
    fi
    read -r kind name blocks size digest <<< "$header"
    [[ $kind == WEB && $name == "$expected" && $blocks =~ ^[1-9][0-9]*$ \
       && $size =~ ^[1-9][0-9]*$ && $digest =~ ^[0-9a-f]{64}$ ]] || exit 2
    (( size <= blocks * 1048576 && size > (blocks - 1) * 1048576 && size <= 104857600 )) || exit 2
    archive="$release_directory/$expected.tar.gz"
    dd iflag=fullblock bs=1048576 count="$blocks" of="$archive" status=none
    IFS= read -r header
    [[ -z $header ]] || exit 2
    truncate --size "$size" "$archive"
    checksum=$(sha256sum "$archive"); actual=${checksum%% *}
    [[ $actual == "$digest" ]] || exit 1
    [[ -z $(tar -tzf "$archive" | awk '/(^\/|(^|\/)\.\.($|\/))/ {print; exit}') ]] || exit 1
    printf -v "web_${expected//-/_}" '%s' "$archive"
}
receive_web owner-console
receive_web public-landings

repository=/root/ptw
platform=/opt/ptw/platform
exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]] || {
    echo "production PTW checkout has tracked changes" >&2; exit 1;
}
git -C "$repository" fetch origin "$branch"
[[ $(git -C "$repository" rev-parse FETCH_HEAD) == "$revision" ]] || exit 1
deployed_revision=$(<"$repository/.local/deployed-revision")
[[ $deployed_revision =~ ^[0-9a-f]{40}$ ]]
declared_base=$(git -C "$repository" log -1 --format=%B "$revision" \
    | sed -n 's/^PTW-Base-Revision: \([0-9a-f]\{40\}\)$/\1/p' | tail -1)
[[ $declared_base == "$deployed_revision" ]]
git -C "$repository" merge-base --is-ancestor "$deployed_revision" "$revision"
changed=$(git -C "$repository" diff --name-only "$deployed_revision..$revision")
[[ -n $changed ]]
if printf '%s\n' "$changed" | awk '
  /^\.github\// || /^scripts\// || /^db\/migrations\// || /^deploy\// ||
  /^commander_god\// || /^skills\/ptw-vps-operations\// ||
  /^validation_pipeline\/commander_release\.py$/ ||
  /(^|\/)\.env/ || /(^|\/)Dockerfile$/ ||
  /^(AGENTS\.md|\.dockerignore|\.firebaserc|firebase\.json|docker-compose\.)/ {bad=1}
  END {exit bad ? 0 : 1}
'; then
    echo "mobile candidate changes protected release infrastructure" >&2
    exit 1
fi
git -C "$repository" merge --ff-only "$revision"
platform_revision=$(git -C "$platform" rev-parse HEAD)
export PTW_MAINTENANCE_LOCK_HELD=1
"$repository/scripts/receive_ptw_preserving_release.sh" "$release_tag" "$revision" "$platform_revision"

deploy_hosting() {
    local target=$1 archive=$2 web_root=$3 temp_config="$release_directory/firebase-$target.json"
    [[ $archive != reuse ]] || return 0
    mkdir -p "$release_directory/$web_root"
    tar -xzf "$archive" --no-same-owner -C "$release_directory/$web_root"
    python3 - "$repository/firebase.json" "$temp_config" "$target" "$web_root" <<'PY'
import json, pathlib, sys
source, output, target, public = sys.argv[1:]
config = json.load(open(source, encoding="utf-8"))
hosting = next(item for item in config["hosting"] if item["target"] == target)
hosting.pop("predeploy", None)
hosting["public"] = public
pathlib.Path(output).write_text(json.dumps({"hosting": [hosting]}), encoding="utf-8")
PY
    cp "$repository/.firebaserc" "$release_directory/.firebaserc"
    docker run --rm --network host \
        -e GOOGLE_APPLICATION_CREDENTIALS=/run/firebase/service-account.json \
        -v /opt/ptw/secrets/firebase-service-account.json:/run/firebase/service-account.json:ro \
        -v "$release_directory:/release:ro" -w /release node:22-bookworm-slim \
        npx --yes firebase-tools@14.17.0 deploy --non-interactive \
        --project provethemwrong-86123 --config "/release/$(basename "$temp_config")" \
        --only "hosting:$target"
}
deploy_hosting public-landings "$web_public_landings" public-dist
deploy_hosting owner-console "$web_owner_console" owner-dist
python3 "$repository/skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py"
echo "PTW mobile release accepted at $revision"
