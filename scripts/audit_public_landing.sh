#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 1 || ! $1 =~ ^https://[A-Za-z0-9.-]+$ ]]; then
    echo "usage: $0 https://PUBLIC_HOST" >&2
    exit 2
fi
origin=${1%/}
directory=$(mktemp -d)
trap 'rm -rf -- "$directory"' EXIT

curl --fail --silent --show-error --max-time 20 --dump-header "$directory/root.headers" "$origin/" > "$directory/root.html"
curl --fail --silent --show-error --max-time 20 "$origin/robots.txt" > "$directory/robots.txt"
curl --fail --silent --show-error --max-time 20 "$origin/ai/public-shell-probe" > "$directory/deep-link.html"

grep -Fq 'noindex,nofollow,noarchive' "$directory/root.html" || { echo "public shell lacks noindex policy" >&2; exit 1; }
grep -Fq 'Disallow: /' "$directory/robots.txt" || { echo "public robots policy is not disallow-all" >&2; exit 1; }
grep -Eiq '^x-robots-tag:[[:space:]]*noindex, nofollow, noarchive' "$directory/root.headers" || { echo "public Hosting X-Robots-Tag is missing" >&2; exit 1; }
grep -Fq '<div id="root"></div>' "$directory/deep-link.html" || { echo "public SPA deep-link rewrite failed" >&2; exit 1; }
grep -Eiq '^content-security-policy:' "$directory/root.headers" || { echo "public Hosting CSP is missing" >&2; exit 1; }

echo "Verified Natal public shell root, noindex policy, robots policy, CSP, and deep-link rewrite at $origin"
