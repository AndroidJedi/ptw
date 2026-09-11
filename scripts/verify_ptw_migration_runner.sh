#!/bin/bash
# Exercise the actual migration runner only against disposable PostgreSQL.
set -Eeuo pipefail
repository=$(git rev-parse --show-toplevel)
temporary=$(mktemp -d /tmp/ptw-migration-canary.XXXXXX)
container="ptw-migration-canary-$$"
cleanup() {
    docker stop "$container" >/dev/null 2>&1 || true
    [[ $temporary == /tmp/ptw-migration-canary.* ]] && rm -rf -- "$temporary"
}
trap cleanup EXIT
mkdir "$temporary/migrations"
cp "$repository"/db/migrations/*.sql "$temporary/migrations/"
docker run --rm -d --name "$container" --hostname commander-db \
    -e POSTGRES_USER=ptw_commander -e POSTGRES_DB=ptw_commander -e POSTGRES_PASSWORD=disposable-canary-only \
    -v "$temporary/migrations:/migrations:ro" -v "$repository/scripts/migrate_commander.sh:/migration-runner:ro" postgres:16-alpine >/dev/null
for attempt in {1..40}; do
    if docker exec -e PGPASSWORD=disposable-canary-only "$container" \
        psql -h 127.0.0.1 -U ptw_commander -d ptw_commander -qAtc 'SELECT 1' >/dev/null 2>&1; then break; fi
    sleep 1
done
run_migrations() { docker exec -e PGPASSWORD=disposable-canary-only "$container" sh /migration-runner >/dev/null; }
query() { docker exec "$container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander -c "$1"; }
run_migrations
run_migrations
[[ $(query "SELECT count(*) FROM commander_schema_migrations WHERE sha256 IS NULL OR length(sha256)<>64") == 0 ]]
printf 'BEGIN;\nCREATE TABLE migration_atomicity_probe(id integer);\nSELECT 1/0;\nCOMMIT;\n' > "$temporary/migrations/999_runtime_canary.sql"
if run_migrations 2>/dev/null; then echo "Invalid migration unexpectedly succeeded" >&2; exit 1; fi
[[ $(query "SELECT to_regclass('public.migration_atomicity_probe') IS NULL") == t ]]
[[ $(query "SELECT count(*) FROM commander_schema_migrations WHERE name='999_runtime_canary.sql'") == 0 ]]
printf 'BEGIN;\nCREATE TABLE migration_atomicity_probe(id integer PRIMARY KEY,label text);\nINSERT INTO migration_atomicity_probe VALUES(1, '\''before'\'');\nCOMMIT;\n' > "$temporary/migrations/999_runtime_canary.sql"
run_migrations
query "UPDATE migration_atomicity_probe SET label='after' WHERE id=1" >/dev/null
[[ $(query "BEGIN READ ONLY; SELECT count(*)=1 AND min(label)='after' FROM migration_atomicity_probe; ROLLBACK;") == t ]]
printf '\n-- edited after application\n' >> "$temporary/migrations/999_runtime_canary.sql"
if run_migrations 2>/dev/null; then echo "Changed applied checksum unexpectedly accepted" >&2; exit 1; fi
echo "Real migration runner passed idempotency, atomic failure, transformation check and applied-checksum rejection"
