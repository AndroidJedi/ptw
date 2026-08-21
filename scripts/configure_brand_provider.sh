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
environment_file=${PTW_OWNER_ENVIRONMENT:-$repository/.env.owner-gateway}
lock_file=${PTW_MAINTENANCE_LOCK:-/run/lock/ptw-maintenance.lock}
test -f "$environment_file" || {
  echo "Required owner environment file is missing." >&2
  exit 1
}

exec 9>"$lock_file"
flock -n 9 || {
  echo "Another PTW maintenance operation is active." >&2
  exit 73
}

trap 'stty echo 2>/dev/null || true' EXIT HUP INT TERM
printf 'OpenAI API key for Branding (input hidden): '
stty -echo
IFS= read -r openai_api_key
stty echo
printf '\n'
test -n "$openai_api_key" || {
  echo "OpenAI API key is required." >&2
  exit 1
}

curl_config=$(mktemp /tmp/ptw-brand-openai-curl.XXXXXX)
response_file=$(mktemp /tmp/ptw-brand-openai-response.XXXXXX)
status_file=$(mktemp /tmp/ptw-brand-openai-status.XXXXXX)
updated_environment=$(mktemp "$repository/.env.owner-gateway.XXXXXX")
trap 'stty echo 2>/dev/null || true; rm -f "$curl_config" "$response_file" "$status_file" "$updated_environment"' EXIT HUP INT TERM
chmod 600 "$curl_config" "$response_file" "$status_file" "$updated_environment"

escaped_key=$(printf '%s' "$openai_api_key" | sed 's/\\/\\\\/g; s/"/\\"/g')
validate_model() {
  model=$1
  {
    printf 'silent\nshow-error\n'
    printf 'header = "Authorization: Bearer %s"\n' "$escaped_key"
    printf 'url = "https://api.openai.com/v1/models/%s"\n' "$model"
  } > "$curl_config"
  : > "$response_file"
  : > "$status_file"
  if ! curl --config "$curl_config" --output "$response_file" --write-out '%{http_code}' > "$status_file"; then
    echo "OpenAI could not be reached; production configuration was not changed." >&2
    exit 1
  fi
  if ! python3 - "$model" "$response_file" "$status_file" <<'PY'
import json
import pathlib
import sys

model, response_name, status_name = sys.argv[1:]
status = pathlib.Path(status_name).read_text().strip()[:3] or "unknown"
try:
    payload = json.loads(pathlib.Path(response_name).read_text())
except (json.JSONDecodeError, OSError):
    print(f"OpenAI returned HTTP {status} without valid JSON; configuration was not changed.", file=sys.stderr)
    raise SystemExit(1)
if status == "200" and payload.get("id") == model:
    raise SystemExit(0)
message = " ".join(str((payload.get("error") or {}).get("message") or "request rejected").split())[:300]
print(f"OpenAI rejected {model} readiness (HTTP {status}: {message}); configuration was not changed.", file=sys.stderr)
raise SystemExit(1)
PY
  then
    exit 1
  fi
}

validate_model gpt-5-mini
validate_model gpt-image-2
escaped_key=

awk '!/^OPENAI_API_KEY=|^BRAND_PROVIDER=|^BRAND_TEXT_MODEL=|^BRAND_IMAGE_MODEL=/' \
  "$environment_file" > "$updated_environment"
{
  printf 'OPENAI_API_KEY=%s\n' "$openai_api_key"
  printf 'BRAND_PROVIDER=openai\n'
  printf 'BRAND_TEXT_MODEL=gpt-5-mini\n'
  printf 'BRAND_IMAGE_MODEL=gpt-image-2\n'
} >> "$updated_environment"
chmod 600 "$updated_environment"
chown root:root "$updated_environment"
mv "$updated_environment" "$environment_file"

openai_api_key=
rm -f "$curl_config" "$response_file" "$status_file"
trap - EXIT HUP INT TERM
echo "OpenAI text and image model access passed; root-owned Branding settings were updated."
echo "Recreate only the Idea service on the current pinned image, then run the Branding readiness audit."
