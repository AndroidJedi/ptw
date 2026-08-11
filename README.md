# PTW Agent Platform

Minimal Phase A trust and execution foundation for Proof Them Wrong. This VPS
runtime is not the Flutter/Firebase production web host.

## Services

- `commander-api`: small FastAPI control-plane skeleton with liveness/readiness
- `commander-worker`: background worker skeleton with database health probing
- `postgres`: private PostgreSQL event store
- `caddy`: loopback-only reverse proxy with baseline security headers

No autonomous agents, job execution, Telegram integration, or public API are
enabled in Phase A.

## Layout

Source lives in `/opt/ptw/platform`; mutable state lives in
`/opt/ptw/persistent-data`; future repositories belong in
`/opt/ptw/workspaces`; backups belong in `/opt/ptw/backups`.

## Bootstrap and operation

```bash
cd /opt/ptw/platform
cp .env.example .env
# Set POSTGRES_PASSWORD to a long random value; never commit .env.
./scripts/bootstrap.sh
./scripts/healthcheck.sh
docker compose logs --tail=100
docker compose down
```

The proxy listens at `http://127.0.0.1:8080`. See `docs/security.md` before
changing the bind address.

## Database migrations

SQL files in `migrations/` initialize a new PostgreSQL data directory in lexical
order. Later Phase A work should add a small explicit migration runner before
post-bootstrap schema changes are needed.

