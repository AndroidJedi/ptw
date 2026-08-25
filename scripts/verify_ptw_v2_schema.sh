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
  [ "$tables" = 31 ] || { echo "expected 31 clean validation tables, got $tables" >&2; exit 1; }
  docker exec -i "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM validation_projects) <> 0
     OR (SELECT count(*) FROM product_briefs) <> 0
     OR (SELECT count(*) FROM creative_batches) <> 0
     OR (SELECT count(*) FROM ad_creatives) <> 0
     OR (SELECT count(*) FROM ad_studio_recipes) <> 0
     OR (SELECT count(*) FROM ad_studio_templates) <> 0
     OR (SELECT count(*) FROM ad_studio_renders) <> 0
     OR (SELECT count(*) FROM ad_studio_sample_sets) <> 0
     OR (SELECT count(*) FROM ad_studio_wizard_proposals) <> 0
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
  IF (SELECT count(*) FROM information_schema.columns
       WHERE table_schema='public' AND table_name='product_briefs'
         AND column_name='project_id') <> 1 THEN
    RAISE EXCEPTION 'Product Brief project membership is unavailable';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
       WHERE conname='commander_entities_kind_check'
         AND pg_get_constraintdef(oid) LIKE '%validation_project%'
  ) THEN
    RAISE EXCEPTION 'Validation Project graph entity kind is unavailable';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
       WHERE conname='commander_relationships_relation_check'
         AND pg_get_constraintdef(oid) LIKE '%rerun_of%'
  ) THEN
    RAISE EXCEPTION 'rerun_of relationship lineage is unavailable';
  END IF;
  IF (SELECT count(*) FROM information_schema.tables
       WHERE table_schema='public' AND table_name LIKE 'ad_studio_%') <> 11 THEN
    RAISE EXCEPTION 'Ad Studio persistence tables are incomplete';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
       WHERE conname='commander_entities_kind_check'
         AND pg_get_constraintdef(oid) LIKE '%studio_recipe%'
         AND pg_get_constraintdef(oid) LIKE '%studio_render%'
  ) THEN
    RAISE EXCEPTION 'Ad Studio graph entity kinds are unavailable';
  END IF;
END $$;
SQL
}

apply_and_check
docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;' >/dev/null

for migration in 001_ptw_validation_v1.sql 002_lesson_driven_creative_reruns.sql; do
  docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
    -f "/migrations/$migration" >/dev/null
done
docker exec -i "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
INSERT INTO commander_entities(id,kind) VALUES
  ('10000000-0000-4000-8000-000000000001','source'),
  ('10000000-0000-4000-8000-000000000002','product_brief'),
  ('10000000-0000-4000-8000-000000000003','product_brief'),
  ('20000000-0000-4000-8000-000000000001','source'),
  ('20000000-0000-4000-8000-000000000002','product_brief');
INSERT INTO commander_sources(
  entity_id,source_type,title,provider,external_id,content,content_sha256
) VALUES
  ('10000000-0000-4000-8000-000000000001','owner_idea','Owner idea','owner','upgrade-a','  First   raw idea  ',repeat('a',64)),
  ('20000000-0000-4000-8000-000000000001','owner_idea','Owner idea','owner','upgrade-b','Second raw idea',repeat('b',64));
INSERT INTO product_briefs(
  entity_id,request_id,owner_idea_source_id,base_brief_id,status,document,document_sha256,
  requested_by,created_at,updated_at,completed_at
) VALUES
  ('10000000-0000-4000-8000-000000000002','10000000-0000-4000-8000-000000000012','10000000-0000-4000-8000-000000000001',NULL,'completed','{"product":"First product"}',repeat('c',64),'upgrade-owner','2026-08-24 08:00:00+00','2026-08-24 08:01:00+00','2026-08-24 08:01:00+00'),
  ('10000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000013','10000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000002','completed','{"product":"Latest project A"}',repeat('d',64),'upgrade-owner','2026-08-24 08:02:00+00','2026-08-24 08:03:00+00','2026-08-24 08:03:00+00'),
  ('20000000-0000-4000-8000-000000000002','20000000-0000-4000-8000-000000000012','20000000-0000-4000-8000-000000000001',NULL,'queued',NULL,NULL,'upgrade-owner','2026-08-24 09:00:00+00','2026-08-24 09:00:00+00',NULL);
SQL
briefs_before=$(docker exec "$application_container" psql -X -qAt -U ptw_commander -d ptw_commander \
  -c "SELECT md5(string_agg(to_jsonb(brief)::text,'' ORDER BY entity_id)) FROM product_briefs brief")
docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -f '/migrations/003_validation_projects.sql' >/dev/null
briefs_after=$(docker exec "$application_container" psql -X -qAt -U ptw_commander -d ptw_commander \
  -c "SELECT md5(string_agg((to_jsonb(brief)-'project_id')::text,'' ORDER BY entity_id)) FROM product_briefs brief")
[ "$briefs_before" = "$briefs_after" ] || { echo "Product Brief fingerprints changed during Project backfill" >&2; exit 1; }
docker exec -i "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
DECLARE project_a uuid; project_a_revision uuid; project_b uuid;
BEGIN
  SELECT project_id INTO project_a FROM product_briefs WHERE entity_id='10000000-0000-4000-8000-000000000002';
  SELECT project_id INTO project_a_revision FROM product_briefs WHERE entity_id='10000000-0000-4000-8000-000000000003';
  SELECT project_id INTO project_b FROM product_briefs WHERE entity_id='20000000-0000-4000-8000-000000000002';
  IF (SELECT count(*) FROM validation_projects) <> 2
     OR (SELECT count(*) FROM product_briefs) <> 3
     OR project_a IS DISTINCT FROM project_a_revision
     OR project_a=project_b THEN
    RAISE EXCEPTION 'populated Project lineage backfill is incorrect';
  END IF;
  IF (SELECT name FROM validation_projects WHERE entity_id=project_a) <> 'Latest project A'
     OR (SELECT name FROM validation_projects WHERE entity_id=project_b) <> 'Second raw idea' THEN
    RAISE EXCEPTION 'populated Project name backfill is incorrect';
  END IF;
  IF (SELECT count(*) FROM commander_relationships WHERE relation='contains') <> 3 THEN
    RAISE EXCEPTION 'populated Project containment backfill is incomplete';
  END IF;
END $$;
SQL
echo "Populated Validation Project migration verified; existing Brief fingerprints unchanged"

docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -f '/migrations/004_ad_studio.sql' >/dev/null
briefs_after_studio=$(docker exec "$application_container" psql -X -qAt -U ptw_commander -d ptw_commander \
  -c "SELECT md5(string_agg((to_jsonb(brief)-'project_id')::text,'' ORDER BY entity_id)) FROM product_briefs brief")
[ "$briefs_after_studio" = "$briefs_after" ] || { echo "Product Brief fingerprints changed during Studio upgrade" >&2; exit 1; }
docker exec "$application_container" psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM information_schema.tables
       WHERE table_schema='public' AND table_name LIKE 'ad_studio_%') <> 11 THEN
    RAISE EXCEPTION 'populated Studio upgrade is incomplete';
  END IF;
END $$;
SQL
echo "Populated 001/002 through Project and Studio migrations verified"

docker exec "$application_container" psql -X -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION ptw_commander;' >/dev/null
apply_and_check

platform_after=$(docker exec "$platform_container" psql -X -qAt -U platform -d platform -c 'SELECT count(*) FROM permanent_platform_data')
[ "$platform_before" = 3 ] && [ "$platform_after" = "$platform_before" ] || {
  echo "independent platform database changed during application schema reset test" >&2
  exit 1
}
echo "PTW Validation PostgreSQL 16 baseline/reset verified; platform row count unchanged ($platform_after)"
