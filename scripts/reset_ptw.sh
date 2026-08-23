#!/bin/sh
set -eu

confirmation=""
release_tag=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --confirm) confirmation=${2:-}; shift 2 ;;
    --release-tag) release_tag=${2:-}; shift 2 ;;
    *) echo "usage: $0 --confirm 'RESET PTW PRODUCTION' [--release-tag TAG]" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "reset must run as root" >&2; exit 1; }
[ "$confirmation" = "RESET PTW PRODUCTION" ] || { echo "exact confirmation is required" >&2; exit 2; }

if [ "${PTW_MAINTENANCE_LOCK_HELD:-0}" != "1" ]; then
  exec 9>/run/lock/ptw-maintenance.lock
  flock -n 9 || { echo "another PTW maintenance operation is active" >&2; exit 73; }
fi

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose="docker compose --env-file $platform/.env --env-file $repository/.env.commander --env-file $repository/.env.owner-gateway --project-directory $repository -f $repository/docker-compose.commander.yml"
positioning_compose="docker compose --env-file $platform/.env --env-file $repository/.env.commander --env-file $repository/.env.owner-gateway --project-name ptw-marketing-positioning --project-directory $repository -f $repository/docker-compose.marketing-positioning.yml"
platform_compose="docker compose --env-file $platform/.env --project-directory $platform -f $platform/docker-compose.yml"

if [ -z "$release_tag" ]; then
  commander_container=$($commander_compose ps -q commander-api)
  owner_container=$($commander_compose ps -q owner-gateway)
  [ -n "$commander_container" ] && [ -n "$owner_container" ] || {
    echo "--release-tag is required during a first v2 cutover" >&2
    exit 1
  }
  commander_image=$(docker inspect --format '{{.Config.Image}}' "$commander_container")
  owner_image=$(docker inspect --format '{{.Config.Image}}' "$owner_container")
  case "$commander_image" in
    ptw-commander:*) release_tag=${commander_image#ptw-commander:} ;;
    *) echo "unexpected deployed Commander image: $commander_image" >&2; exit 1 ;;
  esac
  [ "$owner_image" = "ptw-owner-gateway:$release_tag" ] || {
    echo "Owner Gateway release does not match Commander" >&2
    exit 1
  }
fi
case "$release_tag" in
  ""|latest|*[!A-Za-z0-9._-]*) echo "refusing unversioned production reset image tag" >&2; exit 1 ;;
esac
for image in ptw-commander ptw-marketing-positioning ptw-owner-gateway; do
  docker image inspect "$image:$release_tag" >/dev/null || {
    echo "missing matching image $image:$release_tag" >&2
    exit 1
  }
done
export PTW_IMAGE_TAG=$release_tag

platform_snapshot_before=$(mktemp /run/ptw-platform-before.XXXXXX)
platform_snapshot_after=$(mktemp /run/ptw-platform-after.XXXXXX)
trap 'rm -f -- "$platform_snapshot_before" "$platform_snapshot_after"' EXIT
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
snapshot_platform > "$platform_snapshot_before"

# Stop only PTW v2 application processes. The independent platform bridge and
# its PostgreSQL database remain running and are never migrated by this reset.
$commander_compose stop owner-gateway >/dev/null 2>&1 || true
$commander_compose stop commander-api >/dev/null 2>&1 || true
$positioning_compose stop marketing-positioning-api >/dev/null 2>&1 || true
old_idea_container=$(docker ps -aq --filter 'name=^/ptw-idea-generation-idea-generation-api-1$')
[ -z "$old_idea_container" ] || docker stop "$old_idea_container" >/dev/null

$commander_compose exec -T commander-db psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;'

# Clear only generated Landing output; owner-control state, credentials,
# repositories, the database volume, and all platform paths remain intact.
docker run --rm -v ptw_owner-control:/data alpine:3.22 sh -c \
  'if [ -d /data/landings ]; then find /data/landings -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; fi'

$commander_compose run --rm --no-deps --no-build commander-migrate
$commander_compose up -d --no-deps --wait --no-build commander-api >/dev/null
$positioning_compose up -d --no-deps --wait --no-build marketing-positioning-api >/dev/null
$commander_compose up -d --no-deps --wait --no-build --force-recreate owner-gateway >/dev/null

$commander_compose exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
DECLARE failures text;
BEGIN
  SELECT string_agg(label || '=' || value, ', ') INTO failures
  FROM (VALUES
    ('positioning_projects', (SELECT count(*) FROM positioning_projects)),
    ('positioning_revisions', (SELECT count(*) FROM positioning_revisions)),
    ('landing_draft_sets', (SELECT count(*) FROM landing_draft_sets)),
    ('landing_builds', (SELECT count(*) FROM landing_builds)),
    ('landing_leads', (SELECT count(*) FROM landing_leads)),
    ('entities', (SELECT count(*) FROM commander_entities)),
    ('relationships', (SELECT count(*) FROM commander_relationships))
  ) AS counts(label,value) WHERE value <> 0;
  IF failures IS NOT NULL THEN RAISE EXCEPTION 'v2 reset postcondition failed: %', failures; END IF;
  IF to_regclass('public.ideas') IS NOT NULL
     OR to_regclass('public.laval_runs') IS NOT NULL
     OR to_regclass('public.brand_runs') IS NOT NULL
     OR to_regclass('public.commander_ad_batches') IS NOT NULL THEN
    RAISE EXCEPTION 'retired domain table survived v2 reset';
  END IF;
END $$;
SQL

curl --fail --max-time 3 --silent http://127.0.0.1:8091/readyz >/dev/null
curl --fail --max-time 3 --silent http://127.0.0.1:8093/readyz >/dev/null
curl --fail --max-time 3 --silent http://127.0.0.1:8092/healthz >/dev/null

snapshot_platform > "$platform_snapshot_after"
cmp -s "$platform_snapshot_before" "$platform_snapshot_after" || {
  echo "independent platform database counts changed during Commander reset" >&2
  diff -u "$platform_snapshot_before" "$platform_snapshot_after" >&2 || true
  exit 1
}

# Remove the retired domain container only after all v2 services are healthy.
[ -z "$old_idea_container" ] || docker rm "$old_idea_container" >/dev/null
echo "PTW v2 reset complete; application data is empty and platform counts are unchanged"
