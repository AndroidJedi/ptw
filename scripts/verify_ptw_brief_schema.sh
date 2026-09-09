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
docker exec "$database_container" psql -X -qAt -v ON_ERROR_STOP=1 \
  -U ptw_brief_test -d ptw_brief_test <<'SQL'
INSERT INTO commander_entities(id,kind) VALUES
  ('11111111-1111-4111-8111-111111111111','source'),
  ('22222222-2222-4222-8222-222222222222','validation_project');
INSERT INTO commander_sources(entity_id,source_type,title,provider,external_id,content,content_sha256)
VALUES('11111111-1111-4111-8111-111111111111','owner_idea','Owner idea','owner','existing','Existing Natal Service idea',repeat('a',64));
INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by)
VALUES('22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111','Natal Service','owner','migration-test');
SQL
preserved_before=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT md5(to_jsonb(project)::text) FROM validation_projects project WHERE entity_id='22222222-2222-4222-8222-222222222222'")
apply_migrations
apply_migrations
preserved_after=$(docker exec "$database_container" psql -X -qAt -U ptw_brief_test -d ptw_brief_test -c \
  "SELECT md5(to_jsonb(project)::text) FROM validation_projects project WHERE entity_id='22222222-2222-4222-8222-222222222222'")
[ "$preserved_before" = "$preserved_after" ] || { echo "migration 004 changed the existing Natal Service Project" >&2; exit 1; }

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
instagram_publication_attempts
instagram_publications
landing_assets
landing_checkpoints
landing_generation_runs
landing_learning_proposals
landing_publication_events
landing_publications
landing_skill_snapshots
landing_versions
landing_workspace_files
landing_workspaces
meta_ads_audience_versions
meta_ads_deployments
meta_ads_preset_versions
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
studio_skill_snapshots
universal_studio_assets
universal_studio_versions
universal_studio_workspace_files
universal_studio_workspaces
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
  IF (SELECT count(*) FROM commander_schema_migrations) <> 5
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
     ) THEN
    RAISE EXCEPTION 'the database must contain the Product Brief, Studio, Landing, and Meta Ads migrations';
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
END $$;

INSERT INTO commander_entities(id,kind) VALUES
  ('44444444-4444-4444-8444-444444444444','validation_project');
INSERT INTO validation_projects(entity_id,request_id,owner_idea_source_id,name,name_source,requested_by)
VALUES('44444444-4444-4444-8444-444444444444','55555555-5555-4555-8555-555555555555',NULL,'Empty Project','owner','migration-test');
DO $$
BEGIN
  IF (SELECT owner_idea_source_id FROM validation_projects WHERE entity_id='44444444-4444-4444-8444-444444444444') IS NOT NULL THEN
    RAISE EXCEPTION 'empty Project did not remain empty';
  END IF;
END $$;
SQL

echo "Verified Product Brief, project-scoped Studio, immutable public Landing publication, and PAUSED Meta Ads migrations and idempotent journey."
