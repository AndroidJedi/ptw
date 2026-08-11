#!/usr/bin/env bash
set -euo pipefail

platform_dir=/opt/ptw/platform
cd "$platform_dir"
docker compose ps
curl --fail --silent --show-error http://127.0.0.1:${PTW_HTTP_PORT:-8080}/health/ready
echo

