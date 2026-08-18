# Commander current state

Status: web-only Commander and Idea Laval implemented locally; production cutover pending
Updated: 2026-08-18
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

The Ideas view now includes the Idea Laval evidence engine alongside Idea
Evolution. Laval persists 16 inspectable/restartable stages from Owner Capture
through Final Shortlist, localized search work for configurable countries,
global competitor deduplication, evidence and complaint clusters, Opportunity
Matrix rows, separate Trend Scores and Trend Discoveries, bounded synthesis,
21 operator-driven variants, clustering, independent evaluation, overrides,
costs, and provenance. The Owner Gateway is the only normal web instruction
channel; its bounded proxy never gives the browser direct database access.

Laval's live research path is pluggable. DataForSEO implements localized organic
SERPs, website collection uses public HTTP pages, and the restricted Google
Trends API is represented by an owner-configured bridge. Deterministic fixture
providers remain the safe default and are visibly marked. Live evidence passes
through `ResearchKnowledgeService`; finalists become proposed Hypotheses with
`derived_from` edges to permanent Source UUIDs.

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

- React TypeScript, three Vitest tests, the production Vite build, and two
  mobile/desktop Playwright checks pass.
- Firebase blocking-functions TypeScript check passes.
- Commander/Idea/Laval suite in the Commander image against disposable
  PostgreSQL 16: 72 tests pass; seven intentionally unavailable/retired tests
  skip.
- Focused Laval PostgreSQL suite: 14 tests pass, including the 16-stage fixture,
  exact 21-variant provenance, partial country failure, retry/cache behavior,
  manual approval, country rerun/staleness, overrides, authenticated API, and
  export.
- Owner Gateway built-image suite: 10 tests pass, including exact-owner Laval
  proxying and confirmation-only reset/root-operation gates.
- Fresh Idea, Commander, and Owner Gateway images build and import their runtime
  entrypoints; the Idea image exposes the `lav` CLI.
- Commander deterministic demo and `git diff --check` pass.
- Independent platform checkout: 51/51 tests pass.
- Two-database reset rehearsal passes with the required clean checkpoint:
  one mission, ten idea contexts/revisions, ten post contexts/revisions, and no
  domain runtime rows.

## Production work remaining

1. Add the live Laval provider credentials/access (or explicitly accept fixture
   mode), rebuild the Idea API, Commander API, Owner Gateway, and web image, and
   run the Laval production acceptance checklist.
2. Enable billing/Identity Platform, Google Sign-In, blocking functions, and
   reCAPTCHA Enterprise App Check in the existing Firebase project; pin the
   created owner UID and deploy Hosting.
3. Deploy the reviewed control plane and the independent platform change,
   install the root broker service, and perform the confirmation-gated reset.
4. Run owner login, Plan/Execute, root `id`/`pwd`, manual Generation 1, single
   and ten-variant review, Telegram emergency controls, restart persistence,
   and reset acceptance checks.

## Operational warning

The GitHub working tree and `/opt/ptw/platform` have unrelated histories. Do
not merge or overwrite one with the other.
