#!/bin/sh
set -eu

repository_root=${PTW_REPOSITORY_ROOT:-/root/ptw}
platform_environment=${PTW_PLATFORM_ENVIRONMENT:-/opt/ptw/platform/.env}

cd "$repository_root"
test -f "$platform_environment"
test -f .env.commander
test -f .env.owner-gateway

owner_container=$(docker compose \
  --env-file "$platform_environment" --env-file .env.commander \
  -f docker-compose.commander.yml ps -aq owner-gateway)
idea_container=$(docker compose \
  --env-file "$platform_environment" --env-file .env.owner-gateway \
  -f docker-compose.idea-generation.yml ps -aq idea-generation-api)

test -n "$owner_container" || {
  echo "Owner Gateway container is missing" >&2
  exit 1
}
test -n "$idea_container" || {
  echo "Idea Laval container is missing" >&2
  exit 1
}
test "$(docker inspect --format '{{.State.Status}}' "$owner_container")" = running || {
  echo "Owner Gateway container is not running" >&2
  exit 1
}
test "$(docker inspect --format '{{.State.Status}}' "$idea_container")" = running || {
  echo "Idea Laval container is not running" >&2
  exit 1
}
test "$(docker inspect --format '{{.State.Health.Status}}' "$owner_container")" = healthy || {
  echo "Owner Gateway container is not healthy" >&2
  exit 1
}
test "$(docker inspect --format '{{.State.Health.Status}}' "$idea_container")" = healthy || {
  echo "Idea Laval container is not healthy" >&2
  exit 1
}

owner_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$owner_container")
idea_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$idea_container")
test "$owner_project" != "$idea_project" || {
  echo "Owner Gateway and Idea Laval share a Compose project" >&2
  exit 1
}
idea_networks=$(docker inspect --format '{{json .NetworkSettings.Networks}}' "$idea_container")
python3 -c 'import json, sys; raise SystemExit(0 if "ptw_default" in json.loads(sys.argv[1]) else 1)' \
  "$idea_networks" || {
    echo "Idea Laval is missing the Commander database network" >&2
    exit 1
  }

curl --fail --silent --show-error http://127.0.0.1:8092/healthz >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8093/healthz >/dev/null

docker exec "$owner_container" python -c '
import httpx
from owner_gateway.settings import Settings

settings = Settings.from_environment()
response = httpx.get(
    settings.idea_service_url + "/internal/web/laval/runs",
    headers={"X-PTW-Owner-Gateway-Token": settings.idea_service_token},
    timeout=5,
)
response.raise_for_status()
items = response.json()["items"]
print(f"Owner Gateway -> Idea Laval ready; runs={len(items)}")
'

docker exec "$idea_container" python -m idea_generation.verify_bridge_contract

if [ "${PTW_REQUIRE_BRANDING_READY:-0}" = "1" ]; then
  docker exec "$owner_container" python -c '
import httpx
from owner_gateway.settings import Settings

settings = Settings.from_environment()
headers = {"X-PTW-Owner-Gateway-Token": settings.idea_service_token}
provider = httpx.get(
    settings.idea_service_url + "/internal/web/branding/providers",
    headers=headers,
    timeout=5,
)
provider.raise_for_status()
readiness = provider.json()
if readiness.get("ready") is not True:
    missing = ",".join(str(item) for item in readiness.get("missing") or []) or "unknown"
    raise SystemExit(f"Branding provider is not ready; missing={missing}")
if readiness.get("configured_provider") != "bridge":
    raise SystemExit("Production Branding is not using the established Codex bridge")
if readiness.get("credential_source") != "existing_codex_chatgpt_auth":
    raise SystemExit("Production Branding credential source is not the established Codex authentication")
if readiness.get("text_ready") is not True or readiness.get("image_ready") is not True:
    raise SystemExit("Branding text/image bridge contract is incomplete")
cases = httpx.get(
    settings.idea_service_url + "/internal/web/branding/cases?limit=1",
    headers=headers,
    timeout=5,
)
cases.raise_for_status()
count = len(cases.json().get("items") or [])
if count < 1:
    raise SystemExit("Branding has no selectable completed live Idea case")
print(f"Branding provider and candidate contract ready; sampled_cases={count}")
'
fi

echo "Owner Gateway and Idea Laval dependency audit passed."
