# Commander current state

Status: Idea Laval v3 deployed and verified; saved live run awaits owner resume
Updated: 2026-08-19
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Completed milestone

PTW is now a web-only Commander. The mobile-first React/Vite PWA contains
Overview, Ideas, Jobs, Docs/System, and the break-glass root terminal.
Firebase is used only for verified Google identity and App Check. The Owner
Gateway independently pins the one owner email and UID, exposes bounded
PostgreSQL read/write APIs, streams Codex Plan/Execute events, and bridges an
authenticated WSS connection to the root-only Unix-socket broker.

The active mission is `MISSION_20M_3Y`: create a remotely operated company with
a plausible path to a USD 20M sale or valuation within 36 months. Runtime logic
resolves the active mission instead of using a hard-coded mission constant. LLM
contracts are English-first and owner-facing generated idea fields contain
`{en, uk}`; the UI shows Ukrainian by default and can reveal the source.

The production PWA defaults API and WebSocket traffic to the Commander gateway
even when no build-time override is supplied. Firebase Hosting therefore cannot
silently rewrite API requests to the application shell. Successful API calls
also require a JSON content type, and Hosting uses popup-compatible COOP for the
desktop Google sign-in flow.

The public reCAPTCHA Enterprise site key now ships with the Firebase browser
configuration instead of depending on an operator shell variable. Production
build verification checks the compiled bundle for the API origin, App Check
header, and site key, while the Hosting predeploy hook always rebuilds before
upload. This closes the regression where a valid Firebase session reached
Overview without an App Check header.

PTW-specific Codex skills are now canonical repository content shared by the
desktop agent and mounted into both CLI-agent services. Incident fixes must
update the applicable skill in the same commit; a verifier prevents desktop
links or container mounts from drifting.

Idea Laval now owns an explicit Compose project separate from Commander. This
closes the production failure where the Idea container was absent, shared-network
DNS had no `ptw-idea-api` target, and the authenticated Ideas tab received HTTP
503. The isolated service explicitly joins Commander's database network for
`commander-db` DNS and the platform backend for its gateway alias. A bundled
incident audit verifies both containers, networks, loopback health, and the
token-protected gateway-to-Idea run-list call.

The Ideas view now exposes only the Idea Laval evidence engine. Legacy C01-C10
generation controls, seeded rankings, contexts, API routes, runtime engine,
Telegram mutation controller, and source/docs are removed. An empty run list is
the authoritative state until the owner creates a Laval idea. Laval persists 16
inspectable/restartable stages from Owner Capture
through Final Shortlist, localized search work for configurable countries,
global competitor deduplication, evidence and complaint clusters, Opportunity
Matrix rows, deterministic Market Signals, bounded synthesis,
24 variants across eight operators including `BEHAVIOR_FIRST`, clustering,
fresh independent evaluation, overrides, costs, and provenance. The Owner Gateway is the only normal web instruction
channel; its bounded proxy never gives the browser direct database access.

Laval's live research path is pluggable. DataForSEO implements localized organic
SERPs, website collection uses public HTTP pages, and the restricted Google
Trends API is an optional supplemental source represented by an owner-configured
bridge; its absence does not block Market Signals or finalists. Deterministic fixture
providers remain the safe default and are visibly marked. Live evidence passes
through `ResearchKnowledgeService`; finalists become proposed Hypotheses with
`derived_from` edges to permanent Source UUIDs.

Market Signals v2 keeps the pipeline at 16 stages by replacing the three Trends
stages with Plan, Collection, and Gate. `market-signal-v1` stores the exact
formula, six code-computed components, raw counters, data availability, and
deduplicated evidence IDs; missing data contributes zero and no coverage
multiplier exists. An LLM can only classify supplied evidence IDs as relevant
or not relevant. Each language-stage call has a distinct fresh session and an
append-only audit containing context/schema hashes, prompt version, model, and
truthful success/fallback/failed state.

The independent platform bridge defect is fixed in source: it previously
rejected every `laval_*` mode, ignored the caller's schema, and therefore made
Laval silently use deterministic fallback while documentation incorrectly
credited Codex. The corrected worker allowlists Laval modes and invokes a new
`codex exec --ephemeral --sandbox read-only --output-schema … -` for every job;
it never resumes a conversation or uses the dangerous sandbox bypass.
Production uses the audited `codex-cli-default` sentinel, which omits an
explicit `--model` so ChatGPT-authenticated Codex selects its supported default.

Laval manual corrections are now contextual instead of exposing a generic
database form on every stage. Only Competitor Selection, Opportunity Matrix,
and Trend Gate offer corrections. Their current selected/enabled rows arrive as
human-readable choices, while the stable target UUID is submitted internally.
The owner must provide a reason; the Firebase actor and reason remain appended
to the audit log, and the precise downstream boundary becomes stale. This
change is deployed to the production PWA/API.

Creative production and review are retired operationally on the 1 GB profile.
Their source, migrations, immutable artifacts, append-only reviews, UUID
lineage, and historical database rows remain intact. The Posts navigation and
pending-review metric are absent, while cached clients receive HTTP 410 from
post, creative-review, artifact, ad-batch, workspace-acknowledgement, and
status-notification endpoints.

Telegram is reduced to owner-only `/help`, `/status`, and `/stop`; proactive
outbound notifications are retired. The established platform long poller can
return those bounded emergency responses directly, while Commander no longer
enqueues them to its outbox. Unsupported input returns the web link without
creating domain work.
Emergency stop is durable in the platform database and fans out to idea and
creative runtimes; only the web UI can resume the complete system.

The 1 GB runtime profile disables both Commander polling workers by Compose
profile, cancels unpublished Telegram outbox rows without deleting them, and
never constructs Laval notification producers or imports the Pillow/ad runtime
when creative mode is disabled. PostgreSQL connections have five-second
deadlines, and Idea Laval reuses one serialized process connection instead of
forking a PostgreSQL backend for every repository call. Browser API requests
have a 15-second overload deadline with a Retry action. Laval and Codex
Plan/Execute starts are mutually exclusive and a
conflict reports the active operation with HTTP 409. A single Laval process may
also run only one pipeline thread at a time.

Production releases are built for Linux/amd64 off-host. The release publisher
uses one SSH connection and one input stream; the VPS deployment holds
`/run/lock/ptw-maintenance.lock` from Git reconciliation through image loading,
migrations, one-service-at-a-time recreation, dependency checks, and a
30-second activity sample. No production build, background job, parallel image
load, or multi-service Compose start is permitted. The script creates a
persistent 2 GB `/swapfile` only with at least 4 GB free and applies the bounded
PostgreSQL memory profile to both local database instances.

The confirmation-gated reset path recreates only the two `public` schemas and
clears the Commander asset volume plus three exact live directories. By the
owner's latest decision it has no backup prerequisite and is explicitly marked
irreversible. A disposable PostgreSQL 16 rehearsal verified clean reseeding and
the exact post-reset counts.

The independent platform now owns numbered migration
`011_platform_control.sql`, which creates and seeds the single durable emergency
stop row consumed by the Owner Gateway. Owner read models use explicit fixed SQL
clauses for optional post-review filters instead of untyped nullable parameters.

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
only to the gateway group. Numbered migration `005_retire_idea_evolution.sql`
purges the retired idea records while preserving `laval_*` data and the active
mission; the broad production reset was not run.

Firebase Identity Platform, the Google provider, verified-owner blocking
functions, and reCAPTCHA Enterprise App Check are enabled. The gateway service
account is stored outside Git with owner/gateway-group read permissions. The
owner email is allowlisted and the gateway now pins the UID of its authoritative
verified Google Firebase user.

## Verification

- React TypeScript, thirteen Vitest tests, six Playwright browser tests across
  desktop Chrome, Pixel emulation, and iPhone WebKit, and the production Vite
  build pass. Regression coverage clicks Laval creation, all 16 stage cards,
  rerun/approval/navigation, provider gating, and authenticated export fallback.
  Production browser checks confirm `web.app` forwards before Auth starts,
  iPhone uses a same-tab Google flow with the first-party `firebaseapp.com`
  callback, desktop retains the popup flow, and App Check returns HTTP 200.
- Firebase blocking-functions TypeScript check passes. The deployed Gen 2
  functions use a runtime that accepts the configured audience, and both
  Identity Platform triggers resolve to their matching `run.app` services; this
  removes the audience-validation failure that surfaced as an Identity Toolkit
  HTTP 503 during Google sign-in.
- Firebase Hosting previously verified service-worker cache `ptw-shell-v7`. A
  fresh live browser profile installed and controlled the worker, deleted and
  repopulated its document and asset cache, and reported no consumed-body
  `Response.clone()` errors. Live desktop and iPhone-emulated checks both
  reached the Google account chooser at `accounts.google.com`.
- The App Check regression is repaired in Hosting release
  `ee49e1047722d5bf`: live assets `index-CeGcYnjt.js` and `App-COBAGTGW.js`
  contain the Commander gateway origin, App Check header, and production site
  key, while `ptw-shell-v8` is live. Missing credentials still fail closed with
  HTTP 401 and the production-origin CORS preflight succeeds.
- Laval truthfulness Hosting release `8210ca592d3e0651` serves
  `index-DtKsokDI.js`, `App-BlQWs5Db.js`, and `ptw-shell-v9`. The post-deploy
  audit passes shell/assets, gateway health, negative auth, and CORS.
- Owner-visible recovery Hosting release `fd288a9c92b674cd` serves
  `index-CVxHWi6a.js`, `App-DOSmdhLe.js`, and `ptw-shell-v10`. Migration 009 is
  recorded in production; run `01a01540-7c8b-7f0a-af6c-530ce9070bae` exposes
  the original system failure, `codex:production-recovery` resume, and completed
  retry. Its 32/32 persisted provider tasks and USD 0.0192 cost remain exactly
  once. The requested S00-S15 Telegram snapshot was published by the existing
  worker on its first attempt, and the live shell/assets, dependency bridge,
  health, negative auth, and CORS audits pass.
- Idea Laval v3 Hosting release `68b7e7afd31da5ff` serves
  `index-Dryv3Ppk.js` and `App-DYrfMMcY.js`. Main release `2c6626c`, model
  hotfix `93dd302`, platform bridge `ed76c50`, and Idea migration 010 are live.
  A production schema-bound relevance canary returned a distinct session ID,
  `session_mode=fresh`, `ephemeral=true`, `conversation_reused=false`, and a
  schema-valid binary result. The canary exposed and then closed a configuration
  defect where API model name `gpt-5` was rejected by ChatGPT-authenticated
  Codex; the VPS skill now preserves that diagnostic guardrail.
- Saved live run `01a01540-7c8b-7f0a-af6c-530ce9070bae` remains paused at
  Opportunity Matrix after rollout. Its 52 persisted remote task IDs, 52
  exactly-once cost records, USD 0.0372 total provider cost, and 494 evidence
  rows remain present; status exposes `Resume with Market Signals`. No reset,
  rerun, or automatic resume was executed.
- A later authenticated Overview HTTP 500 was traced to an Owner Gateway
  recreation that omitted `/opt/ptw/platform/.env`, producing a passwordless
  platform PostgreSQL URL. Production was recreated with the correct environment
  and `PlatformRepository.summary()` succeeds. Compose interpolation and gateway
  settings now fail fast on this condition.
- Commander/Laval built-image suite: 80 tests pass or intentionally skip only
  seven retired/external-integration cases; every dependency-backed unit path
  passes.
- Focused Laval suite: 33 tests pass, including the 16-stage fixture without
  Google Trends, exact 24-variant provenance, Market Signal formulas/raw data,
  fresh generator/evaluator sessions, legacy preservation and paid-run upgrade,
  append-only LLM audit enforcement, partial country failure, retry/cache behavior,
  manual approval, country rerun/staleness, overrides, authenticated API, and
  export.
- Owner Gateway built-image suite: 19 tests pass, including exact-owner Laval
  proxying, isolated Idea Compose ownership, post-review filter SQL, credential
  fail-fast behavior, and confirmation-only reset/root-operation gates.
- Production Owner Gateway built-image suite: 14/14 tests pass on the VPS.
- After restoring the absent Idea container, its database-backed health reports
  the active mission and zero runs, and the Owner Gateway's protected internal
  Laval run-list call returns HTTP 200.
- Fresh Idea, Commander, and Owner Gateway images build and import their runtime
  entrypoints; the Idea image exposes the `lav` CLI.
- Commander deterministic demo and `git diff --check` pass.
- Independent platform checkout: 66/66 tests pass, including the fresh,
  schema-bound Laval bridge contract.
- Two-database reset rehearsal passes with the required clean checkpoint:
  one mission, zero legacy idea contexts/revisions, ten post contexts/revisions,
  and no domain runtime rows.
- Firebase Hosting returns the PTW Commander shell with HTTP 200. The public
  gateway health endpoint returns `{"status":"ok"}`, protected APIs reject
  missing bearer credentials with HTTP 401, and the production-origin CORS
  preflight allows only the required methods and headers.
- Deployed Commander and Owner Gateway health checks pass; the Idea service
  reports the active mission, zero legacy generations/ideas/contexts, one
  completed fixture history run, and one paused live run. Root broker and Caddy
  restart checks pass.
- Production UID binding matches the authoritative verified Google Firebase
  user after gateway recreation and restart. The prior pin is rejected, the
  authoritative owner claim is accepted, and bounded gateway logs contain no
  restart errors.
- Platform migration 011 passes a disposable PostgreSQL 16 rehearsal and is
  recorded once in production with one non-stopped singleton row. Production
  Overview and filtered/unfiltered Posts reads pass after restart, with no
  Owner Gateway errors after deployment.

## Production work remaining

1. Run the locked 1 GB audit after 24 clean hours. The deployed profile has a
   2 GB swap file, swappiness 10, 329 MB idle available memory, both databases
   at the bounded settings, healthy APIs, and no retired Commander workers.
   The rollout found no new OOM event after its start.
2. Verify competitor and opportunity corrections plus Market Signal inspection from the authenticated
   owner browser. Complete the remaining browser/API functional acceptance:
   create and inspect a Laval run, exercise Plan/Execute and root terminal
   access, and verify restart persistence from the browser.
3. DataForSEO is configured and the saved five-country live-search run reached
   the Opportunity Matrix with paid task IDs and cost preserved. The owner must
   explicitly choose **Resume with Market Signals** in the web console; deploy
   must not start it. Google Trends can be added later but is not an acceptance
   blocker. Fixture evidence must not enter the permanent Commander research graph.
4. Run owner Plan/Execute, root `id`/`pwd`, Telegram emergency controls, and
   restart-persistence acceptance. Do not claim
   Telegram/provider readiness before these pass.
5. Exercise the production reset only after the owner supplies its exact web
   confirmation. The reset is irreversible and was intentionally not invoked
   during deployment.

## 2026-08-18 Laval truthfulness milestone

Production audit resolved run `01a01476-a4f6-7f3f-bab0-26845f45fc6d` as a
fixture demo: search, competitor evidence, and Trends used fixture providers;
provider cost and graph-linked sources were zero. All 16 database
artifacts were present. The mobile “artifact not created” message was caused by
a failed `/show` request during a transient whole-VPS stall, not missing data.
The later v3 bridge audit corrected one claim from that report: the independent
platform API rejected the `laval_*` modes, so those language stages used their
persisted deterministic fallbacks rather than Codex. No historic artifact was
rewritten; the v3 bridge repair makes future execution auditable.

Migration 006, provider readiness, evidence-mode badges/exports, stop-before-
Trends behavior, queued DataForSEO task persistence, the USD 0.05/0.04 spend
boundary, mobile error/export handling, and a secret-safe provider setup script
are deployed in migration/image/Hosting release order. Post-deploy checks prove
the preserved run is `demo_fixture`, all 16 artifacts persist, fixture evidence
has zero Commander graph links, both internal authenticated export formats carry
the demo warning, readiness is fail-closed, and restart persistence passes. The
remaining acceptance boundary is a physical authenticated owner iPhone reload.

Migration 007 temporarily lowered the live-search ceiling to half a cent. After
confirming that the fixed five-country, secondary-language, and competitor-
evidence scope conservatively requires about USD 0.0372, the owner restored the
original five-cent boundary. Migration 008, runtime clamps, setup, readiness,
and the mobile UI now enforce USD 0.05 maximum with USD 0.04 reservable.

The first DataForSEO credential attempt returned an access-specific HTTP 403;
dummy-auth probes from the same VPS returned the expected 401 from sandbox and
production, proving endpoint reachability while production remained unchanged.
The setup script now reports bounded HTTP/provider status details so account,
IP-whitelist, and credential failures are actionable without exposing secrets.

The first paid live run persisted 32 Standard-queue task IDs and completed 31
within the original 900-second poll window. The remaining paid task completed
remotely and the run resumed by fetching that same ID, with no repost or second
charge. Production now allows 3600 seconds for queue outliers and tells the
owner to Retry later while preserving exactly-once task and cost state.

That recovery was initially triggered by Codex from the VPS, not by the owner
button. Laval now makes the boundary auditable: migration 009 stores bounded
stage failures, resume actors/outcomes, and retry completion; the status API
returns provider-task/cost recovery facts; and the Ideas UI separates Resume
saved work from deliberate stage rerun. Those recovery notifications previously
rendered the authoritative run state through Commander outbox; migration 011
now preserves but cancels unpublished Telegram rows, and the 1 GB profile
retires both automatic and owner-triggered status delivery.

## Operational warning

The GitHub working tree and `/opt/ptw/platform` have unrelated histories. Do
not merge or overwrite one with the other.
