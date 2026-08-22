# Commander current state

Status: Natal iterative three-template review workflow production verified
Updated: 2026-08-22
Architecture authority: [`commander-architecture-review.md`](commander-architecture-review.md)

## Current implementation milestone

Natal now has a canonical landing factory under `natal/`: the exact source
Natal logo and six SVG marks are digest-pinned, one mobile-first UI kit is shared
by product, community/event, and waitlist/concept templates adapted from the
three supplied landing projects, and a deterministic Python builder produces a
dependency-free static site with normalized brief and source provenance. The
`$natal-landing-builder` prevents brand drift and fabricated proof; its
publication authority is narrowly limited to the owner-authenticated,
server-pinned Firebase workflow.

The Owner Console has a sixth `Лендинги` workspace. It loads completed live
Idea Laval evaluations, maps the preferred thesis and mechanisms into editable
business idea, target audience, pain, promise, features, steps, and CTA fields,
and shows all three templates on every round. Recommendation is only a default:
`product`, `community`, and `waitlist` can be switched or reapplied repeatedly
in any order. Each application creates an increasing immutable revision for
that Idea, optionally `supersedes` the published version selected from history,
and preserves every earlier public URL.

Before persistence, Owner Gateway now fails closed unless the independent
ChatGPT-authenticated bridge advertises `natal_landing_revision`. A fresh,
strict-schema builder-agent turn reads the canonical Natal skill, selected
template, current brief, and captured feedback memory; code keeps source IDs,
CTA destination, and verified proof server-owned. The static builder then
publishes the revision to the dedicated `natal-landings-86123` Firebase site.
The Landing tab polls only Landing builds, embeds the exact published page, and
offers durable retry without redirecting to global Jobs or Commander plans.

Owner comments are append-only runtime skill memory. Each comment creates a
`HumanFeedback` that `evaluates` the exact published Landing plus a zero-delta
`WeightUpdate` that `adjusts` the reviewed template component. A new revision
snapshots the latest 100 feedback UUIDs in chronological order and links each
as `derived_from`; older memory remains immutable graph history. Browser review
never mutates `SKILL.md` or rewrites an earlier artifact.

This correction follows the first real owner click. Legacy command
`71ff6c4e-53cd-47ca-8389-2fa1763729ba` created only a plan request and failed
before planning because the mounted Codex refresh token could not be refreshed.
The previous Firebase Auth service account also had no Hosting permission. The
failed command remains audit history. The replacement uses a separate publisher
identity, a server-pinned site, an explicit public-file allowlist, and never
publishes `brief.json` or `build.json`.

Production release `natal-feedback-bbcaf90` at commit `bbcaf90` runs in all
three healthy application services. Owner Console Firebase Hosting version
`8e674dd9771a18ed` serves `index-BZyMdMS1.js`, `App-BOYcAlow.js`, and
`ptw-shell-v24`. The original failed request was replayed through the new domain
pipeline without altering its audit record: build
`c691ef38-a142-4c26-ae3a-6fab29e8b175` is published as dedicated-site version
`61854d2e51b8ec0c` at
`https://natal-landings-86123.web.app/builds/c691ef38-a142-4c26-ae3a-6fab29e8b175/`.
It retains a `derived_from` edge to Idea Laval run
`01a01de0-4980-7ab4-aa91-0cebb8aab3c8`; the row, lineage, and URL survived an
Owner Gateway restart. Both the build URL and latest-root URL return the
idea-specific Natal page, its sampled CSS/SVG/PNG assets return HTTP 200, and
both private JSON paths return HTTP 404.

The owner's next application preserved that waitlist build as revision 1 and
created community revision 2, build
`fc06d55b-4fb6-45e4-813f-0f1abf5e47a4`. Its first two bridge executions remain
failed history: the VPS ChatGPT session required device reauthentication, and
the new auth inode initially had root-only permissions that the non-root worker
could not read. The credential contents were never copied or exposed. After
repairing the exact read-only projection and recreating the worker, platform
job 62 completed with a fresh ephemeral session and revision 2 published as
Firebase version `d42c1e90c039b947` at
`https://natal-landings-86123.web.app/builds/fc06d55b-4fb6-45e4-813f-0f1abf5e47a4/`.
Its `derived_from` Idea edge and `supersedes` revision-1 edge are intact, both
private JSON paths return 404, root and versioned HTML digests match, the frame
policy permits only the two PTW owner origins, all heavy-operation guards are
idle, and both production owner/dependency audits pass.

Branding v1 now runs inside the existing Idea process as the evidence-backed
stage between a completed live Idea case and future visual-post generation. The
Owner Console has six-item responsive navigation with Branding and Landings
between Ideas and Jobs, a readable eligible-case picker, a sequential text-only review for
each of the three logos, explicit direction approval, and private Brand Kit ZIP
download. The primary mobile flow shows one logo, one text field, and one CTA at
a time. A comment regenerates that same logo; an empty field explicitly approves
it and advances. Stage inspection and technical controls remain available only
through collapsed disclosures. Posts remain retired at HTTP 410.

The durable worker snapshots the whole Idea case, uses no paid SEO, bounds
public pages/official YouTube/owner references, makes exactly three symbol-image
requests, and deterministically renders wordmarks/icons and a code-owned
React/TypeScript kit. It stores retry/restart/provider/cost history, serializes
with Laval and Codex, and publishes UUID-linked BrandDirection, Creative,
component, feedback/weight, artifact, and immutable BrandKit graph history.
Stale/superseded kit enforcement is preserved for the future batch contract.

The kit vendors pinned Inter, Manrope, Montserrat, and IBM Plex family binaries
with full OFL files and checksums; generated wordmarks use the selected font.
The deterministic PostgreSQL pipeline, three-review approval, kit superseding,
strict retry, provider-task reuse, graph lineage, URL safety, authenticated
gateway proxy, web unit/build, and desktop/mobile/iPhone WebKit flows pass.
PTW release `branding-codex-cad4264` from commit `cad4264` is deployed serially
on all three application services. Independent platform binaries
`branding-bridge-36c2c23` run from platform source `d9f1498`; the follow-up
source change reserves a 64 MiB demand-backed worker tmpfs for Codex cache and
image transport. Firebase Hosting serves `index-dPkiaUdM.js`,
`App-NVMs-4jm.js`, and `ptw-shell-v18`. Both Firebase hostnames, live dependency
and security checks, and all pinned-container checks pass.

Production Branding reuses the existing `auth_mode=chatgpt` Codex worker; its
auth projection has refresh tokens and no literal API key. The authenticated
bridge exposes the exact five Branding modes and one `gpt-image-2` image call,
while paid SEO and caption scraping remain disabled. Both completed live Idea
cases are selectable even though they have no surviving thesis; rejected
verdicts remain visible rather than being rewritten. The strict readiness audit
passes with `PTW_REQUIRE_BRANDING_READY=1` and identifies the credential source
as the established Codex ChatGPT session.

A production out-of-run logo canary completed as platform job 41 and fresh
session `01a02454-cc62-7d91-a362-b6291fb2bfb6`. The bridge retained one
SHA-256-addressed 1254×1254 raw PNG, Idea verified its digest and normalized it
to a transparent 1024×1024 PNG, and cost metadata truthfully reports Codex
included usage with no USD amount. The worker removed the temporary image
session, no platform job remained queued/running, no new OOM evidence appeared,
and 352 MiB remained available after the canary. No owner case was selected or
Branding run fabricated during deployment; approval of a real Brand Kit remains
an explicit owner action.

The first real Branding run `01a0245a-d070-7207-af07-3bd68506ffc9` completed
all eight automatic stages and all three `gpt-image-2` logo jobs, then entered
the intentional `OWNER_REVIEW` boundary. Every structured provider task
succeeded on its first fresh session, no heavy operation remains active, and no
Branding Telegram action was emitted. An iPhone API-deadline banner during
review exposed an Owner UI defect: its copy told the owner to select Retry but
rendered only Dismiss, while the generic paused stage label made the completed
run look stuck. The corrected UI provides a safe read-only state refresh,
warns that a timed-out mutation may already have committed, labels
`OWNER_REVIEW` as waiting for owner feedback, and explicitly says generation is
complete. The recovery path never repeats a review or approval mutation.
Fix commit `1a5e93a` is live as Firebase Hosting version
`fbeae76963a882d6`, serving `index-BQJjjAPQ.js`, `App-De-t_Yar.js`, and
`ptw-shell-v19` on both Firebase hostnames. The public post-deploy audit passes
gateway health, negative authentication, CORS, and exact live-bundle markers;
27 Vitest checks and all 12 desktop/mobile/iPhone WebKit scenarios pass.

A follow-up mobile review incident showed that the annotation canvas, rating
row, technical direction specimens, and duplicate logo loads made the owner
workflow slow and needlessly complex. Branding feedback is now genuinely
text-only: a comment creates append-only HumanFeedback plus a zero-delta
WeightUpdate without inventing a neutral rating. The legacy rated/annotated API
remains readable and accepted for historical compatibility.

PTW release `branding-simple-d5cca7a` from commit `d5cca7a` is deployed
serially on Commander, Idea, and Owner Gateway. Migration 014 makes only the
review rating projection nullable; existing rated reviews and immutable assets
are unchanged. Firebase Hosting version `decb85b0c00234d7` serves
`index-Dm3k7Nlv.js`, `App-CH1_eIWW.js`, and `ptw-shell-v20` on both hostnames.
The live bundle contains the text-only/next-step markers, gateway health is
200, unauthenticated access remains 401, CORS preflight is 200, and the latest
real run remains at `OWNER_REVIEW` with two of three reviews preserved. The
release memory audit finished with 347 MiB available and no deployment OOM.

A subsequent owner review exposed a contract error in that simplification:
storing any comment was treated as completed review, so the console advanced to
final direction selection without applying the requested changes. The corrected
contract distinguishes correction from approval. A non-empty comment queues an
immutable, restart-safe logo revision for the same direction and keeps the owner
on that logo with visible progress. The new Creative `supersedes` the previous
one and is `derived_from` the exact feedback. An empty field appends an explicit
approval of the current Creative and advances. Final direction selection is
unavailable until all three current Creatives have explicit approvals. Existing
legacy comments remain actionable change requests and can be replayed without
losing append-only feedback or asset history.

PTW release `branding-review-ba24714` from commit `ba24714` is deployed
serially on Commander, Idea, and Owner Gateway. Idea migration 013 adds durable
logo-revision attempts and immutable source/result references. Firebase Hosting
version `d1733984e7f1d6e8` serves `index-CfMCr_ii.js`,
`App-BmBF0zt5.js`, and `ptw-shell-v21` on both hostnames. The live audit passes
gateway health 200, unauthenticated denial 401, CORS preflight 200, and exact
bundle/service-worker markers.

All three non-approval signals preserved on the first real Branding run were
replayed serially after cutover. Each produced a distinct version-2 Creative and
immutable Artifact; all three current logos are back at pending explicit
approval, and none is counted as approved. Graph inspection verifies three
`supersedes` and three feedback `derived_from` edges, all asset digests match,
the operation guard is idle, and no Branding Telegram action exists. Restarting
only Idea preserved every revision and the owner-review state. Verification
passes 124 built-image Commander/Idea tests, 25 built-image Owner Gateway tests,
two disposable-PostgreSQL Branding migration/pipeline tests, 29 Vitest checks,
and all 12 desktop/360 px/iPhone WebKit flows. The established 1 GB audit passes
after regeneration and restart with 399 MiB available and no new OOM evidence.

Release verification passes 123 Commander/Idea tests in the tagged Idea image
against disposable PostgreSQL (five intentional retirement skips), 23 tagged
Owner Gateway tests, 26 Vitest checks, 12 Playwright checks, the deterministic
ZIP checksum/font/license/Ukrainian-glyph/contrast checks, and compilation of
all ten generated TypeScript components. The independent platform suite passes
76 tests in its exact amd64 worker image.

The Owner Console now restores Firebase redirect sign-in from the mounted boot
path instead of waiting for the Auth observer to render the login screen first.
Firebase Auth selects local-storage persistence before initialization, avoiding
the previous `getAuth()` plus asynchronous persistence migration through
IndexedDB during Safari redirect/pagehide. A ten-second boot fallback and a
separate bounded ID-token/App-Check wait turn browser storage stalls into a
visible retry path instead of an indefinite loading screen. The service worker
also bypasses all Firebase `/__/auth/` helper and callback traffic, and the
production build/live audit requires these Safari safeguards. The shell cache
is bumped to `ptw-shell-v16`. Firebase Hosting version `bca9633a185d6218`
serves `index-4XLnhkNC.js` and `App-Cix7w3By.js` from source commit `feeaf8f`.

The incident was isolated before the Owner Gateway: the live shell, lazy App
chunk, App Check marker, gateway health, negative authentication, CORS, VPS
dependencies, and authenticated desktop requests were healthy, while the iOS
attempt produced no API preflight or request after Google sign-in. New unit
coverage proves a redirect result opens the console even when the Auth observer
never fires and a completely stalled boot becomes recoverable. Vitest passes
24 tests, Playwright passes nine checks across desktop, mobile Chrome, and
iPhone WebKit, and the production web build gate passes. The post-deploy live
audit confirms the exact chunks, Auth persistence marker, App Check header/site
key, `/__/auth/` worker bypass, gateway health, negative authentication, and
CORS. A controlled production iPhone WebKit client under `ptw-shell-v16`
reaches the Google account page. A physical authenticated iPhone return and
Overview response remain the only owner-only acceptance.

Completed Idea Laval cases now expose one primary `Завантажити PDF` action in
the Research header. The Idea service generates a concise Ukrainian report with
five-phase and score visuals, competitors, opportunities, market signals,
YouTube observations, mechanisms, falsification outcomes, every stage status,
and bounded clickable HTTP(S) references. PDF export is whole-run only and
rejects unfinished runs; JSON and Markdown remain the technical exports. The
live completed 22-stage case generated a valid 12-page, 80034-byte PDF with 66
clickable URI annotations. This revision is deployed as PTW release
`laval-pdf-9a2545a` at commit `9a2545a` and Firebase Hosting version
`69930816d588c284`, serving `App-CoaIr1k1.js` and `ptw-shell-v15`.

The deployed Owner UI also keeps stage inspection and correction item-local.
Every stage card explicitly opens details; selected competitors, opportunities,
and legacy trend rows expose their permitted audited action beside the readable
item, with the reason requested only after the owner acts. Competitor addition
remains contextual to the selected list. The detached UUID target form is
removed, while server-resolved UUID, required reason, actor audit, and
downstream invalidation remain unchanged. Run summaries report processed stages
separately from strict completion and show partial-stage count, so 21 complete
plus one partial no longer conflicts with a 22-of-22 processed header.

New Idea Laval runs use immutable pipeline version `mechanism_thesis_v1` and a
22-stage evidence -> mechanism -> product-thesis topology. The pipeline retains
24 candidate variants only as intermediate material, extracts 6-20 mechanisms
with code-owned support vectors, synthesizes at most three complete product
loops, and runs fresh-session strict-schema falsification with one retry and no
live fallback. Only surviving theses publish to Commander; an all-weak/rejected
run completes truthfully as `no_surviving_thesis`.

Live V2 requires canary-verified DataForSEO and the official YouTube Data API.
YouTube behavior support is counted by unique creator channel, comments omit
author identity, captions are never scraped, optional owner transcript text is
stored as a manual Source, and count snapshots are append-only. Velocity remains
`insufficient_history` until a second observed snapshot.

Commander now owns `product_mechanism` and `validation_workspace` entities.
Selecting a survivor creates one idempotent workspace and three proposed manual
market probes. Explicit owner start records state but performs no publication,
contact, spend, or other external action. Probe facts, Insights, and append-only
Continue/Mutate/Pivot/Reject decisions remain separate. Continue alone exposes
a Plan job with bounded graph context and a `RESEARCH_CONTEXT_CONSUMED` audit.

The owner UI has Research and Validation subviews, five readable research
phases, thesis cards without percentage-like success scores, server-side UUID
resolution, manual probe evidence capture, explicit mechanism selection for
Mutate, and a materially different loop requirement for Pivot.

Production runs PTW release `branding-codex-cad4264` at commit `cad4264` and
independent platform images `branding-bridge-36c2c23` from source `d9f1498`.
The platform advertises exactly the 11 active Laval modes, five Branding modes,
one `gpt-image-2` request per logo, immutable Commander-volume transport, and a
1000000-byte request limit through its authenticated capabilities endpoint;
Idea startup and release verification fail closed on any contract drift.
DataForSEO, YouTube Data API, and both the Laval and Branding bridge contracts
report live-ready.

The first real `mechanism_thesis_v1` run
`01a01de0-4980-7ab4-aa91-0cebb8aab3c8` recovered in place from its S07 bridge
rejection and completed S21. S00-S06 were reused, S07 completed on stage attempt
2, and all 11 structured modes recorded a successful invocation. Its 98
provider tasks, 52 paid remote IDs, USD 0.0372 actual provider cost, 26 YouTube
videos and snapshots, and 533 evidence rows did not change during recovery.
Append-only history retains the two failed S07 calls, the authenticated recovery
actor, and the successful retry. An out-of-run S07 canary proved a fresh
ephemeral platform job before resume; a one-service Idea restart afterward
preserved the complete database snapshot and passed loopback, public, bridge,
and Owner Gateway dependency checks.

The reset rehearsal exposed two runbook defects before its final checkpoint:
the helper did not inherit the deployed image tag and its platform owner seed
did not explicitly inject `PLATFORM_OWNER_TELEGRAM_ID`. Production was recovered
under the maintenance lock on the verified V2 images. The reset now resolves a
matching non-`latest` tag from all three deployed application containers,
forbids builds, injects the bounded owner value, and recreates Owner Gateway.

Local verification: the Commander suite passes 107 tests with 50
expected external/dependency skips; the disposable PostgreSQL Laval suite passes
55 tests; the Owner Gateway built image passes 20 tests; Vitest passes 18 tests;
and the independent platform suite passes 27 tests. Commander demo generation,
both migration families on disposable PostgreSQL, skill verification, production
web build verification, shell syntax validation, and `git diff --check` pass.

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

The Ideas flow now treats **Start research** as one owner action: it creates the
run and immediately starts it, with automatic 16-stage progression selected by
default and manual checkpoint review available as an explicit alternative.
Pending history is labelled as not started rather than ambiguously pending.
Eligible legacy Trends runs expose one mutually exclusive **Continue research**
action that upgrades saved work to Market Signals; the UI no longer presents a
Google Trends wait, manual approval, and provider wait as competing actions.
Telegram status links target the exact run, and the PWA shell cache is bumped so
the retired Trends/Telegram controls cannot survive as an old loaded screen.

The first completed live Market Signals run exposed a second truthfulness
defect: all recorded language calls were fallback/failed because their nested
output schemas were incomplete, yet downstream deterministic fallbacks still
produced and published a shortlist. The correction defines complete strict
schemas for every Laval language mode, adds semantic ID/count validation,
disables fallback for every live evidence mode, and blocks final hypothesis
publication unless all mandatory language stages are model-backed. The
status/show APIs now separate stage completion from model provenance. Ideas
presents readable Ukrainian summaries for all 16 stages, puts raw JSON behind
disclosure, labels the historical result invalid, exposes its successful model
  call count, and never calls its fallback rows finalists.

The next live run exposed an evidence-contract mismatch at Opportunity Matrix:
the model correctly cited IDs visible inside supplied complaint clusters, while
the semantic validator allowed only each dossier's smaller top-level citation
list. The corrected validator derives its allowlist recursively from the exact
bounded model context. Live language calls now receive one fresh-session
automatic retry, retain both attempts in append-only audit, expose a bounded
semantic reason, and distinguish recovered retry failures from unresolved
failures in API and UI quality verdicts.

Creative production and review are retired operationally on the 1 GB profile.
Their source, migrations, immutable artifacts, append-only reviews, UUID
lineage, and historical database rows remain intact. The Posts navigation and
pending-review metric are absent, while cached clients receive HTTP 410 from
post, creative-review, artifact, ad-batch, workspace-acknowledgement, and
status-notification endpoints.

Telegram input is reduced to owner-only `/help`, `/status`, and `/stop`; general
proactive outbound notifications remain retired. The narrow Idea Laval
exception sends one direct, deduplicated `sendMessage` after a run becomes
paused, completed, or failed. It uses no outbox or additional poller and records
append-only delivery actions without changing run state. The established
platform long poller returns bounded emergency responses directly. Unsupported
input returns the web link without creating domain work.
Emergency stop is durable in the platform database and fans out to idea and
creative runtimes; only the web UI can resume the complete system.

The 1 GB runtime profile disables both Commander polling workers by Compose
profile, cancels unpublished Telegram outbox rows without deleting them, and
constructs only the direct Laval transition notifier; it does not import the
Pillow/ad runtime when creative mode is disabled. PostgreSQL connections have five-second
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

- The isolated Natal release passes all 129 Commander tests, all 39 Owner
  Gateway tests in the built image with only two optional database skips, 30
  Vitest checks, and 15 Playwright checks across desktop, 360 px Chromium, and
  iPhone WebKit. The pinned Commander image passes the same 129 tests with 39
  expected database/external skips, and disposable PostgreSQL repository tests
  prove Landing lineage, idempotency, and retry. The serialized publisher reran
  all 30 web checks and the production build, deployed all three healthy images
  plus Firebase Hosting, and completed the public gateway/Auth/CORS audit. The
  live bundle contains the publish, landing-only history, and open-landing
  controls; unauthenticated Landing list/detail/create calls return HTTP 401 and
  the production preflight returns HTTP 200. Firebase Functions type-check,
  Commander demo, Python compile gate, local and VPS skill validation, strict
  production dependency readiness, and `git diff --check` pass.
- Safari recovery Hosting version `bca9633a185d6218` serves
  `index-4XLnhkNC.js`, `App-Cix7w3By.js`, and `ptw-shell-v16`. The live audit
  proves the compiled local-storage Auth marker, App Check header/site key,
  Firebase Auth helper worker bypass, gateway health, negative authentication,
  and CORS. A controlled iPhone WebKit session loaded the login screen under
  the active worker and reached the first-party Google sign-in flow. Vitest
  passes 24 checks, Playwright passes nine cross-browser checks, Owner Gateway
  passes 20 tests, Commander passes 109 tests with 52 expected local dependency
  skips, Firebase Functions type-checks, the Commander demo and production
  build gate pass, and skill verification plus `git diff --check` pass. The
  remaining acceptance is a physical owner-authenticated iPhone return and
  successful Overview response.
- PTW release `laval-review-acc03a2` at commit `acc03a2` is live in all three
  healthy application services. Firebase Hosting version `3ea404fd83205aca`
  serves `index-DYdpqXmf.js`, `App-DtIiyHPO.js`, and `ptw-shell-v14`; the
  deployed application bundle contains the item-local detail, remove, disable,
  processed-stage, and partial-stage labels. Public gateway health returns HTTP
  200, an unauthenticated Overview request returns HTTP 401, and the production
  CORS preflight returns HTTP 200. The authenticated internal dependency audit
  reports all 11 expected Laval modes and the 1000000-byte request limit. Its
  read-only run-list check reports one preserved run with 22 processed stages,
  21 strictly completed stages, and one partial stage, proving the previously
  conflicting counters now describe different states explicitly. Deployment
  did not start, resume, rerun, rewrite, or charge any research run. Commander
  passes 107 tests with 50 expected local dependency skips, Owner Gateway passes
  20 tests with four expected skips, Vitest passes 18 tests, and Playwright
  passes nine checks across desktop and mobile browsers. The production build,
  Commander demo, skill verification, and `git diff --check` pass. Final
  authenticated interaction acceptance remains an owner-browser reload and
  click-through of the inline controls.
- Laval reliability release `976d46a` is live in the healthy Commander, Idea,
  and Owner Gateway services; follow-up `60cd43d` stabilizes the UI recovery
  regression test without changing runtime code. Firebase Hosting version
  `86239a8851ef08c0` serves `index-nqRdLETV.js`, `App-C0QRNtfY.js`, and
  `ptw-shell-v13`; the public shell/assets, gateway health, negative
  authentication, and CORS audit passes. Owner-authorized recovery resumed run
  `01a01a93-e248-7615-942a-f7e0ef1c780b` at `OPPORTUNITY_MATRIX` attempt 2 and
  completed all 16 stages. The run reports 16 successful required language
  calls, zero fallback/unresolved failures, 10 opportunities, 24 variants, and
  24 evaluations. Its 52 completed provider tasks, 52 persisted remote IDs,
  506 evidence rows, and USD 0.0372 actual provider cost are unchanged; no paid
  search was reposted. The append-only audit retains the original S07 failure,
  the owner-authorized resume, and the completed retry. Commander built-image
  tests report 91 passes with 29 expected dependency/external skips, the Owner
  Gateway image passes 19 tests, the focused Laval image and disposable
  PostgreSQL suite each pass 22 tests, Vitest passes 15 checks, and Playwright
  passes nine checks across desktop Chrome, mobile Chrome, and iPhone WebKit.
- Laval integrity release `85f0a2f` is live on all three healthy production
  services. Firebase Hosting version `859b2a2856d201a3` serves
  `index-BFK2C8KR.js`, `App-BR0jJtNv.js`, and `ptw-shell-v12`; the live bundle
  contains the invalid-result warning, model-failure labels, readable stage
  heading, fallback label, and collapsed raw-JSON disclosure. The public
  shell/assets, gateway health, negative authentication, and CORS audit passes.
  Historical run `01a019c8-9872-73e3-baa2-e3f16e27685c` remains completed at
  exactly USD 0.0372 but now reports `invalid`, 0 successful language calls,
  and 16 fallback calls. An isolated strict-schema relevance canary returned a
  schema-valid fresh ephemeral session with no conversation reuse; Laval run
  and invocation counts were identical before and after. No run was started,
  resumed, rerun, rewritten, or charged during release verification. Commander
  built-image tests report 88 passes with 28 dependency/external skips, the
  Owner Gateway image passes 19 tests, the focused Idea Laval domain image
  passes 20 tests, Vitest passes 15 checks, and Playwright passes nine checks
  across desktop Chrome, mobile Chrome, and iPhone WebKit.
- Seamless Laval Hosting release `ca95e7a78db478c1` serves
  `index-DMjj1FUz.js`, `App-CPpo1qZU.js`, and `ptw-shell-v11`. Fourteen Vitest
  checks and nine Playwright checks across desktop Chrome, mobile Chrome, and
  iPhone WebKit pass, including one-click create/start, automatic-mode default,
  exact-run deep-link selection, and the single legacy Market Signals recovery
  action. The live shell/assets, gateway health, negative authentication, and
  CORS audit passes. No run was started or resumed during deployment. The Idea
  container was intentionally not recreated while a pending run exists, so the
  notification deep-link formatter is committed but awaits the next safe Idea
  image rollout.
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
- Direct Laval Telegram transition release `59bc63f` is live. Production has
  `LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED=true` while the retired general
  `OUTBOUND_NOTIFICATIONS_ENABLED` path and both repository polling workers
  remain disabled. A post-restart canary sent one message, appended reserved
  and sent actions, produced zero `commander_outbox` rows, and did not start or
  resume a Laval run. The saved live run remained paused at Opportunity Matrix
  with all 52 remote task IDs, 52 cost records, USD 0.0372, and 494 evidence
  rows unchanged. Hosting version `a4f3c404d086ada6` passed the live audit.
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
3. Review the recovered five-country live run's evidence, opportunities, and
   final shortlist from the authenticated owner browser. Google Trends can be
   added later but is not an acceptance blocker. Fixture evidence must not
   enter the permanent Commander research graph.
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
