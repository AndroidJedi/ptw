# PTW Agent Platform

PTW Commander v0.1 is a small, deterministic Telegram control plane backed by
PostgreSQL. It does not use an LLM, embeddings, or a knowledge graph.

## Services

- `commander-api`: FastAPI health endpoints and Telegram long polling
- `commander-worker`: PostgreSQL-backed job executor and Telegram responder
- `git-watcher`: zero-model-token polling and durable Telegram notification outbox
- `git-credential-agent`: isolated in-memory access to the PTW deploy key
- `postgres`: private PostgreSQL 16 event/job store
- `caddy`: HTTPS edge for the Commander hostname; only `/health` is public

PostgreSQL data persists at `/opt/ptw/persistent-data/postgres` and has no
host-published port. Caddy publishes 80/443 for automatic HTTPS and retains a
diagnostic listener at `127.0.0.1:8080`.

## Telegram commands

`/ping`, `/status`, `/version`, and `/help` are routed without model
interpretation. Only numeric IDs in `TELEGRAM_ALLOWED_USER_IDS` are accepted.
Every received message, authorization decision, job transition, response, and
health check is append-logged in PostgreSQL without message bodies or secrets.

Use `/task <free-form request>` as the primary owner interface for fixes,
features, reviews, and changes. The command queues the existing specification-
driven engineering workflow; `/engineer repo=ptw <task>` remains compatible.
Attach screenshots or reference images and put `/task ...` in the caption to
make the pending attachments available to the job.

`/research creative ...` and `/creative ...` are also durable tasks. The poller
acknowledges `TASK-<id>` before forwarding, propagates that ID to the creative
service, stores the bridge result, and prefixes the final Telegram result with
the same ID. Transient bridge failures create `ISSUE-<id>`, report a bounded
retry, and remain available through `/inspect`.

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

Detailed design and runbooks are in `docs/architecture.md`,
`docs/bootstrap-report.md`, `docs/operations.md`, and `docs/security-model.md`.

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

## Repository registry and main watcher

`repositories` is the engineering allowlist. The registered monorepo is
`repo=ptw` (`Proof Them Wrong`, `git@github.com:AndroidJedi/ptw.git`, `main`).
Its versioned `project.components.json` declares component paths and validation;
the registry identifies it as a monorepo and stores the manifest filename as
metadata. Arbitrary Git URLs
are not accepted.

`git-watcher` polls `ptw/main` with `git ls-remote` every
`GIT_MAIN_WATCH_INTERVAL_SECONDS` (default 300). Initial discovery stores the
SHA silently. A change atomically advances `watched_branches`, adds one durable
outbox row per configured authorized Telegram ID, and records
`GIT_BRANCH_UPDATED`. Delivery retries five times with bounded exponential
backoff and records `GIT_NOTIFICATION_SENT` or `GIT_NOTIFICATION_FAILED`.
Commit subjects and Git metadata produce a bounded summary; Codex, OpenAI, and
all LLMs are absent from this path.
