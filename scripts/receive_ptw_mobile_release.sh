#!/bin/bash
set -Eeuo pipefail

[[ $(id -u) -eq 0 ]] || { echo "mobile release receiver must run as root" >&2; exit 1; }
IFS= read -r header
read -r protocol version release_tag revision branch extra <<< "$header"
[[ $protocol == PTW-MOBILE-RELEASE && $version == 2 && -z ${extra:-} ]] || exit 2
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
    python3 - "$archive" <<'PY'
import pathlib, sys, tarfile
with tarfile.open(sys.argv[1]) as archive:
    total = 0
    for item in archive:
        path = pathlib.PurePosixPath(item.name)
        if path.is_absolute() or '..' in path.parts or not (item.isfile() or item.isdir()):
            raise SystemExit('Unsafe Hosting archive member')
        total += item.size
        if total > 209715200:
            raise SystemExit('Hosting archive expands beyond its limit')
PY
    printf -v "web_${expected//-/_}" '%s' "$archive"
}
receive_web owner-console
receive_web public-landings

repository=/root/ptw
platform=/opt/ptw/platform
exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }
exec 8>>/opt/ptw/commander-workspace/.git/ptw-commander-operation.lock
flock -n 8 || { echo "Commander is still working; retry deployment after the task finishes" >&2; exit 73; }
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]] || {
    echo "production PTW checkout has tracked changes" >&2; exit 1;
}
git -C "$repository" fetch origin "$branch"
request_revision=$(git -C "$repository" rev-parse FETCH_HEAD)
identifier=${branch#god-deploy/}
record_progress() {
    python3 - "$repository/.local/commander-releases" "$identifier" "$revision" "$1" <<'PY'
import json, os, pathlib, sys, tempfile
directory = pathlib.Path(sys.argv[1])
directory.mkdir(mode=0o700, parents=True, exist_ok=True)
descriptor, name = tempfile.mkstemp(prefix='receipt-', dir=directory)
with os.fdopen(descriptor, 'w') as output:
    json.dump({'id':sys.argv[2], 'revision':sys.argv[3], 'phase':sys.argv[4]}, output)
    output.flush()
    os.fsync(output.fileno())
os.replace(name, directory / (sys.argv[2] + '.json'))
PY
}
git -C "$repository" fetch origin "god-candidate/$identifier"
[[ $(git -C "$repository" rev-parse FETCH_HEAD) == "$revision" ]] || exit 1
deployed_revision=$(<"$repository/.local/deployed-revision")
[[ $deployed_revision =~ ^[0-9a-f]{40}$ ]]
python3 "$repository/scripts/verify_ptw_release_request.py" --repository "$repository" \
    --request "$request_revision" --deployed "$deployed_revision" > "$release_directory/request.json"
[[ $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["revision"])' "$release_directory/request.json") == "$revision" ]]
git -C "$repository" merge-base --is-ancestor "$deployed_revision" "$revision"
changed=$(git -C "$repository" diff --name-only "$deployed_revision..$revision")
[[ -n $changed ]]
# Keep the accepted release tools alive for this entire rollout. New release
# machinery is installed only after acceptance, including receiver self-updates.
mkdir "$release_directory/trusted"
git -C "$repository" archive "$deployed_revision" | tar -x -C "$release_directory/trusted"
export PTW_TRUSTED_RELEASE_ROOT="$release_directory/trusted"
export PTW_PLAN_REPOSITORY="$repository"
export PTW_DEFER_RELEASE_COMMIT=1
record_progress preparing
"$PTW_TRUSTED_RELEASE_ROOT/scripts/ptw_release_recovery.sh" snapshot "$release_directory/recovery"
accepted=0
rollback_release() {
    local status=$?
    trap - EXIT HUP INT TERM
    if [[ $accepted == 0 ]]; then
        if ! "$PTW_TRUSTED_RELEASE_ROOT/scripts/ptw_release_recovery.sh" restore "$release_directory/recovery"; then
            record_progress recovery_failed
            echo "Recovery needs operator attention; protected recovery files retained at $release_directory" >&2
            exit 1
        fi
        record_progress rolled_back
        [[ $status != 0 ]] || status=1
    fi
    cleanup
    exit "$status"
}
trap rollback_release EXIT
trap 'exit 1' HUP INT TERM
git -C "$repository" merge --ff-only "$revision"
platform_revision=$(git -C "$platform" rev-parse HEAD)
export PTW_MAINTENANCE_LOCK_HELD=1
export PTW_MIGRATIONS_AUTHORIZED=1
python3 "$PTW_TRUSTED_RELEASE_ROOT/scripts/verify_ptw_migration_inventory.py" --repository "$repository" --base "$deployed_revision"
record_progress application
"$PTW_TRUSTED_RELEASE_ROOT/scripts/receive_ptw_preserving_release.sh" "$release_tag" "$revision" "$platform_revision"

deploy_hosting() {
    local target=$1
    local archive=$2
    local web_root=$3
    local temp_config="$release_directory/firebase-$target.json"
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
        -v "$release_directory:/release:ro" -w /release \
        node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 \
        npx --yes firebase-tools@14.17.0 deploy --non-interactive \
        --project provethemwrong-86123 --config "/release/$(basename "$temp_config")" \
        --only "hosting:$target"
}
record_progress hosting
deploy_hosting public-landings "$web_public_landings" public-dist
deploy_hosting owner-console "$web_owner_console" owner-dist
python3 "$repository/skills/ptw-owner-console-incident/scripts/audit_live_owner_console.py"
record_progress infrastructure
"$PTW_TRUSTED_RELEASE_ROOT/scripts/apply_ptw_release_configuration.sh" "$repository"
revision_state=$(mktemp "$repository/.local/deployed-revision.next.XXXXXX")
printf '%s\n' "$revision" > "$revision_state"
chmod 0600 "$revision_state"
mv -f "$revision_state" "$repository/.local/deployed-revision"
accepted=1
record_progress accepted
echo "PTW mobile release accepted at $revision"
