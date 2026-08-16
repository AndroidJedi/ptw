# Commander current state

Status: ad estimation implementation complete; production verification pending
Updated: 2026-08-16
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Completed milestone

The ten-context ad image estimation loop is implemented by reusing Commander's
generic graph, outbox, feedback weights, artifact storage, and recovery
structure. Idea Evolution validates `/ads from <idea-id>`, exposes a
**Generate 10 ads** action on `/idea`, and sends an immutable idea snapshot
through an authenticated, idempotent bridge. A01-A10 each create one
AdCreativeSpec, high-quality image, Hypothesis, Creative, reusable components,
and checksummed Artifact. Generation must persist all ten 1080×1350 finals
before serialized Telegram review begins.

Owner `/estimate` replies persist predicted link CTR, rating, and comment as
HumanFeedback before the producing context makes its one multimodal conclusion.
Only after that Insight commits does the next image enter the outbox. Completion
requires ten images, estimates, and conclusions; the final summary ranks by
predicted CTR and then rating. Immutable analytics imports calculate actual
link CTR and compare it with the original estimate. Migration 009 adds the
versioned contexts and durable batch/slot/execution/import projections. A
dedicated `commander-ad-worker` prevents provider latency from blocking the
existing Telegram outbox worker.

The canonical workflow is
[`ad-image-estimation-loop.md`](ad-image-estimation-loop.md).

## Previous completed milestone

Owner idea injection now uses append-only replacement generations. Each queued
owner idea replaces the lowest-scored candidate from the latest completed batch
in the next generation; the surviving candidates are retained with explicit
parent lineage and the completed source batch is never rewritten. Telegram
supports durable multi-part owner-idea drafts through `/idea_done`, and `/run`
received during active work extends the persisted run series instead of being
silently discarded.

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
the same transaction. Migrations 001 through 009 apply cleanly to PostgreSQL 16.

The Telegram adapter in `commander/telegram.py` authenticates
both user and chat allowlists and supports status, queue, policy inspection,
one-time experiment approval/rejection, reasoning summaries, emergency stop,
and resume. The FastAPI webhook, Telegram Bot API client, update deduplication,
outbox worker, health/readiness endpoints, image attachment download, and
deterministic 1080x1350 Instagram feed-post renderer are implemented.

## Last verification

From the repository root:

```text
python3 -m unittest discover -s tests/commander -v  # local dependency/database skips expected
python3 -m commander.demo --output-dir .local/commander-demo  # passed
python3 -m compileall -q commander tests/commander  # passed
git diff --check  # passed
```

The built Commander image passes 55 tests with five expected Idea Evolution
database skips, including the deterministic
ten-image loop, strict serialized review, feedback-before-conclusion ordering,
same-context ownership, bounded recovery, context snapshots, model/dimension
guards, analytics idempotency, and Telegram reply resolution. Migration 009 and
the PostgreSQL repository restart path pass against disposable PostgreSQL 16.
The local machine has no `/opt/ptw/platform` checkout or bot credentials, so a
real Telegram/provider cycle and production restart have not been claimed.

The complete idea-generation image also ran the repository suite with 49 tests
passing and 13 expected skips. A disposable PostgreSQL 16 integration run
passed all 14 database-backed idea-generation tests, including owner
replacement, draft joining, active-run extension, context persistence, API
authentication, and Telegram-update deduplication. The unrelated deployment
platform ran all 57 of its tests in its built worker image.

Production deployment was verified on 2026-08-16. A checksum-verified backup is
stored at `/opt/ptw/backups/idea-generation-20260816T093300Z`. The live API was
built from repository commit `449b4f9`, the old idea-generation poller is
stopped, and the established Commander process remains the only Telegram
long-poller. Its internal route returned a real owner `/status` message, invalid
bridge authentication returned HTTP 403, and an authenticated structured-model
probe returned a valid normalized idea. The idea API and Commander API/worker
all passed health checks after restart.

The production database retained four completed generations, 40 ideas, 400
evaluations, 10 active contexts, no running executions, autopilot off, and a
zero-length run queue. Owner submission #1 was safely reconstructed from the
two Telegram events and is pending at 7,527 characters. Starting G5 will replace
G4 idea #35, `ScamShield Network` (69.30), and retain the other nine G4 ideas as
new lineage-linked rows; G4 itself remains immutable.

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
entities, queued one Telegram photo delivery, and produced a verified PNG.
Synthetic state was removed afterward.

An isolated Compose stack is installed and healthy on `127.0.0.1:8091`. It
reuses the established `@ptw_commander_bot` credential and allowlist from the
root-owned `/opt/ptw/platform/.env`; no token is copied into Git. The existing
long poller remains the only update consumer and forwards creative and
idea-evolution commands over the shared internal Docker network. No webhook is
registered or required.

The current forwarding and structured-model integration is committed in the
unrelated deployment checkout as local commit `503074c`. That runtime history
must remain separate from this GitHub repository; the durable integration
contract is also documented here and in `docs/operations/telegram-runtime.md`.

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

Image creative delivery now produces a 1080x1350 Instagram feed post. Requests
without an attached photo receive composed branded artwork rather than the old
gradient stub; attached photos retain their fitted, darkened treatment.

Codex workspace task acceptance now has a repository-owned durable boundary.
Commander atomically persists the external `TASK-<number>`, interpreted scope,
workspace session and Telegram outbox item. Execution is gated on a status
response backed by Telegram's returned message ID, and a post-restart probe is
provided. Migration 007 adds the durable projection. Live post-restart delivery
is not yet verified in this isolated workspace because the deployment checkout,
runtime database, and established bot environment are unavailable; the reboot
regression therefore remains operationally open.

Commander/Codex sessions now have an append-only minimal-context checkpoint.
It stores agreed decisions, active task/issue references, deployment state,
verification evidence, and the next action without transcript replay. Migration
008 adds the durable stream; API startup automatically restores and checks the
latest checkpoint for SHA-256 integrity and freshness, readiness exposes the
canary, and an authenticated workspace endpoint initializes new sessions. A
separate-process verification command is provided. Checkpoint writes do not
change Telegram acknowledgement or production-completion gates.

## Next milestone

Deploy the three Commander services and updated Idea Evolution bridge from a
reviewed revision, update the unrelated established poller's routing, configure
the existing runtime's OpenAI credential, and run one real owner-only batch.
Verify help/button routing, all ten GPT Image 2 artifacts before first delivery,
one `/estimate` reply and producing-context conclusion per image, graph IDs,
ranking, restart continuation, and actionable provider failure before marking
the Telegram capability active.

## Prior next milestone

Merge the owner-replacement branch through a pull request, then let the owner
inspect `/idea_queue` and send `/run` to start G5. Verify that submission #1 is
recorded as replacing idea #35, G5 completes with exactly 10 ideas and 100 new
evaluations, the human idea appears in `/ranking`, and `/report G5` names the
replacement. Keep autopilot off until this first real replacement generation
has been reviewed.

## Earlier next milestone

Configure the research-provider credential, run the first real research ->
hypothesis -> creative loop, then extend generation so learned component weights
influence variant selection. Also choose a low-cost offsite backup destination
before production knowledge accumulates.

## Operational warning

The GitHub repository and the existing `/opt/ptw/platform` deployment have
unrelated Git histories. Never merge or overwrite one with the other without a
separate migration and provenance review.
