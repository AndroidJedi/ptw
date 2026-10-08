#!/bin/bash
set -Eeuo pipefail

[[ $# -eq 2 && $1 == --confirm && $2 == 'INSTALL PTW RUNTIME EXEC GUARD' ]] || {
    echo "usage: $0 --confirm 'INSTALL PTW RUNTIME EXEC GUARD'" >&2; exit 2;
}
[[ $(id -u) -eq 0 ]] || { echo 'installer requires root' >&2; exit 1; }
exec 9>/run/lock/ptw-maintenance.lock
flock -n 9 || { echo 'another PTW operation is active' >&2; exit 73; }
source_directory=$(cd -- "$(dirname -- "$0")" && pwd)
install -d -m 0755 /usr/local/lib/ptw
install -m 0755 "$source_directory/ptw_runtime_exec_guard.py" /usr/local/lib/ptw/ptw_runtime_exec_guard.py.new
mv -f /usr/local/lib/ptw/ptw_runtime_exec_guard.py.new /usr/local/lib/ptw/ptw_runtime_exec_guard.py
cat > /etc/systemd/system/ptw-runtime-exec-guard.service <<'EOF'
[Unit]
Description=Reclaim old closed PTW exec runtime records
After=docker.service containerd.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/ptw/ptw_runtime_exec_guard.py clean
TimeoutStartSec=2min
Nice=10
UMask=0077
EOF
cat > /etc/systemd/system/ptw-runtime-exec-guard.timer <<'EOF'
[Unit]
Description=Bound PTW health-probe runtime metadata

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemd-analyze verify /etc/systemd/system/ptw-runtime-exec-guard.service /etc/systemd/system/ptw-runtime-exec-guard.timer
systemctl daemon-reload
flock -u 9
python3 /usr/local/lib/ptw/ptw_runtime_exec_guard.py check
systemctl start ptw-runtime-exec-guard.service
systemctl enable --now ptw-runtime-exec-guard.timer
systemctl is-active --quiet ptw-runtime-exec-guard.timer
python3 /usr/local/lib/ptw/ptw_runtime_exec_guard.py check
echo 'PTW runtime exec guard installed and verified'
