#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 RELEASE_TAG GIT_REVISION" >&2
    exit 2
fi

release_tag=$1
git_revision=$2
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ ]] || { echo "invalid release tag" >&2; exit 2; }
[[ $git_revision =~ ^[0-9a-f]{40}$ ]] || { echo "GIT_REVISION must be a full commit SHA" >&2; exit 2; }
[[ $(id -u) -eq 0 ]] || { echo "production deployment must run as root" >&2; exit 1; }

if [[ ${PTW_MAINTENANCE_LOCK_HELD:-0} != 1 ]]; then
    exec 9>/run/lock/ptw-maintenance.lock
    if ! flock -n 9; then
        echo "another PTW maintenance session owns /run/lock/ptw-maintenance.lock" >&2
        exit 73
    fi
elif [[ ! -e /proc/self/fd/9 ]]; then
    echo "maintenance lock inheritance is invalid" >&2
    exit 73
fi

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
idea_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.owner-gateway" --project-name ptw-idea-generation --project-directory "$repository" -f "$repository/docker-compose.idea-generation.yml")
release_directory=$(mktemp -d /var/tmp/ptw-release.XXXXXX)
trap 'rm -rf -- "$release_directory"' EXIT
deployment_started_at=$(date --iso-8601=seconds)

echo "PTW serial maintenance lock acquired"
uptime
free -m
df -h /
journalctl -k -b -1 --no-pager -n 80 --case-sensitive=false \
    --grep='out of memory|oom|killed process' 2>/dev/null || true
journalctl -k -b 0 --no-pager -n 80 --case-sensitive=false \
    --grep='out of memory|oom|killed process' 2>/dev/null || true
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
ps -eo pid,ppid,rss,etimes,stat,comm --sort=-rss

[[ -f "$platform/.env" && -f "$repository/.env.commander" && -f "$repository/.env.owner-gateway" ]] || {
    echo "required production environment file is missing" >&2
    exit 1
}
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]] || {
    echo "production repository has tracked changes; refusing to overwrite them" >&2
    exit 1
}
git -C "$repository" fetch origin "$git_revision"
git -C "$repository" merge --ff-only "$git_revision"
[[ $(git -C "$repository" rev-parse HEAD) == "$git_revision" ]] || {
    echo "production repository did not reach requested revision" >&2
    exit 1
}

receive_image() {
    local expected_name=$1
    local expected_tag=$2
    local header kind name blocks digest image_file actual_digest
    IFS=' ' read -r kind name blocks digest
    [[ $kind == IMAGE && $name == "$expected_name" && $blocks =~ ^[1-9][0-9]*$ && $digest =~ ^[0-9a-f]{64}$ ]] || {
        echo "invalid image stream header for $expected_name" >&2
        exit 1
    }
    image_file="$release_directory/$expected_name.tar"
    dd iflag=fullblock bs=1048576 count="$blocks" of="$image_file" status=none
    IFS= read -r header
    [[ -z $header ]] || { echo "invalid image stream separator" >&2; exit 1; }
    checksum_line=$(sha256sum "$image_file")
    actual_digest=${checksum_line%% *}
    [[ $actual_digest == "$digest" ]] || { echo "checksum mismatch for $expected_name" >&2; exit 1; }
    docker load --input "$image_file"
    image_id=$(docker image inspect "$expected_tag" --format '{{.Id}}')
    image_architecture=$(docker image inspect "$expected_tag" --format '{{.Architecture}}')
    [[ $image_architecture == amd64 ]] || {
        echo "$expected_tag is $image_architecture, expected amd64" >&2
        exit 1
    }
    echo "$expected_tag loaded as $image_id ($image_architecture)"
    rm -f -- "$image_file"
}

receive_image commander "ptw-commander:$release_tag"
receive_image idea-generation "ptw-idea-generation:$release_tag"
receive_image owner-gateway "ptw-owner-gateway:$release_tag"
IFS= read -r stream_end
[[ $stream_end == END ]] || { echo "image stream did not terminate cleanly" >&2; exit 1; }

disk_available=$(df --output=avail -B1 /)
available_bytes=${disk_available##*$'\n'}
available_bytes=${available_bytes// /}
swap_names=$(swapon --show=NAME --noheadings)
if [[ $'\n'$swap_names$'\n' != *$'\n/swapfile\n'* ]]; then
    if [[ -e /swapfile ]]; then
        echo "/swapfile exists but is not active; refusing to overwrite it" >&2
        exit 1
    fi
    [[ $available_bytes -ge 4294967296 ]] || {
        echo "less than 4 GiB is free; 2 GiB swap was not created" >&2
        exit 1
    }
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
fi
grep -Fqx '/swapfile none swap sw 0 0' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
printf 'vm.swappiness=10\n' > /etc/sysctl.d/90-ptw-memory.conf
sysctl --system >/dev/null

"${commander_compose[@]}" stop commander-worker
"${commander_compose[@]}" rm -f commander-worker
"${commander_compose[@]}" stop commander-ad-worker
"${commander_compose[@]}" rm -f commander-ad-worker

platform_postgres=$(docker compose --env-file "$platform/.env" --project-directory "$platform" -f "$platform/docker-compose.yml" ps -q postgres)
[[ -n $platform_postgres ]] || { echo "platform PostgreSQL container is unavailable" >&2; exit 1; }
for setting in \
    "shared_buffers = '48MB'" \
    "effective_cache_size = '192MB'" \
    "work_mem = '1MB'" \
    "maintenance_work_mem = '32MB'" \
    "max_connections = '20'" \
    "autovacuum_max_workers = '1'"
do
    docker exec --env "PTW_POSTGRES_SETTING=$setting" "$platform_postgres" sh -c \
        'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER SYSTEM SET $PTW_POSTGRES_SETTING"'
done
docker restart "$platform_postgres"
until docker exec "$platform_postgres" sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null; do
    sleep 1
done

export PTW_IMAGE_TAG=$release_tag
export CREATIVE_RUNTIME_ENABLED=false
export OUTBOUND_NOTIFICATIONS_ENABLED=false
export LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED=true

"${commander_compose[@]}" up -d --no-deps --wait --no-build commander-db
"${commander_compose[@]}" run --rm --no-deps commander-migrate
"${commander_compose[@]}" up -d --no-deps --wait --no-build commander-api
curl --fail --max-time 2 --silent --show-error http://127.0.0.1:8091/readyz >/dev/null

"${idea_compose[@]}" up -d --no-deps --wait --no-build idea-generation-api
curl --fail --max-time 2 --silent --show-error http://127.0.0.1:8093/healthz >/dev/null

"${commander_compose[@]}" up -d --no-deps --wait --no-build owner-gateway
curl --fail --max-time 2 --silent --show-error http://127.0.0.1:8092/healthz >/dev/null

"$repository/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh"

retired_worker=$("${commander_compose[@]}" ps -q commander-worker)
retired_ad_worker=$("${commander_compose[@]}" ps -q commander-ad-worker)
[[ -z $retired_worker && -z $retired_ad_worker ]] || {
    echo "a retired Commander worker is still running" >&2
    exit 1
}

commander_postgres=$("${commander_compose[@]}" ps -q commander-db)
[[ -n $commander_postgres ]] || { echo "Commander PostgreSQL container is unavailable" >&2; exit 1; }
docker exec "$commander_postgres" psql -At -U ptw_commander -d ptw_commander \
    -c "SELECT datname,numbackends,pg_size_pretty(pg_database_size(datname)) FROM pg_stat_database WHERE datname=current_database();"
docker exec "$platform_postgres" sh -c \
    'psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT datname,numbackends,pg_size_pretty(pg_database_size(datname)) FROM pg_stat_database WHERE datname=current_database();"'

for sample in {1..30}
do
    docker exec "$commander_postgres" psql -At -U ptw_commander -d ptw_commander \
        -c "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND state <> 'idle' AND query NOT LIKE '%pg_stat_activity%';"
    sleep 1
done

free -m
swapon --show
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
mem_available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
[[ $mem_available_kb -gt 256000 ]] || {
    echo "idle MemAvailable is below the 250 MiB acceptance boundary" >&2
    exit 1
}
new_oom_events=$(journalctl --quiet -k -b 0 --since "$deployment_started_at" --no-pager \
    --case-sensitive=false --grep='out of memory|oom|killed process' 2>/dev/null || true)
[[ -z $new_oom_events ]] || {
    echo "new OOM evidence appeared during deployment" >&2
    echo "$new_oom_events"
    exit 1
}
echo "PTW APIs deployed serially at $git_revision"
