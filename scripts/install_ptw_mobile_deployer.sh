#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 CI_PUBLIC_KEY_FILE" >&2
    exit 2
fi
[[ $(id -u) -eq 0 && -s $1 ]] || exit 1
repository=/root/ptw
install -o root -g root -m 0755 "$repository/scripts/receive_ptw_mobile_release.sh" \
    /usr/local/libexec/ptw-mobile-release
id ptw-release >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/ptw-release --shell /bin/bash ptw-release
install -d -o ptw-release -g ptw-release -m 0700 /var/lib/ptw-release/.ssh
public_key=$(<"$1")
[[ $public_key =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ .*)?$ ]] || exit 2
printf 'restrict,command="sudo -n /usr/local/libexec/ptw-mobile-release" %s\n' "$public_key" \
    > /var/lib/ptw-release/.ssh/authorized_keys
chown ptw-release:ptw-release /var/lib/ptw-release/.ssh/authorized_keys
chmod 0600 /var/lib/ptw-release/.ssh/authorized_keys
printf 'ptw-release ALL=(root) NOPASSWD: /usr/local/libexec/ptw-mobile-release\n' \
    > /etc/sudoers.d/ptw-mobile-release
chmod 0440 /etc/sudoers.d/ptw-mobile-release
visudo -cf /etc/sudoers.d/ptw-mobile-release >/dev/null
echo "PTW mobile deploy receiver installed"
