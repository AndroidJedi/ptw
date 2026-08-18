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
docker inspect --format '{{json .NetworkSettings.Networks}}' "$idea_container" \
  | python3 -c 'import json, sys; raise SystemExit(0 if "ptw_default" in json.load(sys.stdin) else 1)' || {
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

echo "Owner Gateway and Idea Laval dependency audit passed."
