#!/bin/sh
set -eu

exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }

if [ "$#" -ne 2 ] || [ "$2" != "--confirm-replace-current-state" ]; then
  echo "usage: $0 /absolute/path/to/backup --confirm-replace-current-state" >&2
  exit 2
fi

backup=$1
case "$backup" in
  /*) ;;
  *) echo "backup path must be absolute" >&2; exit 2 ;;
esac

scripts/verify_commander_backup.sh "$backup"
compose="docker compose --env-file /opt/ptw/platform/.env --env-file .env.commander -f docker-compose.commander.yml"
$compose stop commander-api
$compose stop commander-worker
$compose rm -f commander-worker
$compose stop commander-ad-worker
$compose rm -f commander-ad-worker
$compose up -d --no-deps --wait --no-build commander-db

$compose exec -T commander-db dropdb -U ptw_commander --force --if-exists ptw_commander
$compose exec -T commander-db createdb -U ptw_commander ptw_commander
$compose exec -T commander-db pg_restore \
  -U ptw_commander -d ptw_commander --no-owner --no-acl < "$backup/database.dump"

docker run --rm -v ptw_commander-assets:/data alpine:3.22 sh -c \
  'find /data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
docker run --rm \
  -v ptw_commander-assets:/data \
  -v "$backup:/backup:ro" \
  alpine:3.22 tar -C /data -xzf /backup/assets.tar.gz

$compose run --rm --no-deps commander-migrate
$compose up -d --no-deps --wait --no-build commander-api
echo "restore complete; verify /healthz and /readyz"
