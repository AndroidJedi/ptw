#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must identify the isolated old application database}"
backup_root=${IDEA_BACKUP_DIR:-/var/backups/ptw-idea-generation}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
umask 077
mkdir -p "$backup_root"
target="$backup_root/old-ptw-commander-$timestamp.sql.gz"
pg_dump --dbname="$DATABASE_URL" --format=plain --no-owner --no-acl | gzip -9 > "$target"
gzip -t "$target"
sha256sum "$target" > "$target.sha256"
printf '%s\n' "$target"
