# Commander prototype operations

The first vertical slice is a local, standard-library Python module. It writes
an append-only JSONL event stream and a projection snapshot to a chosen output
directory. It does not contact Telegram, Instagram, or any AI provider.

Run from the repository root:

```sh
python3 -m commander.demo --output-dir .local/commander-demo
```

Run tests:

```sh
python3 -m unittest discover -s tests/commander -v
```

The output directory is disposable demonstration state and is ignored by Git.
For a service deployment, install the optional dependencies and apply all
migrations in order:

```sh
python3 -m pip install -r requirements-commander.txt
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/001_commander_foundation.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/002_commander_control_plane.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/003_telegram_runtime.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/004_outbox_retry.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/005_feedback_weights.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/006_telegram_delivery_links.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/007_workspace_task_acknowledgements.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/008_session_checkpoints.sql
```

Construct the database repository with `connect_postgres(DATABASE_URL)`. Domain
entity/relationship changes and their outbox records commit or roll back
together. An outbox worker must claim records inside `store.transaction()` and
mark them published only after the external delivery succeeds.

Codex workspace intake uses `POST /internal/workspace/tasks`. Registration of
the `TASK-<number>`, interpreted scope, workspace session, and Telegram outbox
message is one database transaction. The caller must poll
`GET /internal/workspace/tasks/<TASK-ID>/acknowledgement` and must not begin
implementation until `may_start` is true. Repeated registration with identical
details is idempotent; reusing an ID with different details is rejected.

## Minimal-context session recovery

Write the agreed bounded state through authenticated
`PUT /internal/workspace/checkpoint`, then initialize each new session from
`GET /internal/workspace/checkpoint`. Treat `stale` as requiring confirmation
against the task/issue and deployment authorities; a corrupt checkpoint is
rejected with HTTP 409. Do not put transcripts, credentials, raw logs, or
attachments in checkpoint fields.

After a restart, verify the restored record in a separate process:

```sh
python3 -m commander.verify_checkpoint_restore --scope commander
```

The command fails for absent, stale, or corrupt state. `/readyz` reports the
startup canary and can enforce it when `COMMANDER_CHECKPOINT_REQUIRED=true`.
This recovery path does not replace the separate real Telegram acknowledgement
probe or live production verification.

Do not run the demo JSONL store concurrently from multiple processes.

Emergency stop and approval checks are policy gates in the domain service.
Telegram will be an authenticated transport adapter over the same command API;
it must not bypass those gates.

`TelegramControlPlane` is the transport-neutral command boundary. Configure
non-empty allowlists for both Telegram user IDs and chat IDs. Its caller must
deliver returned messages through the Bot API, acknowledge callback query IDs,
deduplicate Telegram update IDs, and keep the bot token out of Git.

The executable composition is in `docker-compose.commander.yml`. See
[`telegram-runtime.md`](telegram-runtime.md) for credentials, HTTPS activation,
operations, and the `/creative` command.
