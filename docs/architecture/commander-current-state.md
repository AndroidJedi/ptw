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
the same transaction. Migrations 001 and 002 apply cleanly to PostgreSQL 16.

The transport-neutral Telegram adapter in `commander/telegram.py` authenticates
both user and chat allowlists and supports status, queue, policy inspection,
one-time experiment approval/rejection, reasoning summaries, emergency stop,
and resume. A webhook/polling process and outbound Telegram HTTP client do not
exist yet. Instagram network integration does not exist.

## Last verification

From the repository root:

```text
python3 -m unittest discover -s tests/commander -v  # 12 passed
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

## Next milestone

Add an executable Commander API/worker composition: environment-based secret
loading, a small Telegram webhook endpoint, idempotent update receipt, an
outbox dispatcher, health/readiness endpoints, and integration tests against a
disposable PostgreSQL database. Do not enable a real Telegram webhook until the
owner supplies credentials and an HTTPS deployment target.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
