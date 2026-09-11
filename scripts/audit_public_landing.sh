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
asset_path=$(sed -n 's/.*src="\([^"?]*\/assets\/[^"?]*\.js\)".*/\1/p' "$directory/root.html" | head -1)
[[ $asset_path =~ ^/assets/[A-Za-z0-9._-]+\.js$ ]] || { echo "public shell JavaScript asset is missing" >&2; exit 1; }
curl --fail --silent --show-error --max-time 20 "$origin$asset_path" > "$directory/app.js"

grep -Fq 'noindex,nofollow,noarchive' "$directory/root.html" || { echo "public shell lacks noindex policy" >&2; exit 1; }
grep -Fq 'Disallow: /' "$directory/robots.txt" || { echo "public robots policy is not disallow-all" >&2; exit 1; }
grep -Eiq '^x-robots-tag:[[:space:]]*noindex, nofollow, noarchive' "$directory/root.headers" || { echo "public Hosting X-Robots-Tag is missing" >&2; exit 1; }
grep -Fq '<div id="root"></div>' "$directory/deep-link.html" || { echo "public SPA deep-link rewrite failed" >&2; exit 1; }
grep -Eiq '^content-security-policy:' "$directory/root.headers" || { echo "public Hosting CSP is missing" >&2; exit 1; }
grep -Eiq '^content-security-policy:.*connect\.facebook\.net' "$directory/root.headers" || { echo "public Hosting CSP does not permit the Meta Pixel library" >&2; exit 1; }
grep -Eiq '^content-security-policy:.*www\.facebook\.com' "$directory/root.headers" || { echo "public Hosting CSP does not permit Meta Pixel measurement" >&2; exit 1; }
grep -Fq '1056720310312959' "$directory/app.js" || { echo "public bundle has the wrong Meta Pixel ID" >&2; exit 1; }
grep -Fq 'connect.facebook.net/en_US/fbevents.js' "$directory/app.js" || { echo "public bundle lacks the Meta Pixel library boundary" >&2; exit 1; }
grep -Fq 'natal_meta_pixel_consent_v1' "$directory/app.js" || { echo "public bundle lacks the Meta Pixel consent boundary" >&2; exit 1; }

echo "Verified Natal public shell root, noindex policy, robots policy, consent-gated Meta Pixel, CSP, and deep-link rewrite at $origin"
