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
curl -fsS https://commander.prove-them-wrong.com/health
```

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
