#!/bin/bash
set -Eeuo pipefail

[[ $(id -u) -eq 0 ]] || { echo "audit must run as root" >&2; exit 1; }
exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
positioning_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-marketing-positioning --project-directory "$repository" -f "$repository/docker-compose.marketing-positioning.yml")

uptime
free -m
df -h /
swapon --show
ps -eo pid,ppid,rss,etimes,stat,comm --sort=-rss
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'

for retired_pattern in idea-generation commander-worker ad-worker; do
    retired=$(docker ps -q --filter "name=$retired_pattern")
    [[ -z $retired ]] || {
        echo "retired container matching $retired_pattern is running" >&2
        exit 1
    }
done
positioning_container=$("${positioning_compose[@]}" ps -q marketing-positioning-api)
[[ -n $positioning_container ]] || { echo "Marketing Positioning is unavailable" >&2; exit 1; }

commander_postgres=$("${commander_compose[@]}" ps -q commander-db)
[[ -n $commander_postgres ]] || { echo "Commander PostgreSQL is unavailable" >&2; exit 1; }
docker exec "$commander_postgres" psql -At -U ptw_commander -d ptw_commander \
    -c "SELECT application_name,state,count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY application_name,state ORDER BY application_name,state;"

curl --fail --max-time 2 --silent --show-error http://127.0.0.1:8091/readyz >/dev/null
curl --fail --max-time 3 --silent --show-error http://127.0.0.1:8093/readyz >/dev/null
curl --fail --max-time 2 --silent --show-error http://127.0.0.1:8092/healthz >/dev/null

mem_available_kb=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
[[ $mem_available_kb -gt 256000 ]] || {
    echo "MemAvailable is below 250 MiB" >&2
    exit 1
}
oom_events=$(journalctl --quiet -k --since '24 hours ago' --no-pager --case-sensitive=false \
    --grep='out of memory|oom|killed process' 2>/dev/null || true)
[[ -z $oom_events ]] || {
    echo "OOM evidence exists in the last 24 hours" >&2
    echo "$oom_events"
    exit 1
}

unexpected_pollers=$(ps -eo args= | grep -E 'idea_generation|commander\.worker|commander\.ad_worker|owner_gateway.*(poll|webhook)|marketing_positioning.*(poll|webhook)' | grep -v grep || true)
[[ -z $unexpected_pollers ]] || {
    echo "unexpected retired or additional Telegram polling process is running" >&2
    echo "$unexpected_pollers"
    exit 1
}

echo "PTW 1 GB follow-up audit passed"
