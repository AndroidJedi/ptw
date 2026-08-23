#!/bin/sh
set -eu

application_container=ptw-v2-app-schema-check
platform_container=ptw-v2-platform-schema-check
for container in "$application_container" "$platform_container"; do
  if docker container inspect "$container" >/dev/null 2>&1; then
    echo "refusing to replace existing container: $container" >&2
    exit 1
  fi
done
cleanup() {
  docker rm -f "$application_container" "$platform_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

repository=$(git rev-parse --show-toplevel)
docker run -d --name "$application_container" \
  -e POSTGRES_PASSWORD=application-test -e POSTGRES_USER=ptw_commander -e POSTGRES_DB=ptw_commander \
  -v "$repository/db/migrations:/migrations:ro" postgres:16-alpine >/dev/null
docker run -d --name "$platform_container" \
  -e POSTGRES_PASSWORD=platform-test -e POSTGRES_USER=platform -e POSTGRES_DB=platform \
  postgres:16-alpine >/dev/null

for container in "$application_container" "$platform_container"; do
  attempts=0
  until docker exec "$container" pg_isready >/dev/null 2>&1; do
    attempts=$((attempts + 1)); [ "$attempts" -lt 60 ] || { echo "$container did not become ready" >&2; exit 1; }
    sleep 1
  done
done

docker exec "$platform_container" psql -X -v ON_ERROR_STOP=1 -U platform -d platform \
  -c 'CREATE TABLE permanent_platform_data(id integer PRIMARY KEY); INSERT INTO permanent_platform_data VALUES (1),(2),(3);' >/dev/null
platform_before=$(docker exec "$platform_container" psql -X -qAt -U platform -d platform -c 'SELECT count(*) FROM permanent_platform_data')

apply_and_check() {
  docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
    -f /migrations/001_ptw_marketing_v1.sql >/dev/null
  tables=$(docker exec "$application_container" psql -X -qAt -U ptw_commander -d ptw_commander \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
  [ "$tables" = 26 ] || { echo "expected 26 clean v1 tables, got $tables" >&2; exit 1; }
  docker exec -i "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM positioning_projects) <> 0
     OR (SELECT count(*) FROM positioning_revisions) <> 0
     OR (SELECT count(*) FROM landing_draft_sets) <> 0
     OR (SELECT count(*) FROM landing_builds) <> 0
     OR (SELECT count(*) FROM landing_leads) <> 0
     OR (SELECT count(*) FROM commander_entities) <> 0 THEN
    RAISE EXCEPTION 'clean v1 baseline contains seeded domain data';
  END IF;
  IF to_regclass('public.ideas') IS NOT NULL
     OR to_regclass('public.laval_runs') IS NOT NULL
     OR to_regclass('public.brand_runs') IS NOT NULL
     OR to_regclass('public.commander_ad_batches') IS NOT NULL THEN
    RAISE EXCEPTION 'retired domain table exists';
  END IF;
END $$;
SQL
}

apply_and_check
docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;' >/dev/null
apply_and_check

platform_after=$(docker exec "$platform_container" psql -X -qAt -U platform -d platform -c 'SELECT count(*) FROM permanent_platform_data')
[ "$platform_before" = 3 ] && [ "$platform_after" = "$platform_before" ] || {
  echo "independent platform database changed during application schema reset test" >&2
  exit 1
}
echo "PTW v2 PostgreSQL 16 baseline/reset verified; platform row count unchanged ($platform_after)"
