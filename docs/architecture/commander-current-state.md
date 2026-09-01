# Commander current state

Updated: 2026-09-01
Branch: `codex/web-only-commander`
Deployment: not authorized; local checkout only

## Current milestone

The Result lifecycle is now owner-reviewed and five-Creative-first. The
automatic evaluator subsystem, subjective scoring/ranking, improvement actions,
eligibility decisions, reduced analysis artifacts, lesson proposals, and
automatic final selection have been removed from runtime contracts, persistence,
provider modes, APIs, Owner Console, skills, schema verification, and canonical
documentation.

Initial and Regenerate-all runs make exactly five isolated transient CandidateV2
calls. Tune makes one call, replaces the selected slot, and carries four Creative
UUIDs unchanged. Server integrity checks remain fail-closed for protected copy,
approved Brief language, claims, media authority, recipe/render identity,
clipping/collision/layout safety, and five distinct document/render/media
identities. A successful run stops at `awaiting_review` with exactly five
reviewable Creative UUIDs.

The Owner Console presents a five-card authenticated review grid. Selecting a
card enables Approve or Tune; Regenerate all applies to the set. Approved runs
show a native post and authenticated deterministic export. The learning panel
shows only ID-explicit owner actions and active Project rules. There are no
subjective metrics or hidden selection surfaces. Social posts does not contain
the former loopback asset/Pexels and run/snapshot evidence panel, and its create
form does not explain backend integrity checks or the absence of an evaluator.

Approve, Regenerate all, and Tune are request-UUID idempotent and reject stale
or concurrent actions. A parent remains actionable until a child successfully
reaches `awaiting_review`; failed/terminated children mark their action failed.
Owner feedback, WeightUpdates, outcomes, learning rules/snapshots, and graph
lineage append immediately. Project/strategy/output-profile scope is enforced,
and Product Brief generation remains isolated from Result learning.

Review notification uses a typed Validation → Commander relay. The delivery
receipt is persisted before send. Definite failures retry boundedly, ambiguous
sends do not auto-repeat, and the web review remains available on failure with
manual retry. Telegram remains notifications plus `/help`, `/status`, `/stop`;
it accepts no owner-review mutation. The loopback app does not require or fake
this production relay: without explicit relay configuration it records
`not_configured` and still completes the authenticated five-card web review.

The local Universal profile preserves the prior saved-Studio, language, copy
style, and Pexels requirements: exactly three fresh distinct real-photo
background directions, a screened Pexels physical-object sticker, one texture,
one solid direction, and full-resolution deterministic diversity/layout audits.
Its file authority is `.local/owner-experiments`; local terminate applies only
to active runs.

## Verification status

Passed locally on 2026-09-01:

- Validation: 99 tests ran; 96 passed and the three production-lifecycle tests
  were skipped because no disposable PostgreSQL target is configured.
- Owner Gateway: 5 tests passed.
- Commander: 9 tests passed in the project virtualenv. The required system
  Python invocation also passed its six dependency-free tests and skipped the
  three FastAPI tests; the virtualenv invocation passed all nine.
- Commander web: 35 unit tests, the production TypeScript/Vite build, and all
  21 Playwright desktop/mobile/WebKit tests passed.
- The 40-example content corpus, 21 post-copy anchors, deterministic Studio
  template/render audit, canonical skill verification, Python compilation,
  Commander demo, and `git diff --check` passed.

The Docker daemon is unavailable, so the disposable PostgreSQL schema verifier
and the built-image FastAPI/Pillow test command could not run. No production
database, external provider, live Telegram canary, Firebase release, or
independent platform repository was touched.

The confirmation-gated local reset completed after verification. It removed
6,156 entries from `.local/owner-experiments`, left that authority empty, and a
content/permission/symlink manifest proved all 10,794 other `.local` paths were
unchanged.

## Rollout boundary

A future rollout requires an explicitly authorized clean Commander schema reset;
old lifecycle data is intentionally not migrated. Before that rollout the
unrelated platform bridge must independently advertise only Product Brief,
Brief revision, and Candidate generation JSON modes. Live Telegram capability
cannot be claimed until authorization/routing/provider delivery, persistence,
restart, ambiguity, definite failure, and user-facing retry paths pass in the
deployed environment.

## Next work

Do not deploy or reset production without a separately authorized rollout. At
that time, start with the disposable PostgreSQL/schema and built-image checks,
then follow the clean-reset and live notification canary boundaries above.
