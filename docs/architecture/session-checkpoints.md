# Commander session checkpoint contract

Status: canonical architecture contract  
Updated: 2026-08-14

## Decision

Commander persists a bounded resume checkpoint instead of transcripts. Each
append-only checkpoint contains only the agreed decisions, active tasks and
issues, deployment state, verification evidence, and next action needed to
continue work. It also records the producing workspace session, scope, schema
version, creation time, and a server-computed SHA-256 checksum.

The checkpoint is a recovery aid, not a second task authority. Task and issue
records, graph entities, Git revisions, deployment evidence, and Telegram
delivery rows retain their existing authority. Checkpoint data must be
secret-scrubbed and must refer to durable IDs rather than embedding credentials,
attachments, logs, or transcript text.

## Restore and canary

At API process construction Commander loads the latest `commander` checkpoint,
verifies its checksum, and evaluates its age. The startup result is `fresh`,
`stale`, `corrupt`, `absent`, or `error`; `/readyz` exposes that result. Set
`COMMANDER_CHECKPOINT_REQUIRED=true` to make any result other than `fresh`
block readiness. Absence is non-blocking by default so the first checkpoint can
be created without a bootstrap deadlock.

New Codex sessions restore with authenticated
`GET /internal/workspace/checkpoint`. They update the append-only stream with
`PUT /internal/workspace/checkpoint`; callers cannot supply their own checksum.
The default freshness window is 24 hours and can be changed with
`COMMANDER_CHECKPOINT_MAX_AGE_SECONDS`.

Checkpoint save and restore do not enqueue Telegram messages and do not alter
workspace task acknowledgement status. The established rule remains: work may
start only after the accepted task's Telegram acknowledgement is delivered,
and production completion still requires live deployment evidence rather than
a main-branch merge or a checkpoint claim.
