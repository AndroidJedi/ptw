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
  for migration in "$repository"/db/migrations/*.sql; do
    docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
      -f "/migrations/$(basename "$migration")" >/dev/null
  done
  tables=$(docker exec "$application_container" psql -X -qAt -U ptw_commander -d ptw_commander \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
  [ "$tables" = 19 ] || { echo "expected 19 clean validation tables, got $tables" >&2; exit 1; }
  docker exec -i "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM product_briefs) <> 0
     OR (SELECT count(*) FROM creative_batches) <> 0
     OR (SELECT count(*) FROM ad_creatives) <> 0
     OR (SELECT count(*) FROM commander_entities) <> 0 THEN
    RAISE EXCEPTION 'clean v1 baseline contains seeded domain data';
  END IF;
  IF to_regclass('public.positioning_projects') IS NOT NULL
     OR to_regclass('public.positioning_revisions') IS NOT NULL
     OR to_regclass('public.landing_draft_sets') IS NOT NULL
     OR to_regclass('public.landing_builds') IS NOT NULL
     OR to_regclass('public.landing_leads') IS NOT NULL
     OR to_regclass('public.ideas') IS NOT NULL
     OR to_regclass('public.laval_runs') IS NOT NULL
     OR to_regclass('public.brand_runs') IS NOT NULL
     OR to_regclass('public.commander_ad_batches') IS NOT NULL THEN
    RAISE EXCEPTION 'retired domain table exists';
  END IF;
  IF (SELECT count(*) FROM information_schema.columns
       WHERE table_schema='public' AND table_name='creative_batches'
         AND column_name IN ('request_id','rerun_of_batch_id','requested_by','skill_sha256')) <> 4 THEN
    RAISE EXCEPTION 'learned-rerun creative batch columns are incomplete';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
       WHERE conname='commander_relationships_relation_check'
         AND pg_get_constraintdef(oid) LIKE '%rerun_of%'
  ) THEN
    RAISE EXCEPTION 'rerun_of relationship lineage is unavailable';
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
echo "PTW Validation PostgreSQL 16 baseline/reset verified; platform row count unchanged ($platform_after)"
