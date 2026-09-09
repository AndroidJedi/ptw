#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 4 || $1 != --confirm || $3 != --release-tag ]]; then
    echo "usage: $0 --confirm 'DEPLOY PTW IN PLACE' --release-tag TAG" >&2
    exit 2
fi
confirmation=$2
release_tag=$4
[[ $confirmation == "DEPLOY PTW IN PLACE" ]] || { echo "exact in-place deployment confirmation is required" >&2; exit 2; }
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || { echo "a versioned release tag is required" >&2; exit 2; }
[[ $(id -u) -eq 0 ]] || { echo "in-place deployment must run as root" >&2; exit 1; }
[[ ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 && -e /proc/self/fd/9 ]] || { echo "in-place deployment requires the inherited maintenance lock" >&2; exit 73; }

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
validation_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")

for image in ptw-commander ptw-validation ptw-owner-gateway; do
    docker image inspect "$image:$release_tag" >/dev/null || { echo "missing matching image $image:$release_tag" >&2; exit 1; }
done

"${commander_compose[@]}" up -d --no-deps --wait commander-db >/dev/null
commander_api_container=$("${commander_compose[@]}" ps -q commander-api)
validation_api_container=$("${validation_compose[@]}" ps -q validation-api)
owner_gateway_container=$("${commander_compose[@]}" ps -q owner-gateway)
[[ -n $commander_api_container && -n $validation_api_container && -n $owner_gateway_container ]] || {
    echo "all three current PTW application containers must exist before an in-place deployment" >&2; exit 1;
}
old_commander_image=$(docker inspect "$commander_api_container" --format '{{.Config.Image}}')
old_validation_image=$(docker inspect "$validation_api_container" --format '{{.Config.Image}}')
old_gateway_image=$(docker inspect "$owner_gateway_container" --format '{{.Config.Image}}')
case "$old_commander_image" in ptw-commander:*) old_tag=${old_commander_image#ptw-commander:} ;; *) echo "unexpected Commander image" >&2; exit 1 ;; esac
[[ $old_tag != latest && $old_validation_image == "ptw-validation:$old_tag" && $old_gateway_image == "ptw-owner-gateway:$old_tag" ]] || {
    echo "deployed PTW application images are not one matching versioned release" >&2; exit 1;
}

before_snapshot=$(mktemp /run/ptw-in-place-before.XXXXXX)
after_snapshot=$(mktemp /run/ptw-in-place-after.XXXXXX)
baseline_schema=$(mktemp /run/ptw-in-place-schema.XXXXXX)
rollback_needed=1
snapshot_ready=0

rollback() {
    set +e
    local rollback_failed=0
    export PTW_IMAGE_TAG=$old_tag
    "${commander_compose[@]}" up -d --no-deps --no-build --wait commander-api >/dev/null 2>&1 || rollback_failed=1
    "${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api >/dev/null 2>&1 || rollback_failed=1
    "${commander_compose[@]}" up -d --no-deps --no-build --wait owner-gateway >/dev/null 2>&1 || rollback_failed=1
    [[ $(docker inspect "$("${commander_compose[@]}" ps -q commander-api)" --format '{{.Config.Image}}') == "ptw-commander:$old_tag" ]] || rollback_failed=1
    [[ $(docker inspect "$("${validation_compose[@]}" ps -q validation-api)" --format '{{.Config.Image}}') == "ptw-validation:$old_tag" ]] || rollback_failed=1
    [[ $(docker inspect "$("${commander_compose[@]}" ps -q owner-gateway)" --format '{{.Config.Image}}') == "ptw-owner-gateway:$old_tag" ]] || rollback_failed=1
    if [[ $rollback_failed -ne 0 ]]; then
        echo "CRITICAL: in-place deployment could not verify complete application rollback" >&2
    else
        echo "in-place deployment failed; prior PTW images were restored and the additive migration was not reversed" >&2
    fi
    return "$rollback_failed"
}

cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    if [[ $rollback_needed -eq 1 ]]; then
        if [[ $snapshot_ready -eq 1 ]]; then
            if snapshot_database > "$after_snapshot"; then
                if cmp -s "$before_snapshot" "$after_snapshot"; then
                    echo "Commander authority remained unchanged during rejected in-place deployment" >&2
                else
                    echo "CRITICAL: Commander authority changed during rejected in-place deployment" >&2
                    diff -u "$before_snapshot" "$after_snapshot" >&2 || true
                    status=1
                fi
            else
                echo "CRITICAL: unable to verify Commander authority after rejected in-place deployment" >&2
                status=1
            fi
        fi
        rollback || status=1
        [[ $status -ne 0 ]] || status=1
    fi
    rm -f -- "$before_snapshot" "$after_snapshot" "$baseline_schema"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

snapshot_database() {
    # Capture all pre-existing business tables and columns once. Additive columns
    # do not alter old rows; every previously present column remains protected.
    if [[ ! -s $baseline_schema ]]; then
        "${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander > "$baseline_schema" <<'SQL'
SELECT jsonb_object_agg(table_name,columns) FROM (
 SELECT table_name,jsonb_agg(column_name ORDER BY ordinal_position) AS columns
 FROM information_schema.columns
 WHERE table_schema='public' AND table_name <> 'commander_schema_migrations'
 GROUP BY table_name
) schema;
SQL
    fi
    "${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
        -v baseline_schema="$(cat "$baseline_schema")" -U ptw_commander -d ptw_commander <<'SQL'
CREATE TEMP TABLE ptw_baseline_schema AS SELECT :'baseline_schema'::jsonb AS document;
CREATE OR REPLACE FUNCTION pg_temp.ptw_business_fingerprints()
RETURNS TABLE(table_name text, row_count bigint, row_fingerprint numeric)
LANGUAGE plpgsql AS $$
DECLARE item record;
DECLARE projection text;
BEGIN
  FOR item IN SELECT key,value FROM ptw_baseline_schema,jsonb_each(document) ORDER BY key
  LOOP
    table_name := item.key;
    SELECT string_agg(quote_ident(column_name),',') INTO projection
      FROM jsonb_array_elements_text(item.value) AS fields(column_name);
    EXECUTE format(
      'SELECT count(*),coalesce(sum(hashtextextended(to_jsonb(value)::text,0)::numeric),0) FROM (SELECT %s FROM public.%I) value',
      projection,item.key
    ) INTO row_count,row_fingerprint;
    RETURN NEXT;
  END LOOP;
END $$;
SELECT table_name || '=' || row_count || ':' || row_fingerprint
FROM pg_temp.ptw_business_fingerprints() ORDER BY table_name;
SQL
}


"${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
    -U ptw_commander -d ptw_commander <<'SQL'
DO $$
DECLARE instagram_active boolean;
BEGIN
  IF to_regclass('public.instagram_publications') IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS(SELECT 1 FROM instagram_publications WHERE state->>''status'' NOT IN (''published'',''published_unresolved'',''uncertain'',''failed''))' INTO instagram_active;
    IF instagram_active THEN
      RAISE EXCEPTION 'an Instagram publication is active; deployment refused';
    END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM product_briefs WHERE status='generating')
     OR EXISTS (SELECT 1 FROM universal_studio_workspaces WHERE status IN ('queued','composing','generating_image'))
     OR EXISTS (
       SELECT 1 FROM studio_edit_checkpoints checkpoint
       WHERE NOT EXISTS (
         SELECT 1 FROM studio_learning_runs completed
         WHERE completed.checkpoint_id=checkpoint.entity_id
           AND completed.status='completed'
       )
     )
     OR EXISTS (SELECT 1 FROM landing_workspaces WHERE status IN ('queued','composing','generating_images'))
     OR EXISTS (SELECT 1 FROM landing_checkpoints WHERE status='learning')
     OR EXISTS (SELECT 1 FROM meta_ads_deployments WHERE status NOT IN ('staged','failed')) THEN
    RAISE EXCEPTION 'a mutable PTW operation is active; in-place deployment refused';
  END IF;
END $$;
SQL

# Stop every Commander-database writer before taking the backup and snapshot.
"${commander_compose[@]}" stop owner-gateway commander-api >/dev/null
"${validation_compose[@]}" stop validation-api >/dev/null

backup_directory=/opt/ptw/backups/commander
install -d -m 0700 -o root -g root "$backup_directory"
backup_stamp=$(date --utc '+%Y%m%dT%H%M%SZ')
backup_file="$backup_directory/${backup_stamp}-pre-${release_tag}.dump"
docker exec "$("${commander_compose[@]}" ps -q commander-db)" \
    pg_dump -Fc -U ptw_commander -d ptw_commander > "$backup_file"
[[ -s $backup_file ]] || { echo "Commander PostgreSQL backup is empty" >&2; false; }
chmod 0600 "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
chmod 0600 "$backup_file.sha256"

snapshot_database > "$before_snapshot"
snapshot_ready=1
export PTW_IMAGE_TAG=$release_tag
"${commander_compose[@]}" run -T --rm --no-deps commander-migrate

"${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
  IF (SELECT count(*) FROM commander_schema_migrations) <> 5
     OR NOT EXISTS (SELECT 1 FROM commander_schema_migrations WHERE name='004_public_landing_v1.sql')
     OR NOT EXISTS (SELECT 1 FROM commander_schema_migrations WHERE name='005_instagram_publication_v1.sql')
     OR to_regclass('public.instagram_publications') IS NULL
     OR to_regclass('public.instagram_publication_attempts') IS NULL
     OR NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='landing_publications')
     OR NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='landing_publication_events')
     OR (SELECT is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='validation_projects' AND column_name='owner_idea_source_id') <> 'YES' THEN
    RAISE EXCEPTION 'Landing and Instagram publication migrations are incomplete';
  END IF;
END $$;
SQL

snapshot_database > "$after_snapshot"
cmp -s "$before_snapshot" "$after_snapshot" || {
    echo "pre-existing Commander business rows changed during additive migration" >&2
    diff -u "$before_snapshot" "$after_snapshot" >&2 || true
    false
}

# Cut over one service at a time only after the preservation proof succeeds.
"${commander_compose[@]}" up -d --no-deps --no-build --wait commander-api >/dev/null
curl --fail --silent --max-time 3 http://127.0.0.1:8091/readyz >/dev/null
"${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api >/dev/null
curl --fail --silent --max-time 3 http://127.0.0.1:8093/readyz >/dev/null
"${commander_compose[@]}" up -d --no-deps --no-build --wait --force-recreate owner-gateway >/dev/null
curl --fail --silent --max-time 3 http://127.0.0.1:8092/healthz >/dev/null

"${validation_compose[@]}" exec -T validation-api python -m validation_pipeline.verify_approved_post_access

rollback_needed=0
echo "in-place migration and serial service cutover preserved every pre-existing Commander business row; root-only backup: $backup_file"
