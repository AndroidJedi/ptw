# Commander current state

Status: web-only cutover implemented locally; production cutover pending
Updated: 2026-08-17
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Completed milestone

PTW is now a web-only Commander. The mobile-first React/Vite PWA contains
Overview, Ideas, Posts, Jobs, Docs/System, and the break-glass root terminal.
Firebase is used only for verified Google identity and App Check. The Owner
Gateway independently pins the one owner email and UID, exposes bounded
PostgreSQL read/write APIs, streams Codex Plan/Execute events, and bridges an
authenticated WSS connection to the root-only Unix-socket broker.

The active mission is `MISSION_20M_3Y`: create a remotely operated company with
a plausible path to a USD 20M sale or valuation within 36 months. Runtime logic
resolves the active mission instead of using a hard-coded mission constant. LLM
contracts are English-first and owner-facing generated idea fields contain
`{en, uk}`; the UI shows Ukrainian by default and can reveal the source.

Creative review supports pin, rectangle, and freehand annotations in normalized
coordinates, an area comment per annotation, overall rating/comment, and
predicted CTR. Reviews are append-only and bound to both Creative UUID and
Artifact digest. Corrections create a new review with `supersedes`; the original
HumanFeedback and WeightUpdate lineage is retained.

Telegram is reduced to notifications and owner-only `/help`, `/status`, and
`/stop`. Unsupported input returns the web link without creating domain work.
Emergency stop is durable in the platform database and fans out to idea and
creative runtimes; only the web UI can resume the complete system.

The confirmation-gated reset path recreates only the two `public` schemas and
clears the Commander asset volume plus three exact live directories. By the
owner's latest decision it has no backup prerequisite and is explicitly marked
irreversible. A disposable PostgreSQL 16 rehearsal verified clean reseeding and
the exact post-reset counts.

All legacy client source, platform shells, generated artifacts, manifests,
tooling, and active documentation have been removed. Roboto is owned by
`commander/assets/fonts` with its license. There is no compatibility or archived
client subsystem in the repository.

## Verification

- React TypeScript, Vitest accessibility test, and production Vite build pass.
- Firebase blocking-functions TypeScript check passes.
- Commander built-image suite: 57 tests pass; five intentionally retired
  Telegram-flow tests are skipped.
- PostgreSQL-backed Commander/idea suite: 52 pass and five retired Telegram
  tests skip against disposable PostgreSQL 16.
- Owner Gateway built-image suite passes exact-owner negative/positive
  authentication tests and confirmation-only reset/root-operation gates.
- Independent platform checkout: 51/51 tests pass.
- Two-database reset rehearsal passes with the required clean checkpoint:
  one mission, ten idea contexts/revisions, ten post contexts/revisions, and no
  domain runtime rows.

## Production work remaining

1. Enable billing/Identity Platform, Google Sign-In, blocking functions, and
   reCAPTCHA Enterprise App Check in the existing Firebase project; pin the
   created owner UID and deploy Hosting.
2. Deploy the reviewed control plane and the independent platform change,
   install the root broker service, and perform the confirmation-gated reset.
3. Run owner login, Plan/Execute, root `id`/`pwd`, manual Generation 1, single
   and ten-variant review, Telegram emergency controls, restart persistence,
   and reset acceptance checks.

## Operational warning

The GitHub working tree and `/opt/ptw/platform` have unrelated histories. Do
not merge or overwrite one with the other.
