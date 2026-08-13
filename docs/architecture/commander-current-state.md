# Commander current state

Status: active implementation handoff  
Updated: 2026-08-13  
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Completed milestone

The first generic learning-loop foundation is implemented in `commander/`.
It includes UUIDv7 IDs, append-only entities and relationships, explicit
experiment-state events, versioned policy gates, audit summaries, a selective
context broker, a replayable local JSONL adapter, and an Instagram creative
adapter.

`python3 -m commander.demo` demonstrates:

Hypothesis -> Creative -> Experiment -> MetricSet -> Observation -> Insight ->
Decision -> KnowledgeAssertion -> Next Task.

The PostgreSQL adapter in `commander/postgres_store.py` persists the generic
entity/edge model, maintains typed projections, and writes an outbox message in
the same transaction. Migrations 001 through 004 apply cleanly to PostgreSQL 16.

The Telegram adapter in `commander/telegram.py` authenticates
both user and chat allowlists and supports status, queue, policy inspection,
one-time experiment approval/rejection, reasoning summaries, emergency stop,
and resume. The FastAPI webhook, Telegram Bot API client, update deduplication,
outbox worker, health/readiness endpoints, image attachment download, and
deterministic 1080x1920 Story renderer are implemented. Instagram publishing
does not exist; generated images are returned for review.

## Last verification

From the repository root:

```text
python3 -m unittest discover -s tests/commander -v  # 13 passed; 3 runtime tests skip without optional dependencies
python3 -m commander.demo --output-dir .local/commander-demo  # passed
python3 -m compileall -q commander tests/commander  # passed
git diff --check  # passed
```

Dart and Flutter were unavailable on the VPS, so Flutter tests were not run.

The PostgreSQL migrations were also applied to a disposable `postgres:16-alpine`
container with `ON_ERROR_STOP=1`; all 10 tables and 20 entity enum values were
verified. The adapter transaction tests inject outbox failure and verify the
domain insert rolls back.

A real psycopg 3.2.9 integration run against a separate disposable PostgreSQL
16 container also completed the approval-driven experiment lifecycle. It
persisted 41 entities, 62 pending outbox messages, and the ordered experiment
states `running`, `completed`, and `evaluated`. No deployed PTW database was
accessed.

The complete dependency image runs all 16 tests. The actual local HTTP webhook
-> PostgreSQL -> renderer -> outbox path was exercised: it persisted 18
entities, queued one Telegram photo delivery, and produced a verified 1080x1920
PNG. Synthetic state was removed afterward.

An isolated Compose stack is installed and healthy on `127.0.0.1:8091` using
non-live placeholder Telegram settings. No webhook has been registered. Owner
activation steps are in `docs/operations/telegram-runtime.md`.

## Next milestone

After the owner supplies a BotFather token, allowlisted Telegram IDs, and a DNS
hostname, configure the HTTPS reverse proxy and register the webhook. Then run
a private end-to-end Telegram smoke test before adding Instagram publishing,
automated experiments, or spend.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
