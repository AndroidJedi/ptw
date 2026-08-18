#!/bin/sh
set -eu
for file in /app/ideaGeneration/migrations/*.sql; do
  version=$(basename "$file" .sql)
  if ! psql "$DATABASE_URL" -Atqc "select 1 from schema_migrations where version='$version'" 2>/dev/null | grep -q 1; then
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
  fi
done
