#!/bin/bash
set -Eeuo pipefail

[[ $# -eq 2 && $1 == --confirm && $2 == 'INSTALL PTW STORAGE GUARD' ]] || {
    echo "usage: $0 --confirm 'INSTALL PTW STORAGE GUARD'" >&2; exit 2;
}
[[ $(id -u) -eq 0 ]] || { echo 'installer requires root' >&2; exit 1; }
exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo 'another PTW maintenance operation is active' >&2; exit 73; }
source_directory=$(cd -- "$(dirname -- "$0")" && pwd)
install -d -m 0755 /usr/local/lib/ptw /etc/systemd/journald.conf.d
install -m 0755 "$source_directory/ptw_storage_guard.py" /usr/local/lib/ptw/ptw_storage_guard.py.new
mv -f /usr/local/lib/ptw/ptw_storage_guard.py.new /usr/local/lib/ptw/ptw_storage_guard.py
cat > /etc/systemd/journald.conf.d/60-ptw-storage.conf <<'EOF'
[Journal]
SystemMaxUse=256M
SystemKeepFree=3G
SystemMaxFileSize=16M
MaxRetentionSec=7day
EOF
cat > /etc/systemd/system/ptw-storage-guard.service <<'EOF'
[Unit]
Description=PTW bounded recovery retention and disk reserve
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/ptw/ptw_storage_guard.py maintain
TimeoutStartSec=15min
Nice=10
IOSchedulingClass=idle
UMask=0077
EOF
cat > /etc/systemd/system/ptw-storage-guard.timer <<'EOF'
[Unit]
Description=Check PTW storage every 15 minutes

[Timer]
OnCalendar=*-*-* *:0/15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
# Replace the obsolete checkout-based schedule, including its mismatched glob
# and its cleanup-after-success condition. The guard runs before and after export.
cat > /etc/cron.d/ptw-commander-backup <<'EOF'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
17 3 * * * root /usr/bin/python3 /usr/local/lib/ptw/ptw_storage_guard.py backup >>/var/log/ptw-commander-backup.log 2>&1
EOF
cat > /etc/logrotate.d/ptw-storage <<'EOF'
/var/log/ptw-commander-backup.log {
    daily
    maxsize 10M
    rotate 7
    compress
    missingok
    notifempty
    create 0600 root root
}
EOF
chmod 0644 /etc/cron.d/ptw-commander-backup /etc/logrotate.d/ptw-storage
systemd-analyze verify /etc/systemd/system/ptw-storage-guard.service /etc/systemd/system/ptw-storage-guard.timer
systemctl daemon-reload
systemctl restart systemd-journald
journalctl --rotate
journalctl --vacuum-size=256M --vacuum-time=7d
# Release the shared lock before invoking the installed lock-taking service.
flock -u 9
systemctl start ptw-storage-guard.service
systemctl enable --now ptw-storage-guard.timer
systemctl is-active --quiet ptw-storage-guard.timer
python3 /usr/local/lib/ptw/ptw_storage_guard.py check
echo 'PTW storage guard installed and verified'
