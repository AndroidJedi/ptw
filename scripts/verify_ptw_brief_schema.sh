#!/bin/sh
set -eu

repository=$(git rev-parse --show-toplevel)
database_container="ptw-brief-schema-$$"
cleanup() {
  docker stop "$database_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker run --rm --detach --name "$database_container" \
  -e POSTGRES_DB=ptw_brief_test \
  -e POSTGRES_USER=ptw_brief_test \
  -e POSTGRES_PASSWORD=ptw-brief-test-only \
  -v "$repository/db/migrations:/migrations:ro" \
  postgres:16-alpine >/dev/null

attempt=0
until docker exec "$database_container" pg_isready -U ptw_brief_test -d ptw_brief_test >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 40 ] || { echo "disposable PostgreSQL did not become ready" >&2; exit 1; }
  sleep 1
done

apply_migrations() {
  docker exec "$database_container" sh -eu -c '
    args="-X -v ON_ERROR_STOP=1 -U ptw_brief_test -d ptw_brief_test"
    psql $args -c "CREATE TABLE IF NOT EXISTS commander_schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT clock_timestamp())" >/dev/null
    for migration in /migrations/*.sql; do
      name=$(basename "$migration")
      applied=$(psql $args -qAtc "SELECT count(*) FROM commander_schema_migrations WHERE name='"'"'$name'"'"'")
      if [ "$applied" = 0 ]; then
        psql $args -f "$migration" >/dev/null
        psql $args -c "INSERT INTO commander_schema_migrations(name) VALUES ('"'"'$name'"'"')" >/dev/null
      fi
    done
  '
}

apply_migrations
apply_migrations

actual=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
expected=$(cat <<'TABLES'
commander_audit_events
commander_control
commander_entities
commander_human_feedback
commander_operation_guard
commander_relationships
commander_schema_migrations
commander_sources
commander_weight_updates
product_brief_approvals
product_briefs
validation_generation_attempts
validation_projects
validation_provider_invocations
TABLES
)
[ "$actual" = "$expected" ] || {
  echo "Product Brief v1 schema differs from the exact table allowlist" >&2
  printf 'actual:\n%s\n' "$actual" >&2
  exit 1
}

docker exec "$database_container" psql -X -qAt -v ON_ERROR_STOP=1 \
  -U ptw_brief_test -d ptw_brief_test <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM commander_schema_migrations) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='001_ptw_brief_v1.sql'
     ) THEN
    RAISE EXCEPTION 'the database must contain one Product Brief v1 baseline migration';
  END IF;
  IF (SELECT count(*) FROM commander_control) <> 1
     OR (SELECT count(*) FROM commander_operation_guard) <> 1 THEN
    RAISE EXCEPTION 'bounded singleton control rows are missing';
  END IF;
END $$;
SQL

echo "Verified the single clean Product Brief v1 schema and idempotent migration journey."
