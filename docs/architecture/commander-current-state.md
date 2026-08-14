# Commander current state

Status: active implementation handoff  
Updated: 2026-08-14
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
python3 -m unittest discover -s tests/commander -v  # 19 passed, 8 runtime dependency skips
python3 -m commander.demo --output-dir .local/commander-demo  # passed
python3 -m compileall -q commander tests/commander  # passed
git diff --check  # passed
```

Docker was unavailable in the isolated job workspace, and a disposable runtime
dependency install was blocked by host disk exhaustion, so the FastAPI/Pillow
tests could not be exercised there. Dart and Flutter were unavailable on the
VPS, so Flutter tests were not run.

The PostgreSQL migrations were also applied to a disposable `postgres:16-alpine`
container with `ON_ERROR_STOP=1`; all 10 tables and 20 entity enum values were
verified. The adapter transaction tests inject outbox failure and verify the
domain insert rolls back.

A real psycopg 3.2.9 integration run against a separate disposable PostgreSQL
16 container also completed the approval-driven experiment lifecycle. It
persisted 41 entities, 62 pending outbox messages, and the ordered experiment
states `running`, `completed`, and `evaluated`. No deployed PTW database was
accessed.

The complete dependency environment runs all 25 tests. The actual local HTTP webhook
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

Reply feedback also recovers and validates the Creative UUID from Commander's
generated photo caption when an older or missed Telegram delivery-link row is
absent. The delivery table remains the primary lookup.

Telegram graph inspection is implemented: `/graph` shows counts and recent
IDs, `/graph hypotheses` shows Hypothesis-to-Source UUID lineage, `/graph
weights` shows current component-weight projections, and `/graph creative
<uuid>` reconstructs components, feedback, and weight-update IDs. The existing
poller forwards graph requests in local deployment commit `d28b7d1`.

`/research creative <topic>` is routed by the established poller and bounded to the
`creative_ideation` research type. It persists provider findings as Source
UUIDs and proposed hypotheses with `derived_from` edges. `/creative from
<hypothesis-uuid>` consumes the selected graph hypothesis. The poller change is
local deployment commit `79b864f`. Live provider execution uses the existing
authenticated VPS Codex runtime; an API key is not required.
The bot's `/help` output includes this workflow as of local deployment commit
`175536b`.

The owner-facing `/task` pipeline now acknowledges each accepted request
immediately with the exact interpreted task, job ID, execution state, and
`/cancel <job-id>` instruction. Cancellation removes queued jobs or terminates
an active Codex child process. The worker's Codex runtime home is writable and
its authenticated executor was verified with a real shell call; this corrects
the earlier read-only runtime failure that caused every engineering task to
fail before execution. Creative bridge HTTP 4xx responses now preserve their
actionable validation message, so malformed `/feedback` input is no longer
misreported as creative-service unavailability. These changes are deployed in
the unrelated platform checkout as local commit `6365dce`.

The engineering control plane now has a durable task/issue recovery contract.
Blocking failures receive `ISSUE-<id>` records and append-only sanitized logs;
Telegram reports the block, automatic resolution, parent-task resume, or final
unresolved state. `/inspect TASK-<id>|ISSUE-<id>` retrieves bounded state by ID,
and a host-side JSON exporter can dump full or ID-scoped state for another
agent. Policy v2 authorizes validated pull-request merges to `main`, records the
rollback and resulting revisions, and leaves direct main pushes forbidden.

Creative research and generation now enter that task contract at the existing
poller boundary. They acknowledge a numeric `TASK-<id>` before provider work,
propagate it through the internal creative bridge, prefix the final Telegram
result with the same ID, and retain the structured bridge result. Transient
bridge failures create an issue, report it, retry once, and record either resume
or unresolved failure. This corrects the lifecycle bypass recorded as
`TASK-43` / `ISSUE-2` without duplicating the six research sources or five
hypotheses already stored by the successful request.

`/creative hook` is an explicit text-only mode. It returns a challenge hook as
a Telegram message and does not render or enqueue a Story image; other
`/creative ...` requests retain the existing image-generation workflow.

Creative delivery is non-repeating. Text hooks persist as Creative entities
with the selected research Hypothesis UUID, base hook, delivered hook, and
variant index. Selection prefers the best-matching least-used hypothesis and
uses versioned copy transformations after the candidate pool is exhausted.
Repeated rendered requests also advance a variant index and change the hook;
identical Telegram update IDs remain idempotent and do not create variants.

Text-hook delivery now has the same convenient learning loop as image delivery:
the returned message asks for a `/feedback 1-5 [comment]` reply, its Telegram
message ID resolves to the permanent Creative UUID, and the Creative contains a
reusable hook component that receives an append-only WeightUpdate. The embedded
Creative UUID remains a validated fallback if a delivery-link row is missed.

## Next milestone

Configure the research-provider credential, run the first real research ->
hypothesis -> creative loop, then extend generation so learned component weights
influence variant selection. Also choose a low-cost offsite backup destination
before production knowledge accumulates.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
