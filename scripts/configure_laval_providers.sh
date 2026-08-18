#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root on the PTW VPS." >&2
  exit 1
fi

environment_file=/root/ptw/.env.owner-gateway
if [ ! -f "$environment_file" ]; then
  echo "Required environment file is missing: $environment_file" >&2
  exit 1
fi

printf 'DataForSEO API login: '
IFS= read -r dfs_login
[ -n "$dfs_login" ] || { echo "API login is required." >&2; exit 1; }

printf 'DataForSEO API password (input hidden): '
trap 'stty echo 2>/dev/null || true' EXIT HUP INT TERM
stty -echo
IFS= read -r dfs_password
stty echo
printf '\n'
[ -n "$dfs_password" ] || { echo "API password is required." >&2; exit 1; }

secret_config=$(mktemp /tmp/ptw-dataforseo-curl.XXXXXX)
response_file=$(mktemp /tmp/ptw-dataforseo-response.XXXXXX)
updated_environment=$(mktemp /root/ptw/.env.owner-gateway.XXXXXX)
trap 'stty echo 2>/dev/null || true; rm -f "$secret_config" "$response_file" "$updated_environment"' EXIT HUP INT TERM
chmod 600 "$secret_config" "$response_file" "$updated_environment"

{
  printf 'user = "%s:%s"\n' "$dfs_login" "$dfs_password"
  printf 'silent\nshow-error\nfail-with-body\n'
  printf 'header = "Content-Type: application/json"\n'
  printf 'url = "https://sandbox.dataforseo.com/v3/serp/google/organic/task_post"\n'
  printf 'request = "POST"\n'
  printf 'data = "[{\\"keyword\\":\\"PTW provider readiness\\",\\"location_name\\":\\"United States\\",\\"language_code\\":\\"en\\",\\"priority\\":1}]"\n'
} > "$secret_config"

if ! curl --config "$secret_config" > "$response_file"; then
  echo "DataForSEO sandbox authentication failed; production configuration was not changed." >&2
  exit 1
fi
if ! python3 - "$response_file" <<'PY'
import json, pathlib, sys
payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
raise SystemExit(0 if int(payload.get("status_code", 0)) == 20000 else 1)
PY
then
  echo "DataForSEO sandbox rejected the credentials; production configuration was not changed." >&2
  exit 1
fi

awk '!/^LAVAL_SEARCH_PROVIDER=|^DATAFORSEO_LOGIN=|^DATAFORSEO_PASSWORD=|^DATAFORSEO_VERIFIED=|^LAVAL_MAX_SPEND_USD=|^LAVAL_RESERVED_SPEND_USD=/' "$environment_file" > "$updated_environment"
{
  printf 'LAVAL_SEARCH_PROVIDER=dataforseo\n'
  printf 'DATAFORSEO_LOGIN=%s\n' "$dfs_login"
  printf 'DATAFORSEO_PASSWORD=%s\n' "$dfs_password"
  printf 'DATAFORSEO_VERIFIED=1\n'
  printf 'LAVAL_MAX_SPEND_USD=0.005\n'
  printf 'LAVAL_RESERVED_SPEND_USD=0.004\n'
} >> "$updated_environment"
chmod 600 "$updated_environment"
chown root:root "$updated_environment"
mv "$updated_environment" "$environment_file"

dfs_password=
rm -f "$secret_config" "$response_file"
trap - EXIT HUP INT TERM
echo "DataForSEO sandbox validation passed and the root-owned Laval provider settings were updated."
echo "Recreate only the Idea service with the canonical Compose command, then run the owner dependency audit."
