#!/usr/bin/env bash
set -euo pipefail

target=${TIKTOK_SECRETS_FILE:-/opt/ptw/secrets/tiktok/config.env}
expected_username=${TIKTOK_EXPECTED_USERNAME:-natal_cast}
production=0
[[ $target != /opt/ptw/secrets/tiktok/config.env ]] || production=1

[[ $expected_username == natal_cast ]] || { echo "TikTok account must remain pinned to natal_cast" >&2; exit 2; }
read -r -p "TikTok client key: " client_key
read -r -s -p "TikTok client secret: " client_secret
echo
read -r -s -p "Existing 64-hex token encryption key (leave empty to generate): " encryption_key
echo
if [[ -z $encryption_key ]]; then encryption_key=$(openssl rand -hex 32); fi
[[ $client_key =~ ^[A-Za-z0-9._-]{3,200}$ ]] || { echo "TikTok client key is invalid" >&2; exit 2; }
[[ -n $client_secret && ${#client_secret} -le 500 ]] || { echo "TikTok client secret is invalid" >&2; exit 2; }
[[ $encryption_key =~ ^[0-9A-Fa-f]{64}$ ]] || { echo "TikTok token encryption key must be 64 hex characters" >&2; exit 2; }

if [[ $production -eq 1 ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "Production TikTok configuration must run as root" >&2; exit 1; }
  install -d -o root -g 10001 -m 0750 "$(dirname "$target")"
else
  mkdir -p "$(dirname "$target")"
  [[ ! -L $target ]] || { echo "Refusing symlinked TikTok secrets file" >&2; exit 1; }
fi
temporary=$(mktemp "$(dirname "$target")/.tiktok-config.XXXXXX")
trap 'rm -f "$temporary"' EXIT
chmod 0600 "$temporary"
printf '%s\n' "TIKTOK_CLIENT_KEY=$client_key" "TIKTOK_CLIENT_SECRET=$client_secret" "TIKTOK_TOKEN_ENCRYPTION_KEY=$encryption_key" >"$temporary"
if [[ $production -eq 1 ]]; then
  chown root:10001 "$temporary"
  chmod 0440 "$temporary"
else
  chmod 0600 "$temporary"
fi
mv -f -- "$temporary" "$target"
trap - EXIT
echo "TikTok server credentials stored without printing secret values."
echo "Authorize @natal_cast from the Studio TikTok panel after restarting Validation."
