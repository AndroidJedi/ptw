#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  echo "usage: $0 /absolute/path/to/backup" >&2
  exit 2
fi

backup=$1
(cd "$backup" && sha256sum -c SHA256SUMS)
docker run --rm -i postgres:16-alpine pg_restore --list < "$backup/database.dump" >/dev/null
docker run --rm -v "$backup:/backup:ro" alpine:3.22 tar -tzf /backup/assets.tar.gz >/dev/null
echo "backup verified: $backup"
