#!/bin/bash
set -Eeuo pipefail
repository=${1:?repository required}
[[ $repository == /root/ptw && $(id -u) == 0 && ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 ]] || exit 2
# Installed helpers must be updated as well as the repository copy. Existing
# SSH authorization and private credentials are deliberately not rewritten.
install -o root -g root -m 0755 "$repository/scripts/receive_ptw_mobile_release.sh" /usr/local/libexec/ptw-mobile-release
"$repository/scripts/install_ptw_skill_sync.sh"
if [[ -f /opt/ptw/platform/infrastructure/caddy/Caddyfile ]]; then
    python3 - "$repository/deploy/owner-gateway/Caddyfile.fragment" /opt/ptw/platform/infrastructure/caddy/Caddyfile <<'PY'
import pathlib, re, sys
fragment, destination = map(pathlib.Path, sys.argv[1:])
content = destination.read_text()
new = fragment.read_text()
# The existing installation uses a dedicated host block. Replace exactly that
# block; all unrelated platform and public-domain routes remain intact.
host = new.split('{', 1)[0].strip()
start = re.search(r'(?m)^' + re.escape(host) + r'\s*\{', content)
if not start:
    raise SystemExit('Owner Gateway Caddy host block was not found')
depth = 1
index = start.end()
while depth and index < len(content):
    depth += (content[index] == '{') - (content[index] == '}')
    index += 1
if depth:
    raise SystemExit('Owner Gateway Caddy block is incomplete')
destination.write_text(content[:start.start()] + new.strip() + content[index:])
PY
    docker exec ptw-agent-platform-caddy-1 caddy validate --config /etc/caddy/Caddyfile >/dev/null
    docker exec ptw-agent-platform-caddy-1 caddy reload --config /etc/caddy/Caddyfile
    curl --fail --silent --max-time 15 https://commander.proove-them-wrong.com/healthz >/dev/null
fi
