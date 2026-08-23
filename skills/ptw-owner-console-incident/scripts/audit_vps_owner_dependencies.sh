#!/bin/sh
set -eu

repository_root=${PTW_REPOSITORY_ROOT:-/root/ptw}
platform_environment=${PTW_PLATFORM_ENVIRONMENT:-/opt/ptw/platform/.env}
cd "$repository_root"
test -f "$platform_environment"
test -f .env.commander
test -f .env.owner-gateway

commander_compose="docker compose --env-file $platform_environment --env-file .env.commander --env-file .env.owner-gateway --project-directory $repository_root -f docker-compose.commander.yml"
positioning_compose="docker compose --env-file $platform_environment --env-file .env.commander --env-file .env.owner-gateway --project-name ptw-marketing-positioning --project-directory $repository_root -f docker-compose.marketing-positioning.yml"

owner_container=$($commander_compose ps -q owner-gateway)
commander_container=$($commander_compose ps -q commander-api)
positioning_container=$($positioning_compose ps -q marketing-positioning-api)
for pair in "Owner_Gateway:$owner_container" "Commander:$commander_container" "Marketing_Positioning:$positioning_container"; do
  name=${pair%%:*}; container=${pair#*:}
  test -n "$container" || { echo "$name container is missing" >&2; exit 1; }
  test "$(docker inspect --format '{{.State.Status}}' "$container")" = running || { echo "$name is not running" >&2; exit 1; }
  test "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy || { echo "$name is not healthy" >&2; exit 1; }
done

owner_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$owner_container")
positioning_project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$positioning_container")
test "$owner_project" != "$positioning_project" || { echo "Positioning is not isolated from Owner Gateway" >&2; exit 1; }

curl --fail --silent --show-error http://127.0.0.1:8091/readyz >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8092/healthz >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8093/readyz >/dev/null
docker exec "$positioning_container" python -m marketing_positioning.manage verify

docker exec "$owner_container" python -c '
from marketing_positioning.provider import BridgeProvider
from owner_gateway.landing_revision import LandingRevisionProvider
from owner_gateway.settings import Settings
s = Settings.from_environment()
cap = BridgeProvider(s.landing_llm_bridge_url, s.telegram_bot_token, s.landing_llm_model).capabilities()
expected = {"marketing_positioning_research_plan", "marketing_positioning_document", "marketing_positioning_revision"}
assert set(cap["marketing_positioning_modes"]) == expected
assert "natal_landing_revision" in cap["landing_modes"]
LandingRevisionProvider(bridge_url=s.landing_llm_bridge_url, token=s.telegram_bot_token, skill_path=s.repository_path / "skills/natal-landing-builder/SKILL.md", model=s.landing_llm_model).verify_ready()
print("Positioning and Landing bridge contracts ready")
'

for retired_container in ptw-idea-generation-idea-generation-api-1 ptw-commander-worker-1 ptw-commander-ad-worker-1; do
  test -z "$(docker ps -q --filter "name=^/$retired_container$")" || {
    echo "retired container $retired_container is running" >&2
    exit 1
  }
done
docker exec "$owner_container" python -c '
import sys
import owner_gateway.api
for name in ("idea_generation", "PIL", "commander.ad_generation", "commander.worker"):
    assert name not in sys.modules, name
print("Owner Gateway dependency boundary ready")
'

python3 scripts/verify_ptw_skills.py
echo "PTW v2 dependency audit passed."
