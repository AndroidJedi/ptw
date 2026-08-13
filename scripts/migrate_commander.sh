#!/bin/sh
set -eu

database_args="-v ON_ERROR_STOP=1 -h commander-db -U ptw_commander -d ptw_commander"
psql $database_args -c "CREATE TABLE IF NOT EXISTS commander_schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT clock_timestamp())"

for file in /migrations/*.sql; do
  name=$(basename "$file")
  applied=$(psql $database_args -Atc "SELECT count(*) FROM commander_schema_migrations WHERE name = '$name'")
  if [ "$applied" = "0" ]; then
    psql $database_args -f "$file"
    psql $database_args -c "INSERT INTO commander_schema_migrations (name) VALUES ('$name')"
  fi
done
