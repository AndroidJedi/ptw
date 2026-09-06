#!/bin/sh
set -eu

repository_root=${PTW_REPOSITORY_ROOT:-/root/ptw}
platform_root=${PTW_PLATFORM_ROOT:-/opt/ptw/platform}
platform_environment=${PTW_PLATFORM_ENVIRONMENT:-/opt/ptw/platform/.env}
cd "$repository_root"
test -f "$platform_environment"
test -f .env.commander
test -f .env.owner-gateway

commander_compose="docker compose --env-file $platform_environment --env-file .env.commander --env-file .env.owner-gateway --project-directory $repository_root -f docker-compose.commander.yml"
validation_compose="docker compose --env-file $platform_environment --env-file .env.commander --env-file .env.owner-gateway --project-name ptw-validation --project-directory $repository_root -f docker-compose.validation.yml"
platform_compose="docker compose --env-file $platform_environment --project-directory $platform_root -f $platform_root/docker-compose.yml"

owner_container=$($commander_compose ps -q owner-gateway)
commander_container=$($commander_compose ps -q commander-api)
validation_container=$($validation_compose ps -q validation-api)
codex_auth_container=$($platform_compose ps -q codex-auth)
platform_worker_container=$($platform_compose ps -q commander-worker)
for pair in "Owner_Gateway:$owner_container" "Commander:$commander_container" "Validation:$validation_container" "Codex_Auth:$codex_auth_container" "Platform_Worker:$platform_worker_container"; do
  name=${pair%%:*}; container=${pair#*:}
  test -n "$container" || { echo "$name container is missing" >&2; exit 1; }
  test "$(docker inspect --format '{{.State.Status}}' "$container")" = running || { echo "$name is not running" >&2; exit 1; }
  test "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy || { echo "$name is not healthy" >&2; exit 1; }
done
docker exec "$platform_worker_container" test -r /run/ptw-codex-auth/auth.json || {
  echo "Platform worker cannot read its root-owned Codex credential mount" >&2
  exit 1
}

auth_networks=$(docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$codex_auth_container")
printf '%s\n' "$auth_networks" | grep -Eq '(^|_)backend$' || {
  echo "Codex Auth is missing its private backend network" >&2
  exit 1
}
printf '%s\n' "$auth_networks" | grep -Eq '(^|_)edge$' || {
  echo "Codex Auth is missing outbound edge-network access" >&2
  exit 1
}

owner_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$owner_container")
validation_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$validation_container")
test "$owner_project" != "$validation_project" || { echo "Validation is not isolated from Owner Gateway" >&2; exit 1; }

curl --fail --silent --show-error http://127.0.0.1:8091/readyz >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8092/healthz >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8093/readyz >/dev/null
docker exec "$validation_container" python -m validation_pipeline.manage verify
docker exec "$validation_container" python -c '
from validation_pipeline.config import Settings
from validation_pipeline.provider import StructuredBridge

settings = Settings.from_environment()
capabilities = StructuredBridge(
    settings.bridge_url, settings.bridge_token, settings.model,
).capabilities()
print("Structured bridge capabilities:", capabilities)
'
docker exec "$owner_container" python -c '
import json
import os
import time
import urllib.request

headers = {
    "X-PTW-Codex-Authorization-Token": os.environ["PTW_CODEX_AUTH_BRIDGE_TOKEN"],
}
# The service may perform three bounded 90-second attempts after a fresh login.
deadline = time.monotonic() + 300
while True:
    request = urllib.request.Request(
        "http://codex-auth:8094/v1/authorization", headers=headers,
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        value = json.load(response)
    if value.get("status") != "verifying" or time.monotonic() >= deadline:
        break
    time.sleep(2)
assert value.get("status") == "authorized", value.get("status")
assert value.get("test_status") == "passed", value.get("test_status")
print("ChatGPT/Codex authorization working test passed")
'

if docker inspect "$validation_container" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -Eq '^(DATAFORSEO_|POSITIONING_|LANDING_|YOUTUBE_)'; then
  echo "Validation still exposes a retired research or Landing setting" >&2
  exit 1
fi
docker inspect "$validation_container" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -q '^PEXELS_API_KEY=....................' || { echo "Pexels runtime key is missing" >&2; exit 1; }

for retired_container in ptw-idea-generation-idea-generation-api-1 ptw-commander-worker-1 ptw-commander-ad-worker-1 ptw-marketing-positioning-marketing-positioning-api-1 ptw-ad-studio-local-relay ptw-ad-studio-local-validation ptw-ad-studio-local-db; do
  test -z "$(docker ps -q --filter "name=^/$retired_container$")" || {
    echo "retired container $retired_container is running" >&2
    exit 1
  }
done
docker exec "$owner_container" python -c '
import sys
import owner_gateway.api
for name in ("idea_generation", "marketing_positioning", "owner_gateway.landing", "commander.ad_generation", "commander.worker"):
    assert name not in sys.modules, name
print("Product Brief and Studio Owner Gateway dependency boundary ready")
'

python3 scripts/verify_ptw_skills.py
echo "PTW Validation dependency audit passed."
