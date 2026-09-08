#!/bin/bash
set -Eeuo pipefail

if [[ $# -gt 1 || ${1:-} == -* ]]; then
    echo "usage: $0 [https://natal-dashboard-dev.web.app]" >&2
    exit 2
fi
origin=${1:-https://natal-dashboard-dev.web.app}
[[ $origin =~ ^https://[A-Za-z0-9.-]+$ ]] || { echo "archive origin must be one HTTPS host" >&2; exit 2; }

repository=$(git rev-parse --show-toplevel)
timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
archive="$repository/.local/archives/natal-dashboard-dev/$timestamp"
mkdir -p "$archive/site" "$archive/screenshots" "$archive/metadata"

curl --fail --silent --show-error --location --max-time 30 --dump-header "$archive/metadata/root.headers" "$origin/" > "$archive/site/index.html"
firebase --project natal-dashboard-dev hosting:sites:get natal-dashboard-dev --json > "$archive/metadata/firebase-site.json"
firebase --project natal-dashboard-dev hosting:channel:list --site natal-dashboard-dev --json > "$archive/metadata/firebase-channels.json"
git -C "$repository" rev-parse HEAD > "$archive/metadata/ptw-git-revision.txt"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$archive/metadata/archived-at.txt"
printf '%s\n' "$origin" > "$archive/metadata/source-origin.txt"

node "$repository/scripts/archive_natal_dashboard_screenshots.mjs" \
    "$origin" "$archive/screenshots" "$archive/site/mirror"
(
    cd "$archive"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo "Archived current natal-dashboard-dev assets, screenshots, Firebase metadata, and SHA-256 manifest under $archive"
