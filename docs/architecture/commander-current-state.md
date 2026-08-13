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
the same transaction. Migrations 001 through 006 apply cleanly to PostgreSQL 16.

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
python3 -m unittest discover -s tests/commander -v  # 18 passed; 5 runtime tests skip without optional dependencies
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

The complete dependency image runs all 23 tests. The actual local HTTP webhook
-> PostgreSQL -> renderer -> outbox path was exercised: it persisted 18
entities, queued one Telegram photo delivery, and produced a verified 1080x1920
PNG. Synthetic state was removed afterward.

An isolated Compose stack is installed and healthy on `127.0.0.1:8091`. It
reuses the established `@ptw_commander_bot` credential and allowlist from the
root-owned `/opt/ptw/platform/.env`; no token is copied into Git. The existing
long poller remains the only update consumer and forwards `/creative` over the
shared internal Docker network. No webhook is registered or required.

The forwarding change is committed in the unrelated deployment checkout as
local commit `0db9522`. That checkout has no configured remote, so the durable
integration contract is also documented here and in
`docs/operations/telegram-runtime.md`.

The same established bot now accepts `/task <free-form request>` for fixes,
implementation, reviews, or changes. It maps to the existing specification-
driven engineering job type and supports screenshots/images supplied with the
command as an attachment caption. The deployed change is local commit
`c21febf`; `/engineer repo=ptw <task>` remains compatible.

The PostgreSQL knowledge graph is implemented as UUIDv7 entities plus typed,
foreign-key-protected relationship edges. `ResearchKnowledgeService` now records
provenanced research findings and creates a proposed hypothesis derived from
one or more source IDs. Research findings do not become accepted knowledge
without experiment, observation, insight, and decision stages.

Minimum-cost recovery is installed: daily logical PostgreSQL and asset backups,
policy/Git revision capture, SHA-256 verification, 14-day local retention, and
an explicit restore script. Backup `20260813T055504Z` was checksum-verified and
restored successfully into disposable PostgreSQL 16. The current running graph
is structurally complete but contains zero entities until real research or
creative activity is recorded. Offsite backup copying remains an owner/provider
dependency.

Creative feedback is now an append-only learning flow. Every returned Telegram
image asks the owner to reply `/feedback <1-5> [comment]`. Telegram delivery IDs
resolve internally to Creative UUIDs; feedback evaluates the Creative UUID and
versioned WeightUpdate UUIDs adjust each contained Component UUID. Identical
components are reused by ID, making weights cumulative and available for
deterministic future ranking. The existing poller forwards feedback in local
deployment commit `78f4dcd`.

Telegram graph inspection is implemented: `/graph` shows counts and recent
IDs, `/graph hypotheses` shows Hypothesis-to-Source UUID lineage, `/graph
weights` shows current component-weight projections, and `/graph creative
<uuid>` reconstructs components, feedback, and weight-update IDs. The existing
poller forwards graph requests in local deployment commit `d28b7d1`.

`/research creative <topic>` is routed by the established poller and bounded to the
`creative_ideation` research type. It persists provider findings as Source
UUIDs and proposed hypotheses with `derived_from` edges. `/creative from
<hypothesis-uuid>` consumes the selected graph hypothesis. The poller change is
local deployment commit `79b864f`. Live provider execution is intentionally
disabled until `OPENAI_API_KEY` is supplied outside Git.
The bot's `/help` output includes this workflow as of local deployment commit
`175536b`.

## Next milestone

Configure the research-provider credential, run the first real research ->
hypothesis -> creative loop, then extend generation so learned component weights
influence variant selection. Also choose a low-cost offsite backup destination
before production knowledge accumulates.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
