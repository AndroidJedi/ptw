# Commander disaster recovery

Status: implemented minimum-cost recovery baseline.

Commander state is recoverable from three inexpensive sources:

1. GitHub: code, migrations, policies, and canonical Markdown.
2. A PostgreSQL custom-format logical dump: entities, relationship graph,
   decisions, tasks, inbox, and outbox.
3. A compressed asset archive: uploaded and generated creative files.

Runtime secrets are deliberately excluded. Restore them from the root-owned VPS
environment, never from a backup committed to Git.

## Create and verify a backup

```sh
cd /root/ptw
chmod 700 /opt/ptw/commander-backups
scripts/backup_commander.sh /opt/ptw/commander-backups
scripts/verify_commander_backup.sh /opt/ptw/commander-backups/<timestamp>
```

Each timestamped directory is mode 700 and contains `database.dump`,
`assets.tar.gz`, the Git revision, policy snapshot, and SHA-256 manifest.

The VPS installs `/etc/cron.d/ptw-commander-backup`, which creates a backup at
03:17 UTC and prunes local daily recovery points older than 14 days. Copy
backups off this VPS. A backup
on the same disk does not protect against disk or provider loss. Example cron:

```cron
17 3 * * * cd /root/ptw && scripts/backup_commander.sh /opt/ptw/commander-backups >>/var/log/ptw-commander-backup.log 2>&1
```

Retain at least seven daily and four weekly offsite copies initially. Storage cost is dominated
by media; PostgreSQL logical dumps should remain small during validation.

## Restore

Restore replaces the current Commander database and asset volume. Confirm the
backup path carefully:

```sh
cd /root/ptw
scripts/restore_commander.sh /absolute/path/to/backup --confirm-replace-current-state
curl -fsS http://127.0.0.1:8091/healthz
curl -fsS http://127.0.0.1:8091/readyz
```

The restore script verifies checksums and archive readability before stopping
the API/worker. It then recreates the Commander database, restores assets, and
restarts services. Git code must be checked out at the recorded revision or a
compatible later migration revision.

## Recovery limitations

- There is no offsite destination configured yet.
- There is no point-in-time WAL archive; recovery granularity is the latest
  successful logical backup.
- The unrelated `/opt/ptw/platform` database and workspace need their own
  backup policy; this procedure covers the new learning/knowledge service.
- A restore drill should run after schema or asset-storage changes and at least
  quarterly.
