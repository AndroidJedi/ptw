# Bounded VPS storage recovery

Multiple Owner 401s can coincide with a full host even after successful Google
sign-in. Start with `df -h /`, `df -i /`, Docker healthcheck output, and bounded
`du -x` reads of `/opt/ptw`, `/var/log`, Docker/containerd and `/var/tmp`. Check
Firebase owner lookup and public key retrieval without printing credentials;
never infer a Google sign-in failure from the generic API message alone.

Keep the maintenance lock during reclaim. Enumerate all running/stopped
container image references before removing unused images. Dangling/cache pruning
can reclaim nothing when backups or logs are the actual source. Do not prune
volumes, active container images, authority files, credentials or conversation
state. Preserve the latest checked recovery points and inspect incomplete copies
separately. A failed `assets.tar.gz` is not a completed backup.

The canonical `scripts/ptw_storage_guard.py` owns only
`/opt/ptw/commander-backups`. Retain at most seven complete recovery points within
4 GiB, protecting the latest two and verifying their complete SHA-256 manifests
before any deletion. Match real `YYYYMMDDTHHMMSSZ` names; an extra pair of `?`
in the legacy glob prevented every retention deletion. Reject symlinks, paths
outside the closed manifest, incomplete copies and wrong-directory targets.

`backup` takes the same lock, runs retention before and after export, preserves
the complete current PostgreSQL database and historical assets volume, and
records the accepted revision. It refuses insufficient headroom, enforces the
3 GiB free-space reserve and replacement byte budget while streaming, and removes
its own incomplete staging on failure. Never tie the only cleanup to backup
success. If the two protected points outgrow the budget or authority growth
consumes the reserve, fail visibly and move backups off-host or expand storage;
do not sacrifice protected copies or relax the reserve automatically.

The owner-authorized installation entrypoint is
`scripts/install_ptw_storage_guard.sh --confirm 'INSTALL PTW STORAGE GUARD'`.
It replaces the obsolete checkout-based backup cron, installs a persistent
15-minute `ptw-storage-guard.timer`, caps journald at 256 MiB with 3 GiB keep-free,
and rotates the backup log. It changes no application image, schema or credential.
Verify the installed script digest, effective journald configuration, actual
timer next-elapse, successful service result and a real backup with its manifest
plus `pg_restore --list`. Test lock contention and low-space refusal using
disposable local directories, not the live database. Require repeated healthy
services and an actual owner read before declaring recovery complete.
