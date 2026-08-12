#!/usr/bin/env bash
set -uo pipefail

platform_dir=/opt/ptw/platform
pass_count=0
fail_count=0

check() {
  local name=$1
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS  %s\n' "$name"
    pass_count=$((pass_count + 1))
  else
    printf 'FAIL  %s\n' "$name"
    fail_count=$((fail_count + 1))
  fi
}

cd "$platform_dir" || exit 1
check "Compose configuration" docker compose config --quiet
check "All containers running" bash -c "docker compose ps --status running --services | grep -qx postgres && docker compose ps --status running --services | grep -qx commander-api && docker compose ps --status running --services | grep -qx commander-worker && docker compose ps --status running --services | grep -qx caddy"
check "Loopback readiness" curl --fail --silent --show-error http://127.0.0.1:${PTW_HTTP_PORT:-8080}/health/ready
check "Public health route" curl --fail --silent --show-error http://127.0.0.1:${PTW_HTTP_PORT:-8080}/health
check "PostgreSQL" docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-ptw}" -d "${POSTGRES_DB:-ptw}"
check "Host Codex metadata" scripts/refresh-codex-metadata.sh
check "Automated integration" docker compose run --rm --no-deps \
  -e PYTHONPATH=/app/source -v "$platform_dir:/app/source:ro" \
  commander-api python /app/source/tests/integration.py

printf '\nSummary: %d PASS, %d FAIL\n' "$pass_count" "$fail_count"
test "$fail_count" -eq 0
