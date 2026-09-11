#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 4 || ( $1 != local && $1 != vps ) ]]; then
  echo "usage: $0 local|vps AD_ACCOUNT_ID_OR_DASH PAGE_ID INSTAGRAM_USERNAME" >&2
  exit 2
fi

mode=$1
ad_account_id=${2#act_}
[[ $ad_account_id != - ]] || ad_account_id=
page_id=$3
instagram_username=${4#@}
graph_version=v26.0
instagram_media_origin=${META_INSTAGRAM_MEDIA_ORIGIN:-}
repository=$(git rev-parse --show-toplevel)
python=${PYTHON_BIN:-$repository/.venv/bin/python}

[[ -z $ad_account_id || $ad_account_id =~ ^[0-9]+$ ]] || { echo "Ad Account ID must contain digits only" >&2; exit 2; }
[[ $page_id =~ ^[0-9]+$ ]] || { echo "Page ID must contain digits only" >&2; exit 2; }
[[ $instagram_username =~ ^[A-Za-z0-9._]+$ ]] || { echo "Instagram username is invalid" >&2; exit 2; }
[[ -x $python ]] || python=python3

if [[ $mode == vps ]]; then
  [[ $(id -u) -eq 0 ]] || { echo "VPS configuration must run as root" >&2; exit 1; }
  target=/opt/ptw/secrets/meta-ads/config.env
  name_prefix='[PTW VPS]'
  install -d -o root -g 10001 -m 0750 "$(dirname "$target")"
else
  target=$repository/.local/local-studio.env
  name_prefix='[PTW LOCAL]'
  mkdir -p "$(dirname "$target")"
  if [[ -L $target ]]; then
    echo "Refusing symlinked local secrets file" >&2
    exit 1
  fi
fi

printf 'Paste a newly generated Meta system-user token (input is hidden): ' >&2
IFS= read -r -s access_token
printf '\n' >&2
[[ ${#access_token} -ge 20 ]] || { echo "The Meta token is too short" >&2; exit 1; }

temporary_directory=$(mktemp -d)
output_file=
cleanup() {
  unset access_token
  if [[ -n ${output_file:-} && -f $output_file ]]; then
    rm -f -- "$output_file"
  fi
  rm -rf -- "$temporary_directory"
}
trap cleanup EXIT INT TERM

graph_get() {
  local url=$1 destination=$2
  if ! printf 'oauth2-bearer = "%s"\n' "$access_token" | curl \
    --config - --globoff --proto '=https' --tlsv1.2 --silent --show-error --fail \
    --connect-timeout 10 --max-time 30 --output "$destination" "$url"
  then
    echo "Meta asset verification failed. Recheck token permissions and assigned assets." >&2
    exit 1
  fi
}

accounts_json=$temporary_directory/accounts.json
page_json=$temporary_directory/page.json
instagram_json=$temporary_directory/instagram.json
base=https://graph.facebook.com/$graph_version
if [[ -n $ad_account_id ]]; then
graph_get "$base/me/adaccounts?fields=id,name,currency,account_status&limit=100" "$accounts_json"
graph_get "$base/act_$ad_account_id?fields=id,name,promote_pages" "$page_json"
graph_get "$base/act_$ad_account_id/instagram_accounts?fields=id,username&limit=100" "$instagram_json"

instagram_actor_id=$("$python" - "$accounts_json" "$page_json" "$instagram_json" \
  "$ad_account_id" "$page_id" "$instagram_username" <<'PY'
import json
import sys

accounts_path, page_path, instagram_path, account_id, page_id, username = sys.argv[1:]
with open(accounts_path, encoding="utf-8") as source:
    accounts = json.load(source).get("data", [])
with open(page_path, encoding="utf-8") as source:
    account = json.load(source)
with open(instagram_path, encoding="utf-8") as source:
    instagram = json.load(source).get("data", [])

if not any(str(item.get("id", "")).removeprefix("act_") == account_id for item in accounts):
    raise SystemExit("Configured Ad Account is not assigned to this system user.")
pages = account.get("promote_pages") or {}
pages = pages.get("data", []) if isinstance(pages, dict) else pages
if not any(str(item.get("id")) == page_id for item in pages):
    raise SystemExit("Configured Facebook Page is not available to this Ad Account.")
matches = [item for item in instagram if str(item.get("username", "")).lower() == username.lower()]
if len(matches) != 1 or not matches[0].get("id"):
    raise SystemExit("The requested Instagram account is not uniquely available to this Ad Account.")
print(matches[0]["id"])
PY
)

else
  # An organic-only account must not depend on advertising permissions.
  # System-user tokens discover their assigned Pages through /me/accounts.
  # Meta can reject a direct Page read even when that discovery response
  # contains the Page and its linked professional Instagram account.
  graph_get "$base/me/accounts?fields=id,name,instagram_business_account{id,username}&limit=100" "$instagram_json"
  instagram_actor_id=$("$python" - "$instagram_json" "$page_id" "$instagram_username" <<'PYACCOUNT'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as source:
    pages = json.load(source).get("data", [])
matches = [item for item in pages if str(item.get("id", "")) == sys.argv[2]]
if len(matches) != 1:
    raise SystemExit("The requested Facebook Page is not assigned to this system user.")
account = matches[0].get("instagram_business_account") or {}
if not account.get("id") or str(account.get("username", "")).lower() != sys.argv[3].lower():
    raise SystemExit("The requested professional Instagram account is not linked to this Page.")
print(account["id"])
PYACCOUNT
)
fi

umask 077
output_file=$(mktemp "${target}.tmp.XXXXXX")
if [[ $mode == local && -f $target ]]; then
  awk '!/^META_SYSTEM_USER_ACCESS_TOKEN=/ && !/^META_AD_ACCOUNT_ID=/ && \
       !/^META_PAGE_ID=/ && !/^META_INSTAGRAM_ACTOR_ID=/ && \
       !/^META_GRAPH_API_VERSION=/ && !/^META_ADS_NAME_PREFIX=/ && !/^META_INSTAGRAM_MEDIA_ORIGIN=/' \
    "$target" > "$output_file"
fi
printf '%s\n' \
  "META_SYSTEM_USER_ACCESS_TOKEN=$access_token" \
  "META_AD_ACCOUNT_ID=$ad_account_id" \
  "META_PAGE_ID=$page_id" \
  "META_INSTAGRAM_ACTOR_ID=$instagram_actor_id" \
  "META_GRAPH_API_VERSION=$graph_version" \
  "META_ADS_NAME_PREFIX=$name_prefix" >> "$output_file"
if [[ $mode == local ]]; then
  printf 'META_INSTAGRAM_MEDIA_ORIGIN=%s\n' "$instagram_media_origin" >> "$output_file"
fi

if [[ $mode == vps ]]; then
  chown root:10001 "$output_file"
  chmod 0440 "$output_file"
else
  chmod 0600 "$output_file"
fi
mv -f -- "$output_file" "$target"
output_file=
unset access_token

echo "Selected Meta assets verified and the locked $mode configuration was saved."
echo "Restart the PTW API process before checking Ads / Реклама and Instagram publishing."
echo "Organic publishing additionally needs pages_show_list, instagram_basic, instagram_content_publish and pages_read_engagement."
echo "For local publishing, set META_INSTAGRAM_MEDIA_ORIGIN to a public HTTPS origin reaching this API before configuration."
echo "For VPS publishing, set that nonsecret origin in Validation Compose; do not add it to the strict secret file."
