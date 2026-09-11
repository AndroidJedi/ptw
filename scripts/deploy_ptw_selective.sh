#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 RELEASE_TAG PTW_GIT_REVISION PLATFORM_GIT_REVISION" >&2
    exit 2
fi
release_tag=$1
git_revision=$2
platform_git_revision=$3
image_components=${PTW_RELEASE_IMAGE_COMPONENTS:-}
restart_components=${PTW_RELEASE_RESTART_COMPONENTS:-}
[[ $release_tag =~ ^[A-Za-z0-9._-]+$ && $release_tag != latest ]] || exit 2
[[ $git_revision =~ ^[0-9a-f]{40}$ && $platform_git_revision =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ $(id -u) -eq 0 ]] || { echo "selective deployment must run as root" >&2; exit 1; }
[[ ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 && -e /proc/self/fd/9 ]] || {
    echo "selective deployment requires the inherited maintenance lock" >&2; exit 73;
}

selected() { [[ ",$1," == *",$2,"* ]]; }
for list in "$image_components" "$restart_components"; do
    IFS=, read -ra requested <<< "$list"
    for component in "${requested[@]}"; do
        [[ -z $component || $component =~ ^(commander|validation|owner-gateway|commander-god|platform)$ ]] || {
            echo "invalid selective component: $component" >&2; exit 2;
        }
    done
done
IFS=, read -ra built_components <<< "$image_components"
for component in "${built_components[@]}"; do
    [[ -z $component ]] || selected "$restart_components" "$component" || {
        echo "a published $component image must be included in the restart plan" >&2; exit 2;
    }
done

repository=/root/ptw
platform=/opt/ptw/platform
commander_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
validation_compose=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")
platform_compose=(docker compose --env-file "$platform/.env" --project-directory "$platform" -f "$platform/docker-compose.yml")
started_epoch=$(date +%s)
stage_epoch=$started_epoch
stage_complete() {
    local label=$1 now
    now=$(date +%s)
    echo "PTW fast deploy '$label': $((now - stage_epoch))s (total $((now - started_epoch))s)"
    stage_epoch=$now
}

[[ -f $platform/.env && -f $repository/.env.commander && -f $repository/.env.owner-gateway ]]
[[ -z $(git -C "$repository" status --porcelain --untracked-files=no) ]]
[[ -z $(git -C "$platform" status --porcelain --untracked-files=no -- . ':!infrastructure/caddy/Caddyfile') ]]
if [[ -n $(git -C "$platform" status --porcelain --untracked-files=no -- infrastructure/caddy/Caddyfile) ]]; then
    python3 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/ptw_caddy_configuration.py" verify
fi
[[ $(git -C "$repository" rev-parse HEAD) == "$git_revision" ]]
[[ $(git -C "$platform" rev-parse HEAD) == "$platform_git_revision" ]]

pending_migrations=0
for migration in "$repository"/db/migrations/*.sql; do
    migration_name=$(basename "$migration")
    applied=$("${commander_compose[@]}" exec -T commander-db \
        psql -X -qAt -v ON_ERROR_STOP=1 -v migration_name="$migration_name" \
        -U ptw_commander -d ptw_commander <<'SQL'
SELECT count(*) FROM commander_schema_migrations WHERE name=:'migration_name';
SQL
    )
    if [[ $applied != 1 ]]; then pending_migrations=1; fi
done
[[ $pending_migrations == 0 || ${PTW_MIGRATIONS_AUTHORIZED:-0} == 1 ]] || {
    echo "pending migrations require the backup-bearing in-place deployment path" >&2; exit 1;
}

old_commander_image=$(docker inspect ptw-commander-api-1 --format '{{.Config.Image}}')
old_validation_image=$(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}')
old_gateway_image=$(docker inspect ptw-owner-gateway-1 --format '{{.Config.Image}}')
old_god_image=$(docker inspect ptw-commander-god-1 --format '{{.Config.Image}}')
old_release_running=$(docker inspect ptw-commander-release-1 --format '{{.State.Running}}' 2>/dev/null || true)
old_release_image=$(docker inspect ptw-commander-release-1 --format '{{.Config.Image}}' 2>/dev/null || true)
old_plan_running=$(docker inspect ptw-commander-plan-1 --format '{{.State.Running}}' 2>/dev/null || true)
old_platform_api_image=$(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}')
old_platform_worker_image=$(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}')
old_platform_auth_image=$(docker inspect ptw-agent-platform-codex-auth-1 --format '{{.Config.Image}}')
case "$old_commander_image" in ptw-commander:*) ;; *) echo "unexpected deployed Commander image" >&2; exit 1 ;; esac
case "$old_validation_image" in ptw-validation:*) ;; *) echo "unexpected deployed Validation image" >&2; exit 1 ;; esac
case "$old_gateway_image" in ptw-owner-gateway:*) ;; *) echo "unexpected deployed Gateway image" >&2; exit 1 ;; esac
case "$old_god_image" in
    ptw-validation:*|ptw-commander-god:*) ;;
    *) echo "unexpected deployed GOD image" >&2; exit 1 ;;
esac
case "$old_platform_api_image" in
    ptw-agent-platform-commander-api:*) old_platform_tag=${old_platform_api_image#*:} ;;
    *) echo "unexpected deployed platform API image" >&2; exit 1 ;;
esac
[[ $old_platform_worker_image == "ptw-agent-platform-commander-worker:$old_platform_tag" ]]
[[ $old_platform_auth_image == "ptw-agent-platform-codex-auth:$old_platform_tag" ]]

target_commander_image=$old_commander_image
target_validation_image=$old_validation_image
target_gateway_image=$old_gateway_image
target_god_image=$old_god_image
target_platform_tag=$old_platform_tag
if selected "$image_components" commander; then target_commander_image="ptw-commander:$release_tag"; fi
if selected "$image_components" validation; then target_validation_image="ptw-validation:$release_tag"; fi
if selected "$image_components" owner-gateway; then target_gateway_image="ptw-owner-gateway:$release_tag"; fi
if selected "$image_components" commander-god; then target_god_image="ptw-commander-god:$release_tag"; fi
if selected "$image_components" platform; then target_platform_tag=$release_tag; fi

for image in "$target_commander_image" "$target_validation_image" "$target_gateway_image" "$target_god_image"; do
    [[ $(docker image inspect "$image" --format '{{.Architecture}}') == amd64 ]] || {
        echo "missing Linux/amd64 image $image" >&2; exit 1;
    }
done
if selected "$image_components" platform; then
    for image in ptw-agent-platform-commander-api ptw-agent-platform-commander-worker ptw-agent-platform-codex-auth; do
        [[ $(docker image inspect "$image:$release_tag" --format '{{.Architecture}}') == amd64 ]] || exit 1
    done
fi

export PTW_COMMANDER_IMAGE=$target_commander_image
export PTW_VALIDATION_IMAGE=$target_validation_image
export PTW_OWNER_GATEWAY_IMAGE=$target_gateway_image
export PTW_COMMANDER_GOD_IMAGE=$target_god_image
export PTW_PLATFORM_IMAGE_TAG=$target_platform_tag

before=$(mktemp /run/ptw-fast-before.XXXXXX)
after=$(mktemp /run/ptw-fast-after.XXXXXX)
snapshot_ready=0
rollback_needed=1
cutover_started=0
env_persist_started=0
set_env_value() {
    local file=$1 key=$2 value=$3 temporary
    temporary=$(mktemp "${file}.next.XXXXXX")
    awk -v key="$key" -v value="$value" '
      BEGIN { found=0 }
      index($0,key "=")==1 { if (!found) print key "=" value; found=1; next }
      { print }
      END { if (!found) print key "=" value }
    ' "$file" > "$temporary"
    chmod --reference="$file" "$temporary"
    chown --reference="$file" "$temporary"
    mv -f -- "$temporary" "$file"
}
snapshot_authority() {
    "${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
        -U ptw_commander -d ptw_commander <<'SQL'
CREATE OR REPLACE FUNCTION pg_temp.ptw_authority_snapshot()
RETURNS TABLE(snapshot_line text)
LANGUAGE plpgsql AS $$
DECLARE item record;
DECLARE item_count bigint;
BEGIN
  FOR item IN SELECT schemaname,tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename
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
rollback() {
    set +e
    local failed=0
    echo "fast rollout failed; restoring replaced components" >&2
    export PTW_COMMANDER_IMAGE=$old_commander_image
    export PTW_VALIDATION_IMAGE=$old_validation_image
    export PTW_OWNER_GATEWAY_IMAGE=$old_gateway_image
    export PTW_COMMANDER_GOD_IMAGE=$old_god_image
    export PTW_PLATFORM_IMAGE_TAG=$old_platform_tag
    if [[ $env_persist_started -eq 1 ]]; then
        set_env_value "$repository/.env.commander" PTW_COMMANDER_IMAGE "$old_commander_image" || failed=1
        set_env_value "$repository/.env.commander" PTW_VALIDATION_IMAGE "$old_validation_image" || failed=1
        set_env_value "$repository/.env.commander" PTW_OWNER_GATEWAY_IMAGE "$old_gateway_image" || failed=1
        set_env_value "$repository/.env.commander" PTW_COMMANDER_GOD_IMAGE "$old_god_image" || failed=1
        if selected "$restart_components" platform; then
            set_env_value "$platform/.env" PTW_PLATFORM_IMAGE_TAG "$old_platform_tag" || failed=1
        fi
    fi
    if selected "$restart_components" platform; then
        "${platform_compose[@]}" up -d --no-deps --no-build --wait codex-auth commander-api || failed=1
        "${platform_compose[@]}" up -d --no-deps --no-build --wait commander-worker || failed=1
        [[ $(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}') == "$old_platform_api_image" ]] || failed=1
        [[ $(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}') == "$old_platform_worker_image" ]] || failed=1
        [[ $(docker inspect ptw-agent-platform-codex-auth-1 --format '{{.Config.Image}}') == "$old_platform_auth_image" ]] || failed=1
    fi
    rollback_commander=()
    selected "$restart_components" commander && rollback_commander+=(commander-api)
    selected "$restart_components" commander-god && rollback_commander+=(commander-god)
    if selected "$restart_components" commander-god; then
        if [[ $old_plan_running == true ]]; then
            rollback_commander+=(commander-plan)
        else
            "${commander_compose[@]}" rm -sf commander-plan >/dev/null 2>&1 || failed=1
        fi
        if [[ $old_release_running == true ]]; then
            rollback_commander+=(commander-release)
        else
            "${commander_compose[@]}" rm -sf commander-release >/dev/null 2>&1 || failed=1
        fi
    fi
    [[ ${#rollback_commander[@]} -eq 0 ]] || \
        "${commander_compose[@]}" up -d --no-deps --no-build --wait "${rollback_commander[@]}" || failed=1
    if selected "$restart_components" validation; then
        "${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api || failed=1
        [[ $(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}') == "$old_validation_image" ]] || failed=1
    fi
    if selected "$restart_components" owner-gateway; then
        "${commander_compose[@]}" up -d --no-deps --no-build --wait owner-gateway || failed=1
    fi
    [[ $(docker inspect ptw-commander-api-1 --format '{{.Config.Image}}') == "$old_commander_image" ]] || failed=1
    [[ $(docker inspect ptw-owner-gateway-1 --format '{{.Config.Image}}') == "$old_gateway_image" ]] || failed=1
    [[ $(docker inspect ptw-commander-god-1 --format '{{.Config.Image}}') == "$old_god_image" ]] || failed=1
    if [[ $old_release_running == true ]]; then
        [[ $(docker inspect ptw-commander-release-1 --format '{{.Config.Image}}') == "$old_release_image" ]] || failed=1
    fi
    [[ $failed -eq 0 ]] || echo "CRITICAL: fast rollout rollback verification failed" >&2
    return "$failed"
}
cleanup() {
    status=$?
    trap - EXIT HUP INT TERM
    if [[ $rollback_needed -eq 1 && $cutover_started -eq 1 ]]; then
        if [[ $snapshot_ready -eq 1 ]]; then
            if snapshot_authority > "$after"; then
                cmp -s "$before" "$after" || { echo "CRITICAL: authority changed during rejected fast rollout" >&2; status=1; }
            else
                echo "CRITICAL: unable to verify authority after rejected fast rollout" >&2
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
trap 'exit 1' HUP INT TERM

if [[ -n $restart_components ]]; then
    "${commander_compose[@]}" exec -T commander-db psql -X -qAt -v ON_ERROR_STOP=1 \
        -U ptw_commander -d ptw_commander <<'SQL'
DO $$
DECLARE instagram_active boolean;
BEGIN
  IF to_regclass('public.instagram_publications') IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS(SELECT 1 FROM instagram_publications WHERE state->>''status'' NOT IN (''published'',''published_unresolved'',''uncertain'',''failed''))' INTO instagram_active;
    IF instagram_active THEN RAISE EXCEPTION 'an Instagram publication is active'; END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM product_briefs WHERE status='generating')
     OR EXISTS (SELECT 1 FROM universal_studio_workspaces WHERE status IN ('queued','composing','generating_image'))
     OR EXISTS (SELECT 1 FROM studio_edit_checkpoints checkpoint WHERE NOT EXISTS (
       SELECT 1 FROM studio_learning_runs completed WHERE completed.checkpoint_id=checkpoint.entity_id AND completed.status='completed'))
     OR EXISTS (SELECT 1 FROM landing_workspaces WHERE status IN ('queued','composing','generating_images'))
     OR EXISTS (SELECT 1 FROM landing_checkpoints WHERE status='learning')
     OR EXISTS (SELECT 1 FROM meta_ads_deployments WHERE status NOT IN ('staged','failed')) THEN
    RAISE EXCEPTION 'a mutable PTW operation is active; fast rollout refused';
  END IF;
END $$;
SQL
    snapshot_authority > "$before"
    snapshot_ready=1
fi
stage_complete "preflight"

if [[ $pending_migrations == 1 ]]; then
    "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/apply_ptw_migrations_preserving.sh" "$repository"
    # The migration helper verifies old data and records the accepted new
    # schema baseline before application processes are restarted.
    snapshot_authority > "$before"
fi

"${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/prepare_commander_god_workspace.sh" "$git_revision"
[[ -z $restart_components ]] || cutover_started=1
if selected "$restart_components" platform; then
    "${platform_compose[@]}" up -d --no-deps --no-build --wait codex-auth commander-api
    "${platform_compose[@]}" up -d --no-deps --no-build --wait commander-worker
fi
stage_complete "platform"

commander_services=()
selected "$restart_components" commander && commander_services+=(commander-api)
selected "$restart_components" commander-god && commander_services+=(commander-god)
selected "$restart_components" commander-god && commander_services+=(commander-release)
selected "$restart_components" commander-god && commander_services+=(commander-plan)
[[ ${#commander_services[@]} -eq 0 ]] || \
    "${commander_compose[@]}" up -d --no-deps --no-build --wait "${commander_services[@]}"
if selected "$restart_components" validation; then
    "${validation_compose[@]}" up -d --no-deps --no-build --wait validation-api
fi
if selected "$restart_components" owner-gateway; then
    "${commander_compose[@]}" up -d --no-deps --no-build --wait owner-gateway
fi
stage_complete "application"

curl --fail --silent --max-time 5 http://127.0.0.1:8091/readyz >/dev/null
curl --fail --silent --max-time 5 http://127.0.0.1:8093/readyz >/dev/null
curl --fail --silent --max-time 5 http://127.0.0.1:8092/healthz >/dev/null
if selected "$restart_components" platform || selected "$restart_components" validation; then
    "${validation_compose[@]}" run -T --rm --no-deps validation-api python -m validation_pipeline.verify_bridge_contract
    "${validation_compose[@]}" run -T --rm --no-deps validation-api python -m validation_pipeline.verify_pexels
fi
stage_complete "scoped canaries"

if [[ $snapshot_ready -eq 1 ]]; then
    snapshot_authority > "$after"
    cmp -s "$before" "$after" || { echo "Commander authority changed during fast rollout" >&2; exit 1; }
fi
if selected "$restart_components" platform; then
    "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh" </dev/null
else
    "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh" --quick </dev/null
fi
PTW_MAINTENANCE_LOCK_HELD=1 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/audit_ptw_1gb.sh" </dev/null
(set -a; . "$platform/.env"; . "$repository/.env.commander"; \
  . "$repository/.env.owner-gateway"; set +a; \
  python3 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/send_ptw_bot_canary.py" --read-only)
stage_complete "audits"

for service in ptw-commander-api-1 ptw-validation-validation-api-1 ptw-owner-gateway-1 \
    ptw-commander-god-1 ptw-commander-release-1 ptw-commander-plan-1 ptw-agent-platform-commander-api-1 \
    ptw-agent-platform-commander-worker-1 ptw-agent-platform-codex-auth-1; do
    [[ $(docker inspect "$service" --format '{{.State.Health.Status}}') == healthy ]]
done
[[ $(docker inspect ptw-commander-api-1 --format '{{.Config.Image}}') == "$target_commander_image" ]]
[[ $(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}') == "$target_validation_image" ]]
[[ $(docker inspect ptw-owner-gateway-1 --format '{{.Config.Image}}') == "$target_gateway_image" ]]
[[ $(docker inspect ptw-commander-god-1 --format '{{.Config.Image}}') == "$target_god_image" ]]
[[ $(docker inspect ptw-commander-release-1 --format '{{.Config.Image}}') == "$target_god_image" ]]
[[ $(docker inspect ptw-agent-platform-commander-api-1 --format '{{.Config.Image}}') == "ptw-agent-platform-commander-api:$target_platform_tag" ]]
[[ $(docker inspect ptw-agent-platform-commander-worker-1 --format '{{.Config.Image}}') == "ptw-agent-platform-commander-worker:$target_platform_tag" ]]
[[ $(docker inspect ptw-agent-platform-codex-auth-1 --format '{{.Config.Image}}') == "ptw-agent-platform-codex-auth:$target_platform_tag" ]]

env_persist_started=1
set_env_value "$repository/.env.commander" PTW_COMMANDER_IMAGE "$target_commander_image"
set_env_value "$repository/.env.commander" PTW_VALIDATION_IMAGE "$target_validation_image"
set_env_value "$repository/.env.commander" PTW_OWNER_GATEWAY_IMAGE "$target_gateway_image"
set_env_value "$repository/.env.commander" PTW_COMMANDER_GOD_IMAGE "$target_god_image"
if selected "$restart_components" platform; then
    set_env_value "$platform/.env" PTW_PLATFORM_IMAGE_TAG "$target_platform_tag"
fi
if selected "$restart_components" validation; then
    "${validation_compose[@]}" exec -T validation-api python -m validation_pipeline.verify_approved_post_access
fi

if [[ ${PTW_DEFER_RELEASE_COMMIT:-0} != 1 ]]; then
install -d -m 0700 "$repository/.local"
revision_state=$(mktemp "$repository/.local/deployed-revision.next.XXXXXX")
printf '%s\n' "$git_revision" > "$revision_state"
chmod 0600 "$revision_state"
mv -f -- "$revision_state" "$repository/.local/deployed-revision"
fi
rollback_needed=0
stage_complete "commit"
echo "PTW fast rollout complete at $git_revision in $(($(date +%s) - started_epoch))s; restarted=${restart_components:-none}"
