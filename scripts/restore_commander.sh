#!/bin/sh
set -eu

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
compose="docker compose --env-file .env.commander -f docker-compose.commander.yml"
$compose stop commander-api commander-worker
$compose up -d commander-db

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

$compose up -d commander-api commander-worker
echo "restore complete; verify /healthz and /readyz"
