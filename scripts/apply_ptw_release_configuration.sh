#!/bin/bash
set -Eeuo pipefail
repository=${1:?repository required}
[[ $repository == /root/ptw && $(id -u) == 0 && ${PTW_MAINTENANCE_LOCK_HELD:-0} == 1 ]] || exit 2
# Installed helpers must be updated as well as the repository copy. Existing
# SSH authorization and private credentials are deliberately not rewritten.
install -o root -g root -m 0755 "$repository/scripts/receive_ptw_mobile_release.sh" /usr/local/libexec/ptw-mobile-release
(cd "$repository"; "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/install_ptw_skill_sync.sh")
if [[ -f /opt/ptw/platform/infrastructure/caddy/Caddyfile ]]; then
    changed=$(python3 "${PTW_TRUSTED_RELEASE_ROOT:-$repository}/scripts/ptw_caddy_configuration.py" apply --repository "$repository")
    if [[ $changed == changed ]]; then
        docker exec ptw-agent-platform-caddy-1 caddy validate --config /etc/caddy/Caddyfile >/dev/null
        # Existing production deliberately disables Caddy's admin endpoint.
        docker exec ptw-agent-platform-caddy-1 caddy reload --config /etc/caddy/Caddyfile || docker restart ptw-agent-platform-caddy-1 >/dev/null
    fi
    curl --fail --silent --max-time 15 https://commander.proove-them-wrong.com/healthz >/dev/null
fi
