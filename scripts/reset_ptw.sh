#!/bin/sh
set -eu

confirmation=""
release_tag=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --confirm) confirmation=${2:-}; shift 2 ;;
    --release-tag) release_tag=${2:-}; shift 2 ;;
    *) echo "usage: $0 --confirm 'RESET PTW PRODUCTION' --release-tag TAG" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "reset must run as root" >&2; exit 1; }
[ "$confirmation" = "RESET PTW PRODUCTION" ] || { echo "exact confirmation is required" >&2; exit 2; }
case "$release_tag" in
  ""|latest|*[!A-Za-z0-9._-]*) echo "a versioned --release-tag is required" >&2; exit 2 ;;
esac

if [ "${PTW_MAINTENANCE_LOCK_HELD:-0}" != "1" ]; then
  exec 9>/run/lock/ptw-maintenance.lock
  flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }
fi

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose="docker compose --env-file $platform/.env --env-file $repository/.env.commander --env-file $repository/.env.owner-gateway --project-directory $repository -f $repository/docker-compose.commander.yml"
validation_compose="docker compose --env-file $platform/.env --env-file $repository/.env.commander --env-file $repository/.env.owner-gateway --project-name ptw-validation --project-directory $repository -f $repository/docker-compose.validation.yml"
platform_compose="docker compose --env-file $platform/.env --project-directory $platform -f $platform/docker-compose.yml"

for image in ptw-commander ptw-validation ptw-owner-gateway; do
  docker image inspect "$image:$release_tag" >/dev/null || {
    echo "missing matching image $image:$release_tag" >&2
    exit 1
  }
done
export PTW_IMAGE_TAG=$release_tag

platform_before=$(mktemp /run/ptw-platform-before.XXXXXX)
platform_after=$(mktemp /run/ptw-platform-after.XXXXXX)
trap 'rm -f -- "$platform_before" "$platform_after"' EXIT
snapshot_platform() {
  $platform_compose exec -T postgres sh -c \
    'psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE OR REPLACE FUNCTION pg_temp.ptw_table_counts()
RETURNS TABLE(table_name text, row_count bigint)
LANGUAGE plpgsql AS $$
DECLARE item record;
BEGIN
  FOR item IN
    SELECT schemaname, tablename FROM pg_tables
    WHERE schemaname NOT IN ('pg_catalog','information_schema')
    ORDER BY schemaname, tablename
  LOOP
    table_name := item.schemaname || '.' || item.tablename;
    EXECUTE format('SELECT count(*) FROM %I.%I', item.schemaname, item.tablename) INTO row_count;
    RETURN NEXT;
  END LOOP;
END $$;
SELECT table_name || '=' || row_count FROM pg_temp.ptw_table_counts() ORDER BY table_name;
SQL
}
snapshot_platform > "$platform_before"

# Commander owns only its database. The independent platform database is
# snapshotted and must remain byte-for-byte count-equivalent across this reset.
$commander_compose stop owner-gateway commander-api >/dev/null 2>&1 || true
$validation_compose stop validation-api >/dev/null 2>&1 || true
$commander_compose up -d --no-deps --wait commander-db >/dev/null
$commander_compose exec -T commander-db psql -X -v ON_ERROR_STOP=1 \
  -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;'

# This volume belonged to the deleted SQLite/job/Landing gateway. It has no
# owner in Result v1 and is removed in full after the gateway is stopped.
if docker volume inspect ptw_owner-control >/dev/null 2>&1; then
  docker volume rm ptw_owner-control >/dev/null
fi

$commander_compose run --rm --no-deps commander-migrate
$commander_compose up -d --no-deps --wait --no-build commander-api >/dev/null
$validation_compose up -d --no-deps --wait --no-build validation-api >/dev/null
$commander_compose up -d --no-deps --wait --no-build --force-recreate owner-gateway >/dev/null

$commander_compose exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
  -U ptw_commander -d ptw_commander <<'SQL'
DO $$
DECLARE failures text;
DECLARE forbidden text;
BEGIN
  SELECT string_agg(label || '=' || value, ', ') INTO failures
  FROM (VALUES
    ('entities', (SELECT count(*) FROM commander_entities)),
    ('relationships', (SELECT count(*) FROM commander_relationships)),
    ('sources', (SELECT count(*) FROM commander_sources)),
    ('projects', (SELECT count(*) FROM validation_projects)),
    ('briefs', (SELECT count(*) FROM product_briefs)),
    ('assets', (SELECT count(*) FROM project_assets)),
    ('brand_kits', (SELECT count(*) FROM project_brand_kits)),
    ('recipes', (SELECT count(*) FROM studio_recipes)),
    ('renders', (SELECT count(*) FROM studio_renders)),
    ('runs', (SELECT count(*) FROM content_generation_runs)),
    ('candidates', (SELECT count(*) FROM content_candidates)),
    ('elements', (SELECT count(*) FROM content_elements)),
    ('critic_passes', (SELECT count(*) FROM content_critic_passes)),
    ('actions', (SELECT count(*) FROM content_improvement_actions)),
    ('results', (SELECT count(*) FROM content_results)),
    ('outcomes', (SELECT count(*) FROM content_generation_outcomes)),
    ('feedback', (SELECT count(*) FROM commander_human_feedback)),
    ('weights', (SELECT count(*) FROM commander_weight_updates)),
    ('attempts', (SELECT count(*) FROM validation_generation_attempts)),
    ('provider_invocations', (SELECT count(*) FROM validation_provider_invocations))
  ) AS counts(label,value) WHERE value <> 0;
  IF failures IS NOT NULL THEN
    RAISE EXCEPTION 'Result v1 reset postcondition failed: %', failures;
  END IF;

  SELECT string_agg(table_name, ', ' ORDER BY table_name) INTO forbidden
  FROM information_schema.tables
  WHERE table_schema='public' AND (
    table_name IN ('ideas','research_jobs','research_sources')
    OR
    table_name LIKE 'ad\_%' ESCAPE '\'
    OR table_name LIKE 'landing\_%' ESCAPE '\'
    OR table_name LIKE 'positioning\_%' ESCAPE '\'
    OR table_name LIKE 'idea\_%' ESCAPE '\'
    OR table_name LIKE 'laval\_%' ESCAPE '\'
    OR table_name LIKE 'brand\_run%' ESCAPE '\'
    OR table_name LIKE '%batch%'
    OR table_name LIKE '%publication%'
    OR table_name LIKE '%campaign%'
  );
  IF forbidden IS NOT NULL THEN
    RAISE EXCEPTION 'retired tables survived Result v1 reset: %', forbidden;
  END IF;
  IF (SELECT count(*) FROM commander_schema_migrations) <> 1
     OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='001_ptw_result_v1.sql'
     ) THEN
    RAISE EXCEPTION 'Result v1 has anything other than its single baseline migration';
  END IF;
END $$;
SQL

curl --fail --max-time 3 --silent http://127.0.0.1:8091/readyz >/dev/null
curl --fail --max-time 3 --silent http://127.0.0.1:8093/readyz >/dev/null
curl --fail --max-time 3 --silent http://127.0.0.1:8092/healthz >/dev/null

snapshot_platform > "$platform_after"
cmp -s "$platform_before" "$platform_after" || {
  echo "independent platform database counts changed during Commander reset" >&2
  diff -u "$platform_before" "$platform_after" >&2 || true
  exit 1
}

for retired_container in \
  ptw-marketing-positioning-marketing-positioning-api-1 \
  ptw-idea-generation-idea-generation-api-1 \
  ptw-ad-studio-local-relay \
  ptw-ad-studio-local-validation \
  ptw-ad-studio-local-db \
  ptw-agent-platform-git-watcher-1 \
  ptw-agent-platform-git-credential-agent-1
do
  container_id=$(docker ps -aq --filter "name=^/$retired_container$")
  [ -z "$container_id" ] || docker rm --force "$container_id" >/dev/null
done

echo "PTW Result v1 reset complete; all owned business data is empty and platform counts are unchanged"
