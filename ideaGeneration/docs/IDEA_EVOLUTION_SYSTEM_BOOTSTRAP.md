# Idea Evolution system contract

Status: web-only v2
Updated: 2026-08-17

## Mission

The runtime resolves the one active mission. The clean seed is
`MISSION_20M_3Y`: build a remotely operated company with a plausible path to a
USD 20M sale or valuation within 36 months of activation. No runtime component
may hard-code an obsolete mission ID.

The evaluation rubric is:

- three-year USD 20M exit potential: 25;
- remote operability and autonomy: 25;
- distribution: 15;
- scalability/economics: 15;
- defensibility: 10;
- speed/capital efficiency: 10.

Criteria must total the 0–100 score exactly.

## State model

PostgreSQL is authoritative for missions, C01–C10 contexts and immutable
revisions, generations, ideas, evaluations, reports, submissions, guidance, and
executions. The active mission is selected by `is_active`; a partial unique
index prevents two active missions.

Reset seeds one mission, exactly ten active contexts, and one revision for each
context. It creates no generation, idea, evaluation, report, submission, or
execution. Generation 1 starts only after an explicit owner action in the web
UI.

## Generation contract

Every generation contains exactly ten ideas. Explore slots create independent
ideas; exploit slots preserve valid parent lineage. An evaluator returns one
entry for every supplied idea ID and no other IDs. Bounded provider recovery is
allowed, but completed generations and historical scores are immutable.

Owner Ideas may also enter the Idea Laval Engine before or alongside C01–C10
evolution. Laval does not replace generations: it expands persisted market
evidence, compresses it into opportunities, gates those through trend scores
and discoveries, then produces evidence-linked variants. The shared Owner
Gateway and Ideas screen are the normal control surface for both workflows.

LLM instructions and structured source values are English. Every owner-facing
generated field has the exact shape `{ "en": ..., "uk": ... }`; list values use
parallel arrays. Commander Web shows Ukrainian and lets the owner reveal the
English source. Raw logs and CLI output are not translated.

## Owner controls

Commander Web exposes manual generation count, queue and rankings, reports,
submissions, and versioned C01–C10 editing. Calls pass through the Firebase-
authenticated Owner Gateway to an internal token-authenticated idea API. The
browser never connects directly to PostgreSQL or an internal runtime.

Telegram is notification/emergency-only. `/stop` pauses generation at a safe
boundary and clears queued autonomous work; system resume exists only in the
web System view.

## Post handoff

An owner-selected idea may create one post or a ten-variant A01–A10 batch.
The handoff uses an immutable idea snapshot and idempotency key. Generic idea
learning remains independent of the Instagram adapter and post renderer.

## Recovery invariants

- Context and mission seeds are idempotent and never overwrite owner revisions.
- Runtime tables can be recreated without deleting database roles or volumes.
- A verified off-host backup is mandatory before production reset.
- Autopilot remains off after reset or resume.
- Generation completion, report creation, and batch handoff are restart-safe.
