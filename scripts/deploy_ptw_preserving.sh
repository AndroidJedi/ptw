#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 RELEASE_TAG PTW_GIT_REVISION PLATFORM_GIT_REVISION" >&2
    exit 2
fi
release_tag=$1
git_revision=$2
platform_git_revision=$3
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || {
    echo "invalid or unversioned release tag" >&2; exit 2;
}
[[ $git_revision =~ ^[0-9a-f]{40}$ ]] || { echo "PTW_GIT_REVISION must be a full commit SHA" >&2; exit 2; }
[[ $platform_git_revision =~ ^[0-9a-f]{40}$ ]] || { echo "PLATFORM_GIT_REVISION must be a full commit SHA" >&2; exit 2; }
[[ $(id -u) -eq 0 ]] || { echo "production deployment must run as root" >&2; exit 1; }

if [[ ${PTW_MAINTENANCE_LOCK_HELD:-0} != 1 ]]; then
    exec 9>/run/lock/ptw-maintenance.lock
    flock -n 9 || { echo "another PTW maintenance session is active" >&2; exit 73; }
elif [[ ! -e /proc/self/fd/9 ]]; then
    echo "maintenance lock inheritance is invalid" >&2
    exit 73
fi

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
validation_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")
platform_compose=(docker compose --env-file "$platform/.env" --project-directory "$platform" -f "$platform/docker-compose.yml")

[[ -f "$platform/.env" && -f "$repository/.env.commander" && -f "$repository/.env.owner-gateway" ]] || {
    echo "required production environment file is missing" >&2; exit 1;
}
grep -q '^PTW_IMAGE_TAG=' "$repository/.env.commander" || { echo "PTW_IMAGE_TAG is missing" >&2; exit 1; }
grep -q '^PTW_PLATFORM_IMAGE_TAG=' "$platform/.env" || { echo "PTW_PLATFORM_IMAGE_TAG is missing" >&2; exit 1; }
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]] || {
    echo "production repository has tracked changes" >&2; exit 1;
}
[[ -z $(git -C "$platform" status --porcelain --untracked-files=no) ]] || {
    echo "platform repository has tracked changes" >&2; exit 1;
}
[[ $(git -C "$repository" rev-parse HEAD) == "$git_revision" ]] || {
    echo "production repository is not at the requested revision" >&2; exit 1;
}
[[ $(git -C "$platform" rev-parse HEAD) == "$platform_git_revision" ]] || {
    echo "platform repository is not at the requested revision" >&2; exit 1;
}

for migration in "$repository"/db/migrations/*.sql; do
    migration_name=$(basename "$migration")
    applied=$("${commander_compose[@]}" exec -T commander-db \
        psql -X -qAt -v ON_ERROR_STOP=1 -v migration_name="$migration_name" \
        -U ptw_commander -d ptw_commander <<'SQL'
SELECT count(*) FROM commander_schema_migrations WHERE name=:'migration_name';
SQL
    )
    [[ $applied == 1 ]] || {
        echo "pending migrations require the confirmation-gated in-place deployment path" >&2
        exit 1
    }
done

for image in ptw-commander ptw-validation ptw-owner-gateway \
    ptw-agent-platform-commander-api ptw-agent-platform-commander-worker \
    ptw-agent-platform-codex-auth; do
    [[ $(docker image inspect "$image:$release_tag" --format '{{.Architecture}}') == amd64 ]] || {
        echo "missing Linux/amd64 release image $image:$release_tag" >&2; exit 1;
    }
done

old_app_image=$(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}')
old_platform_image=$(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}')
case "$old_app_image" in ptw-validation:*) old_app_tag=${old_app_image#ptw-validation:} ;; *) exit 1 ;; esac
case "$old_platform_image" in ptw-agent-platform-commander-api:*) old_platform_tag=${old_platform_image#ptw-agent-platform-commander-api:} ;; *) exit 1 ;; esac
[[ $(docker inspect ptw-commander-api-1 --format '{{.Config.Image}}') == "ptw-commander:$old_app_tag" ]]
[[ $(docker inspect ptw-owner-gateway-1 --format '{{.Config.Image}}') == "ptw-owner-gateway:$old_app_tag" ]]
[[ $(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}') == "ptw-agent-platform-commander-worker:$old_platform_tag" ]]
[[ $(docker inspect ptw-agent-platform-codex-auth-1 --format '{{.Config.Image}}') == "ptw-agent-platform-codex-auth:$old_platform_tag" ]]

before=$(mktemp /run/ptw-preserve-before.XXXXXX)
after=$(mktemp /run/ptw-preserve-after.XXXXXX)
rollback_needed=1
snapshot_ready=0

rollback() {
    set +e
    local rollback_failed=0
    echo "preserving rollout failed; restoring prior image tags" >&2
    export PTW_PLATFORM_IMAGE_TAG=$old_platform_tag
    "${platform_compose[@]}" up -d --no-deps --no-build --wait codex-auth commander-worker commander-api || rollback_failed=1
    export PTW_IMAGE_TAG=$old_app_tag
    "${commander_compose[@]}" up -d --no-deps --no-build --wait commander-api owner-gateway || rollback_failed=1
    "${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api || rollback_failed=1
    sed -i "s/^PTW_PLATFORM_IMAGE_TAG=.*/PTW_PLATFORM_IMAGE_TAG=$old_platform_tag/" "$platform/.env" || rollback_failed=1
    sed -i "s/^PTW_IMAGE_TAG=.*/PTW_IMAGE_TAG=$old_app_tag/" "$repository/.env.commander" || rollback_failed=1
    [[ $(docker inspect ptw-commander-api-1 --format '{{.Config.Image}}') == "ptw-commander:$old_app_tag" ]] || rollback_failed=1
    [[ $(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}') == "ptw-validation:$old_app_tag" ]] || rollback_failed=1
    [[ $(docker inspect ptw-owner-gateway-1 --format '{{.Config.Image}}') == "ptw-owner-gateway:$old_app_tag" ]] || rollback_failed=1
    [[ $(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}') == "ptw-agent-platform-commander-api:$old_platform_tag" ]] || rollback_failed=1
    [[ $(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}') == "ptw-agent-platform-commander-worker:$old_platform_tag" ]] || rollback_failed=1
    [[ $(docker inspect ptw-agent-platform-codex-auth-1 --format '{{.Config.Image}}') == "ptw-agent-platform-codex-auth:$old_platform_tag" ]] || rollback_failed=1
    if [[ $rollback_failed -ne 0 ]]; then
        echo "CRITICAL: preserving rollout could not verify complete image rollback" >&2
    fi
    return "$rollback_failed"
}

cleanup() {
    status=$?
    trap - EXIT
    if [[ $rollback_needed -eq 1 ]]; then
        if [[ $snapshot_ready -eq 1 ]]; then
            if snapshot_authority > "$after"; then
                if cmp -s "$before" "$after"; then
                    echo "Commander authority remained unchanged during rejected rollout" >&2
                else
                    echo "CRITICAL: Commander authority changed during rejected rollout" >&2
                    diff -u "$before" "$after" >&2 || true
                    status=1
                fi
            else
                echo "CRITICAL: unable to verify Commander authority after rejected rollout" >&2
                status=1
            fi
        fi
        rollback || status=1
        [[ $status -ne 0 ]] || status=1
    fi
    rm -f -- "$before" "$after"
    exit "$status"
}
trap cleanup EXIT

"${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
    -U ptw_commander -d ptw_commander <<'SQL'
DO $$
BEGIN
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
    RAISE EXCEPTION 'a mutable PTW operation is active; preserving rollout refused';
  END IF;
END $$;
SQL

snapshot_authority() {
    "${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
        -U ptw_commander -d ptw_commander <<'SQL'
CREATE OR REPLACE FUNCTION pg_temp.ptw_authority_snapshot()
RETURNS TABLE(snapshot_line text)
LANGUAGE plpgsql AS $$
DECLARE item record;
DECLARE item_count bigint;
BEGIN
  FOR item IN
    SELECT schemaname,tablename FROM pg_tables
    WHERE schemaname='public' ORDER BY tablename
  LOOP
    EXECUTE format('SELECT count(*) FROM %I.%I',item.schemaname,item.tablename) INTO item_count;
    snapshot_line := 'count|' || item.tablename || '|' || item_count;
    RETURN NEXT;
    RETURN QUERY EXECUTE format(
      'SELECT %L || md5(row_to_json(t)::text) FROM %I.%I t ORDER BY 1',
      'row|' || item.tablename || '|',item.schemaname,item.tablename
    );
  END LOOP;
END $$;
SELECT snapshot_line FROM pg_temp.ptw_authority_snapshot();
SQL
}

snapshot_authority > "$before"
snapshot_ready=1
export PTW_PLATFORM_IMAGE_TAG=$release_tag
"${platform_compose[@]}" up -d --no-deps --no-build --wait codex-auth
"${platform_compose[@]}" up -d --no-deps --no-build --wait commander-worker
"${platform_compose[@]}" up -d --no-deps --no-build --wait commander-api

export PTW_IMAGE_TAG=$release_tag
"${commander_compose[@]}" run -T --rm --no-deps commander-migrate
"${commander_compose[@]}" up -d --no-deps --no-build --wait commander-api
"${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api
"${commander_compose[@]}" up -d --no-deps --no-build --wait owner-gateway

curl --fail --silent --max-time 5 http://127.0.0.1:8091/readyz >/dev/null
curl --fail --silent --max-time 5 http://127.0.0.1:8093/readyz >/dev/null
curl --fail --silent --max-time 5 http://127.0.0.1:8092/healthz >/dev/null
"${validation_compose[@]}" run -T --rm --no-deps validation-api \
    python -m validation_pipeline.verify_bridge_contract
"${validation_compose[@]}" run -T --rm --no-deps validation-api \
    python -m validation_pipeline.verify_pexels

snapshot_authority > "$after"
cmp -s "$before" "$after" || {
    echo "Commander authority changed during preserving rollout" >&2
    diff -u "$before" "$after" >&2 || true
    exit 1
}
"$repository/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh" </dev/null
PTW_MAINTENANCE_LOCK_HELD=1 "$repository/scripts/audit_ptw_1gb.sh" </dev/null

for service in ptw-commander-api-1 ptw-validation-validation-api-1 \
    ptw-owner-gateway-1 ptw-agent-platform-commander-api-1 \
    ptw-agent-platform-commander-worker-1 ptw-agent-platform-codex-auth-1; do
    [[ $(docker inspect "$service" --format '{{.State.Health.Status}}') == healthy ]]
done

sed -i "s/^PTW_PLATFORM_IMAGE_TAG=.*/PTW_PLATFORM_IMAGE_TAG=$release_tag/" "$platform/.env"
sed -i "s/^PTW_IMAGE_TAG=.*/PTW_IMAGE_TAG=$release_tag/" "$repository/.env.commander"
grep -qx "PTW_PLATFORM_IMAGE_TAG=$release_tag" "$platform/.env"
grep -qx "PTW_IMAGE_TAG=$release_tag" "$repository/.env.commander"
rollback_needed=0
echo "PTW preserving rollout complete at $git_revision"
