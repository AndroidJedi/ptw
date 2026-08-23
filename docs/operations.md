# Operations

Run commands from `/opt/ptw/platform`.

## Lifecycle and logs

```bash
./scripts/bootstrap.sh                 # validate, refresh Codex metadata, build/start
docker compose stop                    # stop without removing containers
docker compose start
docker compose restart commander-api commander-worker
docker compose down                    # persistent bind-mounted data is retained
docker compose up -d                   # recover after down/reboot
docker compose logs --tail=200 -f commander-api commander-worker caddy
docker compose ps
```

## Health and tests

```bash
./scripts/healthcheck.sh
./scripts/smoke-test.sh
curl -fsS http://127.0.0.1:8080/health/ready
curl -fsS https://commander.proove-them-wrong.com/health
```

The authenticated structured capabilities response must expose exactly the three
Marketing Positioning modes plus `natal_landing_revision`; retired Laval and
Branding modes are not accepted. The Commander API and
worker images are both prebuilt and pinned with `PTW_PLATFORM_IMAGE_TAG`; never
build either on the 1 GB production host. Recreate them one at a time and run
the PTW Owner Gateway dependency audit before starting a Positioning or Landing
run. Require a fresh schema-bound canary for every advertised PTW mode.

## Migrations

Add an immutable, numbered SQL file under `migrations/`. Commander applies new
files once at startup under a PostgreSQL advisory lock and records them in
`schema_migrations`:

```bash
docker compose restart commander-api
docker compose exec -T postgres psql -U ptw -d ptw -c 'TABLE schema_migrations;'
```

## Backup and recovery basics

Create logical backups outside the database data directory:

```bash
mkdir -p /opt/ptw/backups
docker compose exec -T postgres pg_dump -U ptw -d ptw -Fc > /opt/ptw/backups/ptw.dump
```

Test restores into a separate database before relying on a backup. For recovery,
stop Commander and worker, restore with `pg_restore`, start services, then run the
smoke test. A raw copy of live PostgreSQL files is not a safe logical backup.

Caddy certificates persist below `/opt/ptw/persistent-data/caddy`. PostgreSQL
survives `docker compose down` because its bind mount is outside the repository.

## Engineering jobs

Use `/engineer repo=ptw <bounded task>`. Each isolated job stores `spec.md`,
controlled `attachments/`, and `result.md`. `CODEX_MAX_RETRIES` defaults to 2.
Inspect `engineering_runs.failure_stage` and audit events before resuming; PR
creation safely reuses an existing open PR for the same branch.

GitHub currently reports `main` as unprotected. Recommended repository rules are
PR-required changes, blocked force-push/deletion, and required Flutter/preview CI.
The runner already rejects direct `main` pushes in code.

## GitHub and main watcher

Authenticate the host CLI using device/browser flow:

```bash
gh auth login --hostname github.com --git-protocol ssh --web
gh auth status
```

The write-enabled `PTW Commander VPS` deploy key is scoped by GitHub to
`AndroidJedi/ptw`. Compose mounts the single key read-only only into
`git-credential-agent`; consumers mount its named socket volume and use
`ssh -F /etc/ptw-git/ssh_config`. Never mount `/root/.ssh` into jobs.

```bash
docker compose exec -T postgres psql -U ptw -d ptw -c 'TABLE watched_branches;'
docker compose exec -T postgres psql -U ptw -d ptw -c 'SELECT id,repository_id,branch,status,attempts FROM git_notifications ORDER BY id DESC LIMIT 20;'
docker compose logs --tail=100 git-watcher
```

`GIT_MAIN_WATCH_INTERVAL_SECONDS` defaults to 300 and
`GIT_MAIN_WATCH_MAX_COMMITS` to 5. Initial and unchanged observations are
silent. A future webhook should call the same processor/outbox and replace only
the polling detector.
