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
http_status_file=$(mktemp /tmp/ptw-dataforseo-http-status.XXXXXX)
updated_environment=$(mktemp /root/ptw/.env.owner-gateway.XXXXXX)
trap 'stty echo 2>/dev/null || true; rm -f "$secret_config" "$response_file" "$http_status_file" "$updated_environment"' EXIT HUP INT TERM
chmod 600 "$secret_config" "$response_file" "$http_status_file" "$updated_environment"

escape_curl_config_value() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}
escaped_login=$(escape_curl_config_value "$dfs_login")
escaped_password=$(escape_curl_config_value "$dfs_password")

{
  printf 'user = "%s:%s"\n' "$escaped_login" "$escaped_password"
  printf 'silent\nshow-error\n'
  printf 'header = "Content-Type: application/json"\n'
  printf 'url = "https://sandbox.dataforseo.com/v3/serp/google/organic/task_post"\n'
  printf 'request = "POST"\n'
  printf 'data = "[{\\"keyword\\":\\"PTW provider readiness\\",\\"location_name\\":\\"United States\\",\\"language_code\\":\\"en\\",\\"priority\\":1}]"\n'
} > "$secret_config"
escaped_password=

if ! curl --config "$secret_config" --output "$response_file" --write-out '%{http_code}' > "$http_status_file"; then
  echo "DataForSEO sandbox could not be reached; production configuration was not changed." >&2
  exit 1
fi
if ! python3 - "$response_file" "$http_status_file" <<'PY'
import json, pathlib, sys
response_path, status_path = map(pathlib.Path, sys.argv[1:])
http_status = status_path.read_text().strip()[:3] or "unknown"
try:
    payload = json.loads(response_path.read_text())
except (json.JSONDecodeError, OSError):
    print(
        f"DataForSEO sandbox returned HTTP {http_status} without a JSON status. "
        "Check API Access, the IP whitelist, and account status, then contact DataForSEO support if it persists.",
        file=sys.stderr,
    )
    raise SystemExit(1)
provider_status = int(payload.get("status_code", 0))
if http_status == "200" and provider_status == 20000:
    raise SystemExit(0)
message = " ".join(str(payload.get("status_message") or "request rejected").split())[:400]
print(
    f"DataForSEO sandbox rejected the request (HTTP {http_status}, provider status {provider_status}: {message}).",
    file=sys.stderr,
)
raise SystemExit(1)
PY
then
  echo "Production configuration was not changed." >&2
  exit 1
fi

awk '!/^LAVAL_SEARCH_PROVIDER=|^DATAFORSEO_LOGIN=|^DATAFORSEO_PASSWORD=|^DATAFORSEO_VERIFIED=|^LAVAL_MAX_SPEND_USD=|^LAVAL_RESERVED_SPEND_USD=/' "$environment_file" > "$updated_environment"
{
  printf 'LAVAL_SEARCH_PROVIDER=dataforseo\n'
  printf 'DATAFORSEO_LOGIN=%s\n' "$dfs_login"
  printf 'DATAFORSEO_PASSWORD=%s\n' "$dfs_password"
  printf 'DATAFORSEO_VERIFIED=1\n'
  printf 'LAVAL_MAX_SPEND_USD=0.05\n'
  printf 'LAVAL_RESERVED_SPEND_USD=0.04\n'
} >> "$updated_environment"
chmod 600 "$updated_environment"
chown root:root "$updated_environment"
mv "$updated_environment" "$environment_file"

dfs_password=
rm -f "$secret_config" "$response_file" "$http_status_file"
trap - EXIT HUP INT TERM
echo "DataForSEO sandbox validation passed and the root-owned Laval provider settings were updated."
echo "Recreate only the Idea service with the canonical Compose command, then run the owner dependency audit."
