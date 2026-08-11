#!/usr/bin/env bash
set -euo pipefail

platform_dir=/opt/ptw/platform
if [[ ! -f "$platform_dir/.env" ]]; then
  echo "Missing $platform_dir/.env; copy .env.example and set a random POSTGRES_PASSWORD." >&2
  exit 1
fi

docker compose --project-directory "$platform_dir" config --quiet
docker compose --project-directory "$platform_dir" up -d --build
docker compose --project-directory "$platform_dir" ps

