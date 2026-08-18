# Commander current state

Status: web-only Commander and Idea Laval deployed; owner UID binding and authenticated acceptance pending
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

Production cutover is live on the existing VPS. Firebase Hosting serves the
mobile web console at `https://provethemwrong-86123.firebaseapp.com`, with the
parallel `web.app` host forwarding before Auth initialization, and
`https://commander.proove-them-wrong.com` terminates TLS in the independent
platform Caddy service before proxying to the Owner Gateway. Commander, Idea,
and Owner Gateway remain loopback-only on their host-published ports. The
root-only broker is installed as a systemd service and exposes its Unix socket
only to the gateway group. Existing Idea data was preserved by additive
migration; no production reset was run.

Firebase Identity Platform, the Google provider, verified-owner blocking
functions, and reCAPTCHA Enterprise App Check are enabled. The gateway service
account is stored outside Git with owner/gateway-group read permissions. The
owner email is allowlisted, but the UID remains deliberately unbound until the
first successful Google login creates the authoritative Firebase user.

## Verification

- React TypeScript, three Vitest tests, and the production Vite build pass.
  Production browser checks confirm `web.app` forwards before Auth starts,
  iPhone uses a same-tab Google flow with the first-party `firebaseapp.com`
  callback, desktop retains the popup flow, and App Check returns HTTP 200.
- Firebase blocking-functions TypeScript check passes. The deployed Gen 2
  functions use a runtime that accepts the configured audience, and both
  Identity Platform triggers resolve to their matching `run.app` services; this
  removes the audience-validation failure that surfaced as an Identity Toolkit
  HTTP 503 during Google sign-in.
- Firebase Hosting serves service-worker cache `ptw-shell-v7`. A fresh live
  browser profile installed and controlled the worker, deleted and repopulated
  its document and asset cache, and reported no consumed-body `Response.clone()`
  errors. Live desktop and iPhone-emulated checks both reached the Google account
  chooser at `accounts.google.com`.
- Commander/Idea/Laval suite in the Commander image against disposable
  PostgreSQL 16: 72 tests pass; seven intentionally unavailable/retired tests
  skip.
- Focused Laval PostgreSQL suite: 14 tests pass, including the 16-stage fixture,
  exact 21-variant provenance, partial country failure, retry/cache behavior,
  manual approval, country rerun/staleness, overrides, authenticated API, and
  export.
- Owner Gateway built-image suite: 10 tests pass, including exact-owner Laval
  proxying and confirmation-only reset/root-operation gates.
- Production Owner Gateway built-image suite: 10/10 tests pass on the VPS.
- Fresh Idea, Commander, and Owner Gateway images build and import their runtime
  entrypoints; the Idea image exposes the `lav` CLI.
- Commander deterministic demo and `git diff --check` pass.
- Independent platform checkout: 51/51 tests pass.
- Two-database reset rehearsal passes with the required clean checkpoint:
  one mission, ten idea contexts/revisions, ten post contexts/revisions, and no
  domain runtime rows.
- Firebase Hosting returns the PTW Commander shell with HTTP 200. The public
  gateway health endpoint returns `{"status":"ok"}`, protected APIs reject
  missing bearer credentials with HTTP 401, and the production-origin CORS
  preflight allows only the required methods and headers.
- Deployed Commander and Owner Gateway health checks pass; the Idea service
  reports the active mission, ten preserved generations, and no active Laval
  run. Root broker and Caddy restart checks pass.

## Production work remaining

1. Complete the first allowlisted Google login, pin the resulting Firebase UID
   in the VPS-only gateway environment, recreate the gateway, and run the
   authenticated browser/API acceptance checks.
2. Add DataForSEO credentials and restricted Google Trends bridge access when
   available, switch Laval away from visibly marked deterministic fixture mode,
   and run the live-provider production acceptance checklist. Fixture evidence
   must not enter the permanent Commander research graph.
3. Run owner Plan/Execute, root `id`/`pwd`, manual Generation 1, single- and
   ten-variant review, Telegram emergency controls, and restart-persistence
   acceptance. Do not claim Telegram/provider readiness before these pass.
4. Exercise the production reset only after the owner supplies its exact web
   confirmation. The reset is irreversible and was intentionally not invoked
   during deployment.

## Operational warning

The GitHub working tree and `/opt/ptw/platform` have unrelated histories. Do
not merge or overwrite one with the other.
