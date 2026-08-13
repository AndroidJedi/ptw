#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /absolute/backup-root" >&2
  exit 2
fi

backup_root=$1
case "$backup_root" in
  /*) ;;
  *) echo "backup root must be an absolute path" >&2; exit 2 ;;
esac

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$backup_root/$timestamp"
mkdir -p "$destination"
chmod 700 "$backup_root" "$destination"

compose="docker compose --env-file .env.commander -f docker-compose.commander.yml"
$compose exec -T commander-db pg_dump \
  -U ptw_commander -d ptw_commander --format=custom --no-owner --no-acl \
  > "$destination/database.dump"

docker run --rm \
  -v ptw_commander-assets:/data:ro \
  -v "$destination:/backup" \
  alpine:3.22 tar -C /data -czf /backup/assets.tar.gz .

git rev-parse HEAD > "$destination/git-revision.txt"
cp config/commander/policies.json "$destination/policies.json"
(
  cd "$destination"
  sha256sum database.dump assets.tar.gz git-revision.txt policies.json > SHA256SUMS
)
chmod 600 "$destination"/*
echo "$destination"
