#!/usr/bin/env bash
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="$repository/.venv/bin/python"
workspace="${STUDIO_WORKSPACE_PATH:-$repository/.local/studio-workspace}"

if [[ ! -x "$python" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-validation.txt" >&2
  exit 1
fi
if [[ ! -d "$repository/apps/commander-web/node_modules" ]]; then
  echo "Missing web dependencies. Run: npm --prefix apps/commander-web ci" >&2
  exit 1
fi

port_is_listening() {
  "$python" - "$1" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.settimeout(0.25)
    raise SystemExit(listener.connect_ex(("127.0.0.1", int(sys.argv[1]))) != 0)
PY
}

for port in 8088 5173; do
  if port_is_listening "$port"; then
    echo "Local Studio port $port is already in use. Stop the prior Studio process and run this launcher again." >&2
    exit 1
  fi
done

cleanup() {
  if [[ -n "${studio_api_pid:-}" ]]; then
    kill "$studio_api_pid" 2>/dev/null || true
    wait "$studio_api_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$repository"
STUDIO_WORKSPACE_PATH="$workspace" \
STUDIO_TUNE_MODE=1 \
STUDIO_TUNE_REPOSITORY_ROOT="$repository" \
STUDIO_TUNE_STATE_PATH="$repository/.local/studio-tune" \
"$python" -m uvicorn \
  validation_pipeline.studio_local_api:create_app --factory \
  --host 127.0.0.1 --port 8088 &
studio_api_pid=$!

for _attempt in {1..50}; do
  if ! kill -0 "$studio_api_pid" 2>/dev/null; then
    wait "$studio_api_pid"
    exit 1
  fi
  if curl --fail --silent http://127.0.0.1:8088/healthz >/dev/null \
    && curl --fail --silent \
      -H 'Authorization: Bearer e2e-owner-token' \
      -H 'X-Firebase-AppCheck: e2e-app-check' \
      http://127.0.0.1:8088/api/v1/studio >/dev/null; then
    break
  fi
  sleep 0.1
done
curl --fail --silent \
  -H 'Authorization: Bearer e2e-owner-token' \
  -H 'X-Firebase-AppCheck: e2e-app-check' \
  http://127.0.0.1:8088/api/v1/studio >/dev/null || {
  echo "Local Owner API did not become ready on 127.0.0.1:8088." >&2
  exit 1
}

echo "PTW local app: http://127.0.0.1:5173/?e2e=1"
VITE_E2E=true VITE_LOCAL_APP=true npm --prefix apps/commander-web run dev -- --host 127.0.0.1 --strictPort
