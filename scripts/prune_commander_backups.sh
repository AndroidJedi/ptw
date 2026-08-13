#!/bin/sh
set -eu

backup_root=${1:-/opt/ptw/commander-backups}
case "$backup_root" in
  /opt/ptw/commander-backups) ;;
  *) echo "refusing to prune unexpected directory: $backup_root" >&2; exit 2 ;;
esac

# Keep two weeks of daily local recovery points. Offsite retention is separate.
find "$backup_root" -mindepth 1 -maxdepth 1 -type d -mtime +14 \
  -name '20????????T??????Z' -exec rm -rf -- {} +
