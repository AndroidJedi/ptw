#!/bin/sh
set -eu

database_args="-v ON_ERROR_STOP=1 -h commander-db -U ptw_commander -d ${PTW_MIGRATION_DATABASE:-ptw_commander}"
psql $database_args -c "CREATE TABLE IF NOT EXISTS commander_schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT clock_timestamp(), sha256 text); ALTER TABLE commander_schema_migrations ADD COLUMN IF NOT EXISTS sha256 text"

for file in /migrations/*.sql; do
  name=$(basename "$file")
  case "$name" in *[!a-zA-Z0-9_.-]*) echo "Invalid migration filename" >&2; exit 1 ;; esac
  digest=$(sha256sum "$file"); digest=${digest%% *}
  applied=$(psql $database_args -Atc "SELECT count(*) FROM commander_schema_migrations WHERE name = '$name'")
  if [ "$applied" = "0" ]; then
    # Existing migrations wrap their SQL in BEGIN/COMMIT. Strip only those
    # standalone outer statements and include the ledger in the same transaction.
    { printf 'BEGIN;\n'; sed '/^BEGIN;$/d; /^COMMIT;$/d' "$file"; printf "\nINSERT INTO commander_schema_migrations (name,sha256) VALUES ('%s','%s');\nCOMMIT;\n" "$name" "$digest"; } | psql $database_args
  else
    known=$(psql $database_args -Atc "SELECT coalesce(sha256,'') FROM commander_schema_migrations WHERE name='$name'")
    if [ -n "$known" ] && [ "$known" != "$digest" ]; then
      echo "Applied migration checksum changed: $name" >&2; exit 1
    fi
    if [ -z "$known" ]; then psql $database_args -c "UPDATE commander_schema_migrations SET sha256='$digest' WHERE name='$name' AND sha256 IS NULL"; fi
  fi
done
