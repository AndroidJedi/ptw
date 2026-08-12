# PTW Agent Platform

PTW Commander v0.1 is a small, deterministic Telegram control plane backed by
PostgreSQL. It does not use an LLM, embeddings, or a knowledge graph.

## Services

- `commander-api`: FastAPI health endpoints and Telegram long polling
- `commander-worker`: PostgreSQL-backed job executor and Telegram responder
- `postgres`: private PostgreSQL 16 event/job store
- `caddy`: loopback-only reverse proxy with baseline security headers

PostgreSQL data persists at `/opt/ptw/persistent-data/postgres`. PostgreSQL has
no host-published port; Caddy remains bound to `127.0.0.1:8080` by default.

## Telegram commands

`/ping`, `/status`, `/version`, and `/help` are routed without model
interpretation. Only numeric IDs in `TELEGRAM_ALLOWED_USER_IDS` are accepted.
Every received message, authorization decision, job transition, response, and
health check is append-logged in PostgreSQL without message bodies or secrets.

`/status` reports Commander, worker, PostgreSQL, Git, Codex CLI, disk space, and
queued/failed job counts. A missing optional command such as `codex` is shown as
unavailable; it does not crash the job.

## Bootstrap and operation

```bash
cd /opt/ptw/platform
cp .env.example .env
# Set POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN, and TELEGRAM_ALLOWED_USER_IDS.
chmod 600 .env
./scripts/bootstrap.sh
./scripts/healthcheck.sh
docker compose logs --tail=100
docker compose down
```

Do not commit `.env`. The bot token should be rotated if it is ever pasted into
a ticket, chat, shell history, or log.

## Database and job flow

At API startup, numbered SQL files are applied once under a PostgreSQL advisory
lock and recorded in `schema_migrations`; this also upgrades an existing Phase A
database. Core tables are `users`, `sessions`, `jobs`, and `events`.

A valid Telegram message creates a queued row. The worker atomically claims it
with `FOR UPDATE SKIP LOCKED`, executes it, sends the Telegram response, and
persists the terminal state. The normal event sequence is:

```text
USER_MESSAGE_RECEIVED -> COMMAND_ACCEPTED -> JOB_CREATED -> JOB_STARTED
-> JOB_COMPLETED -> RESPONSE_SENT
```

## SecretStore

Application code retrieves bootstrap credentials through `SecretStore`, not by
using `.env` as its storage interface. The Phase A `EnvironmentSecretStore`
implements `get` and `exists`; `put` deliberately rejects writes because process
environment is immutable. A later backend can implement the same interface with
Vault, a cloud secret manager, or an encrypted local store without changing
Commander or worker call sites.
