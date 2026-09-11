#!/bin/bash
# Recovery is run from the accepted release, never the candidate being deployed.
set -Eeuo pipefail
action=${1:?action required}
directory=${2:?directory required}
[[ $(id -u) == 0 && $directory == /var/tmp/ptw-mobile-release.*/recovery ]] || exit 2
repository=/root/ptw
platform=/opt/ptw/platform
if [[ $action == snapshot ]]; then
    mkdir -m 0700 "$directory"
    git -C "$repository" rev-parse HEAD > "$directory/revision"
    git -C "$repository" archive HEAD | tar -x -C "$directory"
    cp -p "$repository/.env.commander" "$directory/commander.env"
    cp -p "$repository/.env.owner-gateway" "$directory/gateway.env"
    cp -p "$repository/.local/deployed-revision" "$directory/deployed-revision"
    [[ ! -f /usr/local/libexec/ptw-mobile-release ]] || cp -p /usr/local/libexec/ptw-mobile-release "$directory/receiver"
    cp -p /opt/ptw/platform/infrastructure/caddy/Caddyfile "$directory/Caddyfile"
    for service in commander-api commander-god commander-release commander-plan owner-gateway; do
        docker inspect "ptw-$service-1" --format '{{.Config.Image}}' 2>/dev/null > "$directory/$service.image" || true
    done
    docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}' > "$directory/validation.image"
    python3 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/ptw_hosting_recovery.py" snapshot "$directory/hosting.json"
elif [[ $action == restore ]]; then
    # Both revisions remain reachable. Detach at the accepted commit without
    # rewriting history or touching the separate owner development checkout.
    old_revision=$(<"$directory/revision")
    current_revision=$(git -C "$repository" rev-parse HEAD)
    if [[ $current_revision != "$old_revision" ]]; then
        git -C "$repository" -c core.hooksPath=/dev/null switch --detach "$old_revision"
    fi
    # Git restores file bytes, not the worker group's write permissions. Repair
    # the restored skill view explicitly; candidate Git hooks stay disabled.
    (
        cd "$repository"
        "${PTW_TRUSTED_RELEASE_ROOT:-$directory}/scripts/install_ptw_skill_sync.sh"
        # The verifier resolves the canonical repository from its own path, so
        # execute the restored accepted copy rather than the archived snapshot.
        python3 "$repository/scripts/verify_ptw_skills.py"
    )
    cp -p "$directory/commander.env" "$repository/.env.commander"
    cp -p "$directory/gateway.env" "$repository/.env.owner-gateway"
    cp -p "$directory/deployed-revision" "$repository/.local/deployed-revision"
    [[ ! -f "$directory/receiver" ]] || cp -p "$directory/receiver" /usr/local/libexec/ptw-mobile-release
    if [[ -f "$directory/Caddyfile" ]]; then
        cp -p "$directory/Caddyfile" /opt/ptw/platform/infrastructure/caddy/Caddyfile
        docker exec ptw-agent-platform-caddy-1 caddy reload --config /etc/caddy/Caddyfile || docker restart ptw-agent-platform-caddy-1 >/dev/null
    fi
    commander=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-directory "$repository" -f "$repository/docker-compose.commander.yml")
    validation=(docker compose --env-file "$platform/.env" --env-file "$repository/.env.commander" --env-file "$repository/.env.owner-gateway" --project-name ptw-validation --project-directory "$repository" -f "$repository/docker-compose.validation.yml")
    "${commander[@]}" up -d --no-deps --no-build --wait commander-api commander-god commander-release owner-gateway
    if [[ -s "$directory/commander-plan.image" ]]; then "${commander[@]}" up -d --no-deps --no-build --wait commander-plan; fi
    if [[ ! -s "$directory/commander-plan.image" ]] && docker inspect ptw-commander-plan-1 >/dev/null 2>&1; then
        docker stop ptw-commander-plan-1 >/dev/null
        docker rm ptw-commander-plan-1 >/dev/null
    fi
    "${validation[@]}" up -d --no-deps --no-build --wait validation-api
    for service in commander-api commander-god commander-release commander-plan owner-gateway; do
        [[ ! -s "$directory/$service.image" ]] || [[ $(docker inspect "ptw-$service-1" --format '{{.Config.Image}}') == "$(<"$directory/$service.image")" ]]
    done
    [[ $(docker inspect ptw-validation-validation-api-1 --format '{{.Config.Image}}') == "$(<"$directory/validation.image")" ]]
    python3 "${PTW_TRUSTED_RELEASE_ROOT:-$directory}/scripts/ptw_hosting_recovery.py" restore "$directory/hosting.json"
else exit 2
fi
