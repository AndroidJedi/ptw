#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 RELEASE_TAG GIT_REVISION PLATFORM_GIT_REVISION 'RESET PTW PRODUCTION'" >&2
    exit 2
fi
release_tag=$1
git_revision=$2
platform_git_revision=$3
confirmation=$4
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || { echo "invalid or unversioned release tag" >&2; exit 2; }
[[ $git_revision =~ ^[0-9a-f]{40}$ ]] || { echo "GIT_REVISION must be a full commit SHA" >&2; exit 2; }
[[ $platform_git_revision =~ ^[0-9a-f]{40}$ ]] || { echo "PLATFORM_GIT_REVISION must be a full commit SHA" >&2; exit 2; }
[[ $confirmation == "RESET PTW PRODUCTION" ]] || {
    echo "exact production reset confirmation is required" >&2; exit 2;
}
[[ $(id -u) -eq 0 ]] || { echo "production deployment must run as root" >&2; exit 1; }

if [[ ${PTW_MAINTENANCE_LOCK_HELD:-0} != 1 ]]; then
    exec 9>/run/lock/ptw-maintenance.lock
    flock -n 9 || { echo "another PTW maintenance session is active" >&2; exit 73; }
elif [[ ! -e /proc/self/fd/9 ]]; then
    echo "maintenance lock inheritance is invalid" >&2
    exit 73
fi

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
validation_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")
platform_compose=(docker compose --env-file "$platform/.env" --project-directory "$platform" -f "$platform/docker-compose.yml")
release_directory=$(mktemp -d /var/tmp/ptw-release.XXXXXX)
trap 'rm -rf -- "$release_directory"' EXIT
deployment_started_at=$(date --iso-8601=seconds)

[[ -f "$platform/.env" && -f "$repository/.env.commander" && -f "$repository/.env.owner-gateway" ]] || {
    echo "required production environment file is missing" >&2; exit 1;
}
# Remove obsolete first-attempt settings without reading or printing values.
sed -i '/^DATAFORSEO_/d;/^POSITIONING_/d;/^LANDING_/d;/^YOUTUBE_/d;/^OWNER_CONTROL_DATABASE=/d;/^ROOT_BROKER_/d;/^CODEX_/d;/^GH_CONFIG_/d' "$repository/.env.owner-gateway"
pexels_line=$(grep '^PEXELS_API_KEY=' "$repository/.env.owner-gateway" || true)
pexels_value=${pexels_line#PEXELS_API_KEY=}
[[ ${#pexels_value} -ge 20 && $pexels_value != replace-with-pexels-api-key ]] || {
    echo "a root-owned PEXELS_API_KEY is required before cutover" >&2; exit 1;
}
unset pexels_line pexels_value
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]] || {
    echo "production repository has tracked changes" >&2; exit 1;
}
git -C "$repository" fetch origin "$git_revision"
git -C "$repository" merge --ff-only "$git_revision"
[[ $(git -C "$repository" rev-parse HEAD) == "$git_revision" ]] || { echo "requested revision was not deployed" >&2; exit 1; }

echo "PTW serial lock acquired"
uptime
free -m
df -h /
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
journalctl -k -b 0 --no-pager -n 80 --case-sensitive=false --grep='out of memory|oom|killed process' 2>/dev/null || true

receive_image() {
    local stream_name=$1 expected_tag=$2 header kind name blocks digest image_file checksum_line actual_digest architecture
    IFS=' ' read -r kind name blocks digest
    [[ $kind == IMAGE && $name == "$stream_name" && $blocks =~ ^[1-9][0-9]*$ && $digest =~ ^[0-9a-f]{64}$ ]] || {
        echo "invalid image stream header for $stream_name" >&2; exit 1;
    }
    image_file="$release_directory/$stream_name.tar"
    dd iflag=fullblock bs=1048576 count="$blocks" of="$image_file" status=none
    IFS= read -r header
    [[ -z $header ]] || { echo "invalid image stream separator" >&2; exit 1; }
    checksum_line=$(sha256sum "$image_file"); actual_digest=${checksum_line%% *}
    [[ $actual_digest == "$digest" ]] || { echo "checksum mismatch for $stream_name" >&2; exit 1; }
    docker load --input "$image_file"
    architecture=$(docker image inspect "$expected_tag" --format '{{.Architecture}}')
    [[ $architecture == amd64 ]] || { echo "$expected_tag is not linux/amd64" >&2; exit 1; }
    echo "$expected_tag loaded and verified"
    rm -f -- "$image_file"
}

receive_image commander "ptw-commander:$release_tag"
receive_image validation "ptw-validation:$release_tag"
receive_image owner-gateway "ptw-owner-gateway:$release_tag"
receive_image platform-commander-api "ptw-agent-platform-commander-api:$release_tag"
receive_image platform-commander-worker "ptw-agent-platform-commander-worker:$release_tag"
receive_file() {
    local stream_name=$1 header kind name blocks size digest artifact_file checksum_line actual_digest
    IFS=' ' read -r kind name blocks size digest
    [[ $kind == FILE && $name == "$stream_name" && $blocks =~ ^[1-9][0-9]*$ && $size =~ ^[1-9][0-9]*$ && $digest =~ ^[0-9a-f]{64}$ ]] || {
        echo "invalid release artifact header for $stream_name" >&2; exit 1;
    }
    (( size <= blocks * 1048576 && size > (blocks - 1) * 1048576 )) || {
        echo "invalid exact size for $stream_name" >&2; exit 1;
    }
    artifact_file="$release_directory/$stream_name.bundle"
    dd iflag=fullblock bs=1048576 count="$blocks" of="$artifact_file" status=none
    IFS= read -r header
    [[ -z $header ]] || { echo "invalid release artifact separator" >&2; exit 1; }
    truncate --size "$size" "$artifact_file"
    checksum_line=$(sha256sum "$artifact_file"); actual_digest=${checksum_line%% *}
    [[ $actual_digest == "$digest" ]] || { echo "checksum mismatch for $stream_name" >&2; exit 1; }
}
receive_file platform-revision
IFS= read -r stream_end
[[ $stream_end == END ]] || { echo "image stream did not terminate cleanly" >&2; exit 1; }
for image in ptw-commander ptw-validation ptw-owner-gateway; do
    [[ $(docker image inspect "$image:$release_tag" --format '{{.RepoTags}}') == *"$image:$release_tag"* ]] || exit 1
done
for image in ptw-agent-platform-commander-api ptw-agent-platform-commander-worker; do
    [[ $(docker image inspect "$image:$release_tag" --format '{{.RepoTags}}') == *"$image:$release_tag"* ]] || exit 1
done

export PTW_IMAGE_TAG=$release_tag
"${commander_compose[@]}" up -d --no-deps --wait commander-db

[[ -z $(git -C "$platform" status --porcelain --untracked-files=no) ]] || {
    echo "platform repository has tracked changes" >&2; exit 1;
}
old_platform_api_image=$(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}')
old_platform_worker_image=$(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}')
case "$old_platform_api_image" in
    ptw-agent-platform-commander-api:*) old_platform_tag=${old_platform_api_image#ptw-agent-platform-commander-api:} ;;
    *) echo "unexpected deployed platform API image: $old_platform_api_image" >&2; exit 1 ;;
esac
[[ $old_platform_worker_image == "ptw-agent-platform-commander-worker:$old_platform_tag" ]] || {
    echo "deployed platform API and worker tags do not match" >&2; exit 1;
}
git -C "$platform" bundle verify "$release_directory/platform-revision.bundle"
git -C "$platform" fetch "$release_directory/platform-revision.bundle" HEAD
[[ $(git -C "$platform" rev-parse FETCH_HEAD) == "$platform_git_revision" ]] || {
    echo "platform revision bundle does not match the requested commit" >&2; exit 1;
}
git -C "$platform" merge --ff-only "$platform_git_revision"
[[ $(git -C "$platform" rev-parse HEAD) == "$platform_git_revision" ]] || {
    echo "requested platform revision was not deployed" >&2; exit 1;
}

export PTW_PLATFORM_IMAGE_TAG=$release_tag
# Render the exact production configuration before replacing either bridge
# service. A comma-delimited tmpfs option must remain one mount item.
rendered_platform_compose="$release_directory/platform-compose.yml"
"${platform_compose[@]}" config > "$rendered_platform_compose"
if grep -Eq '^[[:space:]]*-[[:space:]]+mode=' "$rendered_platform_compose"; then
    echo "platform Compose split a tmpfs option into an invalid mount item" >&2
    exit 1
fi
# Put the enforcing worker in place before the API admits PTW structured modes.
"${platform_compose[@]}" up -d --no-deps --no-build --wait commander-worker
"${platform_compose[@]}" up -d --no-deps --no-build --wait commander-api

restore_platform_images() {
    export PTW_PLATFORM_IMAGE_TAG=$old_platform_tag
    "${platform_compose[@]}" up -d --no-deps --no-build --wait commander-api
    "${platform_compose[@]}" up -d --no-deps --no-build --wait commander-worker
}

# Run a fresh strict-model invocation through the newly deployed API and worker
# for every retained PTW mode. Restore the prior images if any canary fails;
# the irreversible Commander reset has not started at this point.
if ! "${validation_compose[@]}" run --rm --no-deps validation-api \
    python -m validation_pipeline.verify_bridge_contract; then
    restore_platform_images
    echo "platform bridge canary failed; prior platform images restored" >&2
    exit 1
fi
if ! "${validation_compose[@]}" run --rm --no-deps validation-api \
    python -m validation_pipeline.verify_pexels; then
    restore_platform_images
    echo "Pexels source canary failed; prior platform images restored" >&2
    exit 1
fi
sed -i "s/^PTW_PLATFORM_IMAGE_TAG=.*/PTW_PLATFORM_IMAGE_TAG=$release_tag/" "$platform/.env"
grep -qx "PTW_PLATFORM_IMAGE_TAG=$release_tag" "$platform/.env" || {
    echo "platform release tag was not persisted" >&2; exit 1;
}

PTW_MAINTENANCE_LOCK_HELD=1 "$repository/scripts/reset_ptw.sh" \
    --confirm "$confirmation" --release-tag "$release_tag"

if grep -q '^PTW_IMAGE_TAG=' "$repository/.env.commander"; then
    sed -i "s/^PTW_IMAGE_TAG=.*/PTW_IMAGE_TAG=$release_tag/" "$repository/.env.commander"
else
    printf '\nPTW_IMAGE_TAG=%s\n' "$release_tag" >> "$repository/.env.commander"
fi
grep -qx "PTW_IMAGE_TAG=$release_tag" "$repository/.env.commander" || {
    echo "application release tag was not persisted" >&2; exit 1;
}

"$repository/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh"
(set -a; . "$platform/.env"; . "$repository/.env.commander"; \
  . "$repository/.env.owner-gateway"; set +a; \
  python3 "$repository/scripts/send_ptw_bot_canary.py")
PTW_MAINTENANCE_LOCK_HELD=1 "$repository/scripts/audit_ptw_1gb.sh"

commander_postgres=$("${commander_compose[@]}" ps -q commander-db)
for sample in {1..30}; do
    docker exec "$commander_postgres" psql -qAt -U ptw_commander -d ptw_commander \
        -c "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state <> 'idle' AND query NOT LIKE '%pg_stat_activity%';"
    sleep 1
done
free -m
swapon --show
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
mem_available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
[[ $mem_available_kb -gt 256000 ]] || { echo "idle MemAvailable is below 250 MiB" >&2; exit 1; }
new_oom_events=$(journalctl --quiet -k -b 0 --since "$deployment_started_at" --no-pager --case-sensitive=false --grep='out of memory|oom|killed process' 2>/dev/null || true)
[[ -z $new_oom_events ]] || { echo "new OOM evidence appeared during deployment" >&2; echo "$new_oom_events"; exit 1; }
systemctl stop ptw-validation-24h-audit.timer ptw-validation-24h-audit.service >/dev/null 2>&1 || true
systemctl reset-failed ptw-validation-24h-audit.timer ptw-validation-24h-audit.service >/dev/null 2>&1 || true
followup_audit_at=$(date --utc --date='+24 hours' '+%Y-%m-%d %H:%M:%S UTC')
systemd-run --quiet --unit=ptw-validation-24h-audit --on-calendar="$followup_audit_at" \
    --timer-property=Persistent=true "$repository/scripts/audit_ptw_1gb.sh"
systemctl is-active --quiet ptw-validation-24h-audit.timer || {
    echo "24-hour PTW resource audit timer was not scheduled" >&2
    exit 1
}
echo "PTW Product Brief and Studio APIs deployed from a clean production reset at $git_revision"
