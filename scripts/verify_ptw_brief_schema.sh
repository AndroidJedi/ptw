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
until docker exec -e PGPASSWORD=ptw-brief-test-only "$database_container" \
  psql -h 127.0.0.1 -U ptw_brief_test -d ptw_brief_test -qAtc 'SELECT 1' >/dev/null 2>&1; do
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

apply_pre_public_migrations() {
  docker exec "$database_container" sh -eu -c '
    args="-X -v ON_ERROR_STOP=1 -U ptw_brief_test -d ptw_brief_test"
    psql $args -c "CREATE TABLE IF NOT EXISTS commander_schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT clock_timestamp())" >/dev/null
    for migration in /migrations/*.sql; do
      name=$(basename "$migration")
      case "$name" in 001_*|002_*|003_*) ;; *) continue ;; esac
      applied=$(psql $args -qAtc "SELECT count(*) FROM commander_schema_migrations WHERE name='"'"'$name'"'"'")
      if [ "$applied" = 0 ]; then
        psql $args -f "$migration" >/dev/null
        psql $args -c "INSERT INTO commander_schema_migrations(name) VALUES ('"'"'$name'"'"')" >/dev/null
      fi
    done
  '
}

apply_pre_public_migrations
docker exec -i "$database_container" psql -X -qAt -v ON_ERROR_STOP=1 \
  -U ptw_brief_test -d ptw_brief_test <<'SQL'
INSERT INTO commander_entities(id,kind) VALUES
  ('11111111-1111-4111-8111-111111111111','source'),
  ('22222222-2222-4222-8222-222222222222','validation_project'),
  ('33333333-3333-4333-8333-333333333331','product_brief'),
  ('33333333-3333-4333-8333-333333333332','studio_workspace');
INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256)
VALUES('11111111-1111-4111-8111-111111111111','owner_idea','Owner idea','owner','existing','Existing Natal Service idea',repeat('a',64));
INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by)
VALUES('22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111','Natal Service','owner','migration-test');
INSERT INTO product_briefs(entity_id,project_id,request_id,owner_idea_source_id,status,requested_by)
VALUES('33333333-3333-4333-8333-333333333331','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333334','11111111-1111-4111-8111-111111111111','completed','migration-test');
INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by)
VALUES('33333333-3333-4333-8333-333333333332','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333331',1,'brief_generation','universal'||'_'||'ad','draft','migration-test');
SQL
preserved_before=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT md5(jsonb_build_array(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by,created_at,updated_at)::text) FROM validation_projects WHERE entity_id='22222222-2222-4222-8222-222222222222'")
apply_migrations
apply_migrations
preserved_after=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT md5(jsonb_build_array(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by,created_at,updated_at)::text) FROM validation_projects WHERE entity_id='22222222-2222-4222-8222-222222222222'")
[ "$preserved_before" = "$preserved_after" ] || { echo "an additive migration changed existing Project values" >&2; exit 1; }
retired_preserved=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT count(*) FROM universal_studio_workspaces WHERE entity_id='33333333-3333-4333-8333-333333333332'")
[ "$retired_preserved" = 1 ] || { echo "active-template constraint rewrote a historical Post row" >&2; exit 1; }
if docker exec "$database_container" psql -X -qAt -v ON_ERROR_STOP=1 \
  -U ptw_brief_test -d ptw_brief_test -c \
  "BEGIN; INSERT INTO commander_entities(id,kind) VALUES('33333333-3333-4333-8333-333333333335','studio_workspace'); INSERT INTO universal_studio_workspaces(entity_id,project_id,source_brief_id,ordinal,origin,template_id,status,requested_by) VALUES('33333333-3333-4333-8333-333333333335','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333331',2,'brief_generation','retired_probe','draft','migration-test'); COMMIT;" >/dev/null 2>&1; then
  echo "active-template constraint accepted a new unsupported Post workspace" >&2
  exit 1
fi

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
creative_attribution_sources
creative_insight_snapshots
creative_learning_decisions
creative_learning_runs
creative_skill_snapshots
creative_visual_descriptors
creative_visual_descriptor_sources
instagram_manual_post_events
instagram_manual_post_packages
instagram_publication_attempts
instagram_publications
instagram_validation_arms
instagram_validation_import_rows
instagram_validation_imports
instagram_validation_test_events
instagram_validation_tests
tiktok_account_connections
tiktok_oauth_states
tiktok_publication_attempts
tiktok_publications
landing_assets
landing_checkpoints
landing_generation_runs
landing_analytics_events
landing_analytics_rollup_snapshots
landing_learning_proposals
landing_publication_events
landing_publications
landing_skill_snapshots
landing_versions
landing_workspace_files
landing_workspaces
meta_ads_audience_versions
meta_ads_control_actions
meta_ads_deployments
meta_ads_insight_snapshots
meta_ads_preset_versions
meta_ads_recommendations
meta_ads_stage_runs
meta_ads_status_snapshots
meta_ads_workspaces
product_brief_approvals
product_briefs
studio_edit_checkpoints
studio_generation_runs
studio_learning_decisions
studio_learning_proposals
studio_learning_runs
studio_project_logo_defaults
studio_skill_snapshots
template_authoring_media
template_authoring_records
universal_studio_assets
universal_studio_versions
universal_studio_workspace_files
universal_studio_workspaces
validation_generation_attempts
validation_projects
validation_provider_invocations
TABLES
)
for table in $expected; do
  printf '%s\n' "$actual" | grep -Fx "$table" >/dev/null || {
    echo "Required Product Brief table is missing: $table" >&2
    exit 1
  }
done

expected_migrations=$(find "$repository/db/migrations" -maxdepth 1 -name '*.sql' | wc -l | tr -d ' ')
docker exec -i "$database_container" psql -X -qAt -v ON_ERROR_STOP=1 -v expected_migrations="$expected_migrations" \
  -U ptw_brief_test -d ptw_brief_test <<'SQL'
CREATE TEMP TABLE expected_migration_inventory AS SELECT :expected_migrations AS count;
DO $$
BEGIN
  IF (SELECT count(*) FROM commander_schema_migrations) <> (SELECT count FROM expected_migration_inventory)
     OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='001_ptw_brief_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='002_ptw_landing_studio_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='003_ptw_meta_ads_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='004_public_landing_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='005_instagram_publication_v1.sql'
     ) OR NOT EXISTS (
     SELECT 1 FROM commander_schema_migrations WHERE name='006_meta_ads_control_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='007_tiktok_publication_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='008_analytics_creative_learning_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='009_instagram_manual_validation_v1.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='010_studio_project_logo_defaults.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='011_project_first_brief_source_guard.sql'
     ) OR NOT EXISTS (
       SELECT 1 FROM commander_schema_migrations WHERE name='012_phone_metrics_only.sql'
     ) THEN
    RAISE EXCEPTION 'the database must contain the Product Brief, Studio, Landing, Instagram validation, and Analytics migrations';
  END IF;
  IF (SELECT count(*) FROM commander_control) <> 1
     OR (SELECT count(*) FROM commander_operation_guard) <> 1 THEN
    RAISE EXCEPTION 'bounded global control rows are missing';
  END IF;
  IF (SELECT is_nullable FROM information_schema.columns
      WHERE table_schema='public' AND table_name='validation_projects'
        AND column_name='owner_idea_source_id') <> 'YES' THEN
    RAISE EXCEPTION 'empty Projects are not permitted after migration 004';
  END IF;
  IF (SELECT count(*) FROM information_schema.columns
      WHERE table_schema='public' AND table_name='validation_projects'
        AND column_name IN ('deleted_at','deleted_by','delete_request_id')) <> 3 THEN
    RAISE EXCEPTION 'Project deletion tombstone columns are incomplete';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='tiktok_connection_protected' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='tiktok_publications_protected' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='tiktok_attempts_immutable' AND NOT tgisinternal) THEN
    RAISE EXCEPTION 'TikTok immutable identity and attempt triggers are incomplete';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='creative_learning_runs_frozen' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='creative_learning_runs_no_delete' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='landing_analytics_events_retention_guard' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='creative_visual_descriptor_sources_immutable' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='creative_skill_snapshots_immutable' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='creative_learning_decisions_immutable' AND NOT tgisinternal) THEN
    RAISE EXCEPTION 'Analytics learning lineage triggers are incomplete';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='instagram_manual_packages_immutable' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='instagram_validation_tests_immutable' AND NOT tgisinternal)
     OR NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='instagram_validation_import_rows_immutable' AND NOT tgisinternal) THEN
    RAISE EXCEPTION 'Instagram manual validation immutable triggers are incomplete';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='studio_project_logo_defaults_immutable' AND NOT tgisinternal) THEN
    RAISE EXCEPTION 'Studio Project logo default lineage trigger is incomplete';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='post_studio_workspaces_template_id_check' AND NOT convalidated
  ) THEN
    RAISE EXCEPTION 'Post Studio active-template constraint is incomplete';
  END IF;
END $$;

INSERT INTO commander_entities(id,kind) VALUES
  ('44444444-4444-4444-8444-444444444444','validation_project');
INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by)
VALUES('44444444-4444-4444-8444-444444444444','55555555-5555-4555-8555-555555555555',NULL,'Empty Project','owner','migration-test');
INSERT INTO commander_entities(id,kind) VALUES
  ('66666666-6666-4666-8666-666666666666','source'),
  ('77777777-7777-4777-8777-777777777777','source');
INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256)
VALUES
  ('66666666-6666-4666-8666-666666666666','owner_idea','First idea','owner','first-source','First idea',repeat('b',64)),
  ('77777777-7777-4777-8777-777777777777','owner_idea','Replacement idea','owner','replacement-source','Replacement idea',repeat('c',64));
UPDATE validation_projects
SET owner_idea_source_id='66666666-6666-4666-8666-666666666666',updated_at=clock_timestamp()
WHERE entity_id='44444444-4444-4444-8444-444444444444';
DO $$
BEGIN
  IF (SELECT owner_idea_source_id FROM validation_projects WHERE entity_id='44444444-4444-4444-8444-444444444444')
       <> '66666666-6666-4666-8666-666666666666'::uuid THEN
    RAISE EXCEPTION 'empty Project did not accept its immutable first source';
  END IF;
  BEGIN
    UPDATE validation_projects
    SET owner_idea_source_id='77777777-7777-4777-8777-777777777777',updated_at=clock_timestamp()
    WHERE entity_id='44444444-4444-4444-8444-444444444444';
    RAISE EXCEPTION 'Validation Project accepted a source replacement';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'immutable Validation Project fields cannot change' THEN
      RAISE;
    END IF;
  END;
  UPDATE validation_projects
  SET deleted_at=clock_timestamp(),deleted_by='migration-test',
      delete_request_id='88888888-8888-4888-8888-888888888888',updated_at=clock_timestamp()
  WHERE entity_id='44444444-4444-4444-8444-444444444444';
  IF NOT EXISTS (
    SELECT 1 FROM validation_projects
    WHERE entity_id='44444444-4444-4444-8444-444444444444'
      AND deleted_at IS NOT NULL AND deleted_by='migration-test'
      AND delete_request_id='88888888-8888-4888-8888-888888888888'
  ) THEN
    RAISE EXCEPTION 'Project deletion tombstone was not persisted';
  END IF;
  BEGIN
    UPDATE validation_projects SET name='Restored Project'
    WHERE entity_id='44444444-4444-4444-8444-444444444444';
    RAISE EXCEPTION 'deleted Validation Project accepted a mutation';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'deleted Validation Project cannot change' THEN
      RAISE;
    END IF;
  END;
END $$;
SQL

echo "Verified Product Brief, Project deletion, Studio, public Landing, manual Instagram validation, preserved social history, and Analytics migrations."
