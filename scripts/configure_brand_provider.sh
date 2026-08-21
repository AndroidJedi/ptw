#!/bin/sh
set -eu

if [ "$#" -ne 0 ]; then
  echo "Usage: $0" >&2
  exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root on the PTW VPS." >&2
  exit 1
fi

repository=${PTW_REPOSITORY_ROOT:-/root/ptw}
lock_file=${PTW_MAINTENANCE_LOCK:-/run/lock/ptw-maintenance.lock}
test -x "$repository/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh" || {
  echo "Branding dependency audit is missing." >&2
  exit 1
}

exec 9>"$lock_file"
flock -n 9 || {
  echo "Another PTW maintenance operation is active." >&2
  exit 73
}

echo "Branding reuses the existing ChatGPT-authenticated Codex bridge; no additional OpenAI API key is configured."
PTW_REQUIRE_BRANDING_READY=1 \
  "$repository/skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh"
