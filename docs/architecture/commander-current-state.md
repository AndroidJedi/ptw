# Commander current state

Updated: 2026-09-22
Branch: `main`
Deployment: live and accepted from code revision
`84f4db7b5e8a22773cd128ff3fd66528ef11a681`. Owner Hosting version
`851b5707e0309f29` remains current. Commander and Validation run
`god-mobile-20260916-84f4db7b5e8a`; unchanged Owner Gateway retains
`god-mobile-20260916-57332cbb949a`, and the companion platform retains
`instagram-manual-retry-20260915-d455ac4`.

## Approved production accounts — local, not deployed

The source now permits the two additional verified Google accounts
`svitlanabilan23@gmail.com` and `befree833@gmail.com` through the Firebase
blocking functions, Owner Console, and Owner Gateway. The original account
retains its pinned UID and App Check remains required. Deployment must update
the Firebase auth-guard functions separately from the PTW in-place release;
the latter includes migrations 012–014 and needs its preserving confirmation
gate. Do not treat a Hosting-only rollout as complete access.

The first owner-authorized mobile attempt passed CI and applied additive
migrations 012–014 while preserving existing rows, but failed after cutover
because the still-reused companion bridge lacks `studio_manual_edit` (and
`template_creation`). The receiver restored the accepted application and Owner
Hosting. Firebase functions remain unchanged. A compatible platform API/worker
revision is prepared locally; the coupled release must use the serial in-place
publisher once direct VPS access is available.

## Template draft recovery and reliable comparison — local, not deployed

Templates now has a separate Drafts section above the accepted gallery. It shows
active, failed, interrupted, paused, capability-gap and proposed runs with their
latest digest-bound preview, localized status, comparison count, safe failure
summary and Open/Continue action. Active drafts poll automatically. Accepted and
rejected runs remain in compact history, and only accepted versions enter the
gallery or Project template picker. The page explains that reference analysis is
durable while raw reference pixels remain temporary.

The Draft action now visibly opens its run: the page scrolls to and focuses the
review panel, localizes the run status and phase, and shows the proposed-run
accept/reject actions before the preview with a short explanation of the next
step. The button exposes an opening state while the run detail is fetched. This
fixes the misleading no-op appearance caused by rendering the detail above the
current viewport.

Every Template Creation Agent phase now pins `xhigh`. Model and effort are bound
into the request fingerprint and sanitized invocation record. A structured bridge
must explicitly advertise `template_creation → xhigh`; other workflows keep their
existing effort. The two-attempt structured correction and 420-second timeout are
unchanged. The system-prompt share is 6 KiB within the existing 52 KiB total so a
second-attempt validation hint cannot block its own corrective call.

A failed compare resumes with the exact saved PNG only when its media digest and
definition digest still match. It does not rerender or increase the iteration
count before a valid comparison response. Failures store only phase, category,
model, effort, attempt count and a sanitized validation error. Valid solvable
patches are retained before a capability pause; an owner may explicitly choose an
existing-component approximation instead of developing a new capability.

Authoring now has digest-pinned official App Store and Google Play badge assets,
canonical Natal symbol motifs with deterministic rotation, and transparent Pexels
fixture `neutral_person_stock_v1` with source/author/license provenance. The fixture is replaced
by the existing Post image after an accepted template is applied to a Project.
Store badge boxes render as their full black rounded pills with the official artwork
contained and centered, preventing intrinsic Apple/Google asset ratios from making
the visible buttons smaller or uneven against the owner reference.
Bright owner markup is treated as annotation only. Refinement comparisons retain
the last proposed revision as a baseline, apply pending edits before a focused
clarification, and stop repeated issue/path cycles as `no_progress`. Every four
comparisons produce a manual checkpoint. The Templates workspace presents the
preview and next action together, localizes checkpoint categories, and exposes
Continue, Refine and append-only Restore without showing a disabled Accept action.

Each correction is now durable and visible with exact owner text and phases.
Retry and explicit Discard are append-only, correction screenshots stay isolated
from initial analysis, and preview/compare bind the applied correction ID. Browser
storage retains the last two texts until the server confirms them. Accept is
hidden for working/failed corrections. Preview reuse also checks a render contract
over document, renderer version and fixed-asset digests.

The local run `fff155a8-b5c0-4313-a958-18aaf3c9e779` append-only recovered revision
110 as revisions 112–113. Its exact correction reference was recovered at digest
`22bdb8fcc059f33d4f7e42ce7272a518ea7ae37a9910fd67a0574884afffe252`.
Revision 124 first reached `proposed` with the two four-times-smaller Natal motifs
at `-18°/+14°`, official store assets and the visible Pexels fixture. After owner
review showed the contained artwork made the visible badges too narrow, renderer
v3 began painting the complete component surface behind image artwork. One more
real `xhigh` compose and compare completed in one attempt each. Revision 135 is
`proposed` at state
`935b0cc12c7520c407e7981cc739bc1b93f35de5c894f8643ac182d428b1b8f5` with both
existing `250 × 58` slots rendered as equal-height black rounded pills, preview
digest `76c373897ec451d86463e5d8860b0f1f1acfcaff4b080f58d4e6752e5b56ad1b`,
render contract `240fca5bc067aa00049329571929222ee4f0dd570d3370fcdf734ecf7a65e0bc`,
zero differences and zero renderer failures. It remains unaccepted and absent
from the reusable gallery until owner review.

Local verification passes 334 Validation tests, 112 web tests, the production
build, nine Templates and three existing-Post application browser cases across
desktop, 360px and iPhone WebKit, 43 Commander tests with five expected
environment skips plus the demo, the authenticated disposable PostgreSQL
Templates and existing-Post application canaries, the deterministic Studio visual
audit, and skill verification. The local API was restarted on the updated source;
no commit, push, deployment, publication or production mutation ran.

## Apply templates to existing Posts — local, not deployed

The Post editor now has Change template, a compact Post selector and a single
editing toolbar. It lists accepted Post designs with native previews and applies
an exact version to the existing creative, carrying pending copy and its raw
image while preserving image history and immutable approvals. Authored layouts
expose their own text fields and the shared image workflow; Phone Metrics keeps
its established controls and Manual Agent. New template versions never silently
update selected layouts. Initial Brief composition remains Phone Metrics.

The switch validates registry identity and state, reconciles uncertain requests,
rolls back failed renders, and persists through SQLite and PostgreSQL restart.
New migration `014_project_post_templates.sql` extends the preserving template-ID
constraint without rewriting prior rows. Historical cloning and Landing sources
now read template identity from the approved record, and publication copy uses
its visible authored text. Existing approved PNG bytes remain unchanged.

Verification includes 324 Validation tests, 105 web tests, the production build,
12 desktop/360px/iPhone-WebKit Post flows, the deterministic Studio visual audit,
and a real authenticated HTTP/disposable-PostgreSQL apply/approve/restart canary.
Focused regressions additionally cover historical Landing/clone sources and
copy, and the live local chooser was inspected in Ukrainian at 1440 and 360px.
The local API was refreshed; no owner Post was changed during verification.
No commit, push, deployment, publishing or production database mutation ran.

## Templates gallery and Template Creation Agent — source only, not deployed

The global private Templates destination registers the protected Phone Metrics
and existing Landing definitions, plus owner-accepted declarative versions.
Post-only, Landing-only and coordinated creation share the existing template
registry and structured provider infrastructure. Combined acceptance appends two
separate versions atomically, with an exact Post-template reference on Landing.
Existing Project selection, content, controls, saves, approvals and lineage are
unchanged. See [Templates mode](templates-mode.md) for the canonical route.

Typed component configuration compiles to the existing Studio renderer, with
reusable native phone/brand assets, bounded text/image/CTA/card/overlay/decoration
instances and desktop/mobile geometry. Built-in gallery previews use the real
Phone renderer and shared Landing React renderer with neutral fixtures. Immutable
versions and PNG digests persist through new forward migration
`013_template_authoring.sql`, with the same append-only/CAS/request semantics in
PostgreSQL and local SQLite. No applied migration was modified.

The single-worker agent persists one reference analysis, patch composition,
render/compare iterations, differences and byte measurements. Temporary normalized
references expire and never enter template versions or Project state. Corrections,
timeouts and restart interruptions resume saved state. Every proposal requires a
successful comparison; owner acceptance creates versions. Genuine capability gaps
pause for an isolated allowlisted source review, focused tests, visual inspection
and an exact source/preview receipt before resume. Studio Manual Agent cannot code.
The new canonical policy is `skills/template-creation-agent/SKILL.md`.

Verification passes 320 Validation tests, 15 Owner Gateway tests, 104 Owner Console
tests and the production build; 43 Commander tests plus demo (seven expected host
skips; five in the runtime image after installing its missing test prerequisite,
Git). All 84 desktop/360px/iPhone-WebKit flows passed across the full run and one
focused retry of an existing Commander attachment timing failure; all six new
Templates flows also passed a final rerun. Studio visual audit, full-resolution
native previews, skill validation/symlink sync, compilation, whitespace checks,
disposable migration/schema guards, Templates PostgreSQL acceptance/restart and
existing Studio save/restart canaries pass. The refreshed loopback API serves
authenticated, digest-verified native built-in previews.

A real Codex combined canary converged after two comparisons and resumed from its
saved analysis. The final measured call used 18,074 B of structured context and
a 418 B response, with one attempt and separate image attachments. The Validation
image build could not fetch Node base-image metadata because Docker Hub timed out;
that new image remains unverified. Production also requires the companion bridge
to advertise the optional `template_creation` JSON/multimodal mode. No source was
committed, pushed, deployed or published, and production PostgreSQL was untouched.

## Modular Post/Landing templates and compact agents — source only, not deployed

The reported Post workspace merge is a browser-state race rather than evidence
that saved PostgreSQL creatives were combined or deleted. Project/creative
navigation reused the same React Studio instance, and an older asynchronous
creative-list/detail response could finish after Back navigation and overwrite
the newer route's editor state. The Post view is now keyed by its exact
Project/creative scope, each load invalidates prior generations, and route
changes clear stale list/detail/editor state. A regression resolves the previous
Project response last and proves it cannot replace the current Project's Post.

Post and Landing templates now use separate immutable registries over a small
surface-neutral definition contract. Phone Metrics is the only registered Post
definition; the unsupported square template implementation and compatibility
paths are removed. A preservation-safe `NOT VALID` constraint migration rejects
new unsupported Post rows while preserving every existing row and physical table
name. Landing definitions remain independently
creatable and may resolve a versioned Post-template definition reference without
receiving any Project, Brief, creative, asset, or approved-version data.

Manual Agent mode now sends only catalog-backed scalar values and accepts at
most 64 scalar patch operations. PTW applies patches and validates the complete
state server-side, preserving the browser response contract. Recent text is
capped at four messages/4 KiB, and Post/Landing provider contracts have explicit
component, total, and response byte budgets recorded in invocation metadata.
Initial generation uses registry-owned compact catalogs and surface-filtered,
byte-bounded Creative Skill views instead of unbounded authority snapshots.
This source milestone has not been deployed; the production revision and
Hosting version above remain unchanged. Local verification passes all 297
Validation tests, 14 Owner Gateway tests, 43 Commander tests with seven expected
environment skips plus the demo, 99 Owner Console tests and production build,
all 78 desktop/360px/iPhone-WebKit flows, the Phone Metrics visual audit, skill
validation, Python compilation, whitespace checks, migration-runner idempotency,
the disposable full-schema guard, and the real HTTP/PostgreSQL save/restart
canary. The migration canary proves historical unsupported rows are retained
while new unsupported Post rows are rejected.

## Post and Landing manual Agent mode — local, not deployed

Post Studio and Landing Studio now expose one owner-only **Agent mode** that
translates a task message plus up to four temporary screenshots into the complete
bounded configuration/content already editable in that surface. The browser
applies the returned values through the same local editor state and preview path
as manual control changes. Phone Metrics may additionally request its existing
phone-screen generator; Landing may request its existing hero and visual-break
generators. Screenshot references are normalized and metadata-stripped for that
turn, then remain outside Project state, checkpoints, versions, and chat history.

The agent is a schema-bound Studio operation, not an MCP server or coding agent.
It cannot add components, HTML, CSS, scripts, claims, social proof, or contact
endpoints; execute tools or shell commands; modify repository files; or Save,
Approve, Publish, or deploy. Post and Landing remain draft/state-hash guarded,
provider responses are domain-validated, and image work uses only the existing
generation routes after the returned draft has been persisted where required.
The canonical runtime policy is `skills/studio-manual-agent/SKILL.md`.

The local `studio_manual_edit` v3 prompt payload now includes a fail-closed
English `agent_control_contract` generated from the live Post/Landing component catalog.
It explains every currently exposed component's purpose, visible result, exact
setting paths, bounded options, dependencies, and immutable boundaries. In
particular, it maps “hide/remove the phone device” to the Phone Metrics device
visibility control, distinguishes that from Image only, and exposes the saved
image-style/background choices without starting generation unless the owner
explicitly requests it. A catalog change without matching semantic coverage
fails before a provider call. This remains local and not deployed.

A local owner trial exposed a timeout-classification and request-recovery gap:
the 420-second Codex execution deadline was surfaced as a misleading state
conflict and included raw subprocess context, while refresh discarded the owner
message. Agent edits now use bounded `high` reasoning, keep the semantic layer
under 16 KB, sanitize provider failures as 503/504 without changing the draft,
and retain only the latest four text requests per Project in browser-local
storage. Screenshots and editor state remain ephemeral and are never retained.

A subsequent Phone Metrics trial exposed a compound-intent gap: the Agent
correctly generated requested home-medicine-cabinet artwork but also disabled
the device container, so the final render hid the new pixels and left a blank
area; it also placed slogans rather than requested numerals in the lower Metric
values. The v3 prompt now decomposes all clauses, receives request-specific
end-state constraints, and rejects/corrects schema-valid responses whose control
interactions hide a requested result. “Remove phone + change/show the picture”
now means enabled artwork area plus Image only, a natural picture description
counts as an image operation, one unspecified duplicate logo resolves to the
in-phone mark, and lower numeric requests retain the Metric value/label roles
without inventing evidence. The exact reported Ukrainian instruction is a
regression fixture. Template-inapplicable stale Phone direction provenance no
longer appears as a false changed path. This remains local and not deployed.

The source contract adds the coordinated `studio_manual_edit` structured mode to
local Codex and the production bridge client. Production remains unchanged until
the companion bridge advertises that JSON/multimodal capability and this source is
released with it. Local verification passes all 323 Validation tests, 14 Owner
Gateway tests, 43 Commander tests with five expected environment skips plus the
demo, 114 Owner Console tests and its production build, all 84
desktop/360px/iPhone-WebKit browser flows, the deterministic Studio visual audit,
the new skill validator and canonical skill sync, Python compilation, and
whitespace checks. A no-write Phone Metrics Agent canary on the affected local
creative returned HTTP 200 with no changed paths or image actions in about 19
seconds. A second disposable no-write canary using the exact reported Ukrainian
prompt completed in one provider attempt in about 24 seconds with Image only,
the artwork area enabled, one outer logo, numeric 01/02/03 Metric values, and a
text-free home-medicine-cabinet image action. This milestone has not been
deployed.

## Studio editor image-control recovery — local, not deployed

The Post template now starts every component-setting disclosure collapsed.
Phone Metrics retries transient authenticated raw-hero thumbnail reads and offers
a keyboard-operable retry if the bounded attempts fail, so the current tile is
not left as a silent empty placeholder. The owner’s explicit fresh-generation
choice is preserved instead of forcing Enhance back on after every run.
Generation now has a distinct visible pending state, and focused regressions
prove that success and failure both restore the Generate & apply action.
After an image exists, choosing a complete replacement style and background no
longer strands that action in a disabled state: Generate & apply saves the new
direction first and immediately uses it, while Save new direction remains the
non-generating option.

For owner inspection, the dev server now has an explicit
`VITE_PRODUCTION_BACKEND=true` mode that proxies every `/api` request through the
local same-origin Vite server to the production Gateway. It keeps browser CORS
and authenticated media behavior realistic, does not expose local Tune, and
shows the live-production warning because actions in that window mutate live
authority. Local reCAPTCHA attestation correctly fails closed, so this mode now
requires one registered UUIDv4 Firebase App Check debug token and refuses both
tokenless startup and production builds. The token stays only in the running
local environment; localhost is not added to the production reCAPTCHA allowlist.
The running canary on `localhost:5174` obtains App Check tokens in both Chromium
and WebKit, opens the Google sign-in handoff in both engines, and retains the
expected production `401` boundary without owner credentials while production
health remains `200`.

The Studio Tune, visual-audit, and Owner Console incident skills now require
these invariants. Local verification passes 109 Owner Console tests and its
production build, all 84 desktop/360px/iPhone WebKit flows, independent
Chromium/WebKit App Check and Auth handoff probes, the deterministic Studio
visual audit, 43 Commander tests with seven expected environment skips plus the
demo, all applicable skill validators, the canonical skill sync check, and
whitespace checks. This milestone has not been deployed or published.

## First Brief source attachment guard — live and accepted

An existing empty Project could not receive its first Product Brief because the
immutable Project trigger also rejected the one required `NULL` to source-UUID
attachment. The initial request rolled back before any Source, Brief, graph
edge, provider invocation, or generation job persisted.

Migration `011_project_first_brief_source_guard.sql` allows exactly that first
assignment and still rejects source replacement, source removal, and every
other protected Project-field change. The accepted release passed the complete
GitHub verification/build pipeline, disposable migration and real repository
flow tests, live dependency/auth/schema-bound provider checks, root-only
backup/rehearsal and pre-existing-row preservation proof, serial cutover, Owner
Console audit, and post-release health/resource checks. The affected Project
remains empty and is ready for one normal owner retry; no data cleanup, reset,
or provider recovery was needed.

## Owner editor responsiveness and Commander keyboard layout — live and accepted

Owner Console color controls now pair the native swatch with one editable,
copy/pasteable `#RRGGBB` field across Post Studio and Landing. Post
component-setting panels use one semantic expandable/collapsible
section control. Phone subforms respond to the inspector's actual width rather
than only the browser viewport, so button, metric, typography, and color controls
stack before labels or values collide in a narrow sidebar.

Commander now derives its workspace height from the visual viewport's bottom and
the workspace's real top position. When a mobile keyboard is open, the mobile
navigation yields that space and the bounded composer remains visible and
independently scrollable. Local checks cover pasteable HEX values, all Phone
section disclosures, narrow-container geometry, simulated keyboard resizing,
desktop/360px/iPhone WebKit flows, and the deterministic Studio visual audit.

The preserving release passed 102 Owner Console tests and its production build,
all 84 desktop/360px/WebKit browser flows, schema/skill/dependency/resource
audits, and the read-only Telegram identity canary. It advanced the deployed
revision without restarting a runtime container, published the Owner Console,
and verified the live entry and application bundles, Gateway health, private
route rejection, and CORS. No migration, production-data mutation, provider
execution, reset, or outbound Telegram message occurred.

## Commander development branch publication — live and accepted

Commander now has a branch-publication path independent from production Deploy.
An explicit owner chat instruction or **Push branch** action publishes the clean,
committed current hosted branch through the credentialed host controller. The
push is normal and non-force, runs no release checks, never promotes `main`, and
does not deploy. The coding runner still receives no GitHub key. Protected and
divergent branches fail closed, and ambiguous transport outcomes reconcile the
exact remote revision. The Owner Console shows the current branch and distinct
push progress. A post-release private GOD chat read the exact Git revision and
clean status, survived a locked `commander-god`-only restart with its completed
reply intact, and the live no-op publication smoke test pushed
`feature/instagram-manual-validation` at the accepted revision without starting
another deployment.

The accompanying restriction audit found no other source-development handoff
that incorrectly depends on production deployment. Plan remains read-only; the
coding shell still cannot access production data, secrets, Docker, publishing,
or external messaging; and protected/force Git updates remain unavailable.
Those are retained production and credential boundaries, not development gates.

## Project-default Natal logo colors — live and accepted

Post Studio now exposes one symbol color and one `NATAL` name color in both
templates. The shared pair recolors every visible lock-up, including the full
symbol inner stroke, while preserving the canonical PNG alpha, dimensions,
spacing, and typography. Phone Metrics config is v13;
legacy mutable drafts uplift without a false checkpoint and immutable versions
stay untouched.

A changed pair becomes the append-only Project default only on Save or Approve,
with lineage to that edit checkpoint through migration
`010_studio_project_logo_defaults.sql`. Future AI-created Posts and explicit
template replacements inherit locked colors; existing drafts remain unchanged,
and approved clones keep their source-version colors. Preview, Landing, and
Creative Skill learning do not mutate this authority.

Production applied migration `010` from a retained root-only checksummed backup,
proved every pre-existing business row unchanged, and started with zero Project
logo-default rows. The accepted release passed 303 Validation tests, 43 Commander
tests, 14 Owner Gateway tests, 98 Owner Console tests and its production build,
all 84 desktop/360px/WebKit browser flows, both disposable PostgreSQL migration
checks, the deterministic Studio visual audit, live provider/Pexels checks, and
the authenticated Owner Console audit. The first artifact transfer exhausted
the VPS while containerd ingested a candidate image; accepted source, migration
state, images, and Hosting were restored. Pruning 478 obsolete, unreferenced image
tags reclaimed 3.578 GB while retaining all container-referenced images. The
same immutable verified artifacts then completed with about 8.5 GB free.

## Instagram-first manual validation — live and accepted

PTW now focuses on fast business-idea tests. Active social UI/API is
Instagram only. Organic direct publishing remains, and manual **Copy all texts**
creates an immutable exact-Post package with a unique tracked Landing URL.
Meta Ads API and TikTok routes, jobs, and UI are unmounted; their modules and
historical PostgreSQL tables stay preserved behind the new
`legacy-social-automation-recovery` skill.

Paid testing now freezes one published Landing plus 2–6 distinct approved Posts,
creates a ZIP launch kit for one manually configured Campaign → one Ad Set → all
Ads, and never stores audience input. First-party Landing views/CTA/contact events
are attributed automatically per arm. Meta Ads Manager delivery enters through
CSV auto-detection, preview, matched/ignored-row confirmation, and immutable
import snapshots. Cost per primary CTA drives an informational leader only.

Studio can clone one selected approved Post into a new editable same-template
draft without AI. Approved raw assets are digest-frozen for cloning; legacy
versions fail closed if their exact raw asset is no longer present. In both Post
templates, only the background is mandatory. Every foreground group, every
Every Phone metric card and every in-phone button is
individually optional with deterministic reflow.

Migration `009_instagram_manual_validation_v1.sql` adds clone lineage, manual
Post packages, validation tests/arms/lifecycle events, and CSV import authority.
The canonical behavior is in
[`instagram-manual-validation.md`](instagram-manual-validation.md). Production
installed the additive migration from a checksummed, root-only pre-release
backup and preserved every pre-existing Commander business row. The seven new
authority tables remain empty after deployment, proving that release checks did
not create a Post, test, CSV import, provider mutation, or spend.

Acceptance passes 289 Validation tests in the release runtime image, 14 Owner
Gateway tests, 42 Commander tests with seven expected local environment skips
plus the Commander demo, 95 Owner web tests and the production build, all 84
desktop/360px/WebKit browser flows, the disposable PostgreSQL migration and
idempotency rehearsal, Python compilation, deterministic Studio visual audit,
canonical skill verifier, whitespace checks, live dependency/resource/OOM
audits, and approved-Post route/data reconciliation. Fresh provider jobs 887–895
all completed on attempt 1, including Product Brief/revision, both Post
templates, compact Landing composition, both learning modes, image generation,
image enhancement, and Pexels.

The first in-place attempt was rejected after healthy cutover because the
approved-Post release canary still requested retired `/ads`; the outer publisher
restored every prior image and both Hosting sites. The canary now requires
`/instagram` and `/instagram-tests`, with a static regression. A second attempt
was rolled back after isolated compact-Landing job 886 reached its bounded
provider deadline; a schema-bound dependency audit passed before the single
permitted fresh retry. The accepted retry passed all provider work, migrations,
authority and server audits. Its outer Owner gate then withheld Hosting because
12 old browser expectations still named Ads/TikTok and the previous fixed-logo
contract. Those tests now cover manual tracked packages, Instagram tests and
optional foreground components; the final clean preserving release runs the
complete 84-case suite and publishes the audited Owner Console. At no point did
the release reset data, activate advertising, create a Meta/TikTok object, or
send a Telegram message.

## Earlier accepted production history

## Meta Creative reconciliation and app-mode guard — live and accepted

The owner's next Website deployment reached Creative after creating PAUSED
Campaign `120251775220490671`, PAUSED Ad Set `120251776379740671`, and uploading
the exact approved image. It then failed because Graph API v26 rejects the
Campaign-style exact-name `filtering` expression on the Ad Account's
`adcreatives` edge. Read-only production calls proved that the unfiltered edge
succeeds with no matching PTW Creative while the filtered edge returns HTTP
400/code `100`; Campaign, Ad Set, and Ad filters remain accepted.

The deployed adapter reconciles Creative names across bounded cursor pages without
using Meta's full credential-bearing next URL, retains duplicate detection, and
adds a production-shaped regression that rejects the old filter and exercises
the complete Website staging path through a final PAUSED Ad. The exact saved
Creative payload also received a non-mutating provider validation. It exposed a
separate external gate: code `100`, subcode `1885183`, because **PTW Local Ads**
is still in Development mode. Backend and existing-history UI now explain the
Meta App Dashboard → Live action and label the same-deployment retry explicitly;
the generic retry is no longer presented for this condition. Owner cache v14
forces installed consoles to load that corrected action.

Production retry and real Creative/Ad readback must wait until the owner switches
the Meta app to Live. The existing Campaign and Ad Set remain provider-verified
PAUSED, the image hash remains saved, and no activation or spend occurred.

The preserving release accepted Validation image
`meta-creative-recovery-20260914-9ca2243` after all 281 tests in its real
Linux/amd64 image, nine live bridge/media jobs, Pexels, dependency, resource,
authority, approved-Post, and one-GB server audits. The final UI release
`meta-creative-ui-final-20260914-31ff9ab` published Firebase Hosting version
`176cfad6c2db2878`; 104 component tests and all 87 desktop/360px/WebKit browser
flows passed. Live audit confirmed entry `index-DOiPzgwa.js`, app
`App-D27qEzyf.js`, cache v14, healthy Gateway, protected-route 401s, and CORS.
The saved deployment still has exactly three stage records, no retry/control
record, no Creative/Ad ID, and the same uploaded image hash.

## Meta Ads creation feedback and live budget guard — live and accepted

Production diagnosis for the Natal Website request found one PAUSED Campaign,
then an Ad Set failure with Meta code `100`, subcode `1885272`. The immutable
audience preset stored `200` UAH minor units (₴2.00), while the live Ad Account
reported `min_daily_budget=4491` (₴44.91). Exact non-mutating Ad Set validation
failed below `4491` and passed at `4491`; the deployment therefore never reached
image upload, Creative creation, or Ad creation. The generic `New Traffic Ad`
shown in Ads Manager is a separate manual draft, not the PTW deployment.

The candidate reads and exposes Meta's current minimum, rejects a stale low
preset before reserving a new deployment, and offers a copied immutable preset
at the compliant minimum. Budget-subcode failures explain the correction and
cannot retry the unchanged request. The Ads action now shows a local request
acknowledgement, live per-object progress, approved-render digest, frozen Landing
URL, and an exact deepest-object Ads Manager link once Meta IDs exist.

Owner polling is serialized and waits for each response before scheduling the
next. Slow responses are no longer invalidated by later interval ticks, and a
verified connection is reused during quiet status refreshes. The latest outcome
is visible at the top; healthy setup diagnostics collapse; a request review
shows the exact image, Landing, audience, and PAUSED safety contract; and a
five-step tracker gives one next action while keeping IDs/digests secondary.
Local verification passes 279 Validation tests, 14 Gateway tests, 40 Commander
tests with five expected isolated-container skips plus the demo, 103 Owner web
tests and the production build, all 84 desktop/360px/WebKit browser flows,
both disposable PostgreSQL journeys, Python compilation, the canonical skill
verifier, and whitespace checks.

The first preserving pass replaced only Validation and passed fresh bridge jobs
855–863 on attempt 1, Pexels, dependencies, resources, authority preservation,
and approved-Post access. The outer publisher correctly withheld Owner Hosting
because one full-suite Ads test still expected the prior blocked-setup heading.
The correction keeps unavailable setup expanded as **What is still needed** and
healthy setup collapsed as **Meta setup**. The complete 84-case browser gate then
passed; the second preserving pass reused every container and published Owner
Hosting version `66a5b23c6fa82191`. The live audit resolves entry bundle
`index-CI89oYRI.js`, App bundle `App-BKfd4HLT.js`, cache v11, Gateway health,
private-route rejection, CORS, and the required UI contract.

Production PostgreSQL retains all three historical Meta deployment requests; the
latest remains the original 2026-09-14 08:33 UTC failure. Campaign
`120251775220490671` remains PAUSED, and the request still has no Ad Set, image
hash, Creative, or Ad. No Meta deployment/control record was added during the
release, and no retry, activation, data deletion, or spend change occurred.

## Analytics-driven Creative Skills — live and accepted

The accepted release removes every active Post/Landing Save and
Approve learning call, dialog, retry/recovery route, and deployment blocker while
preserving the historical tables and immutable edit checkpoints. Save now saves;
Approve saves and versions. Neither can create or activate a rule.

Migration `008_analytics_creative_learning_v1.sql` adds immutable Instagram/
TikTok insight snapshots, cookieless Landing events with 90-day raw retention,
indefinite daily rollups, opaque publication attribution, digest-bound safe
visual descriptors, frozen performance-learning datasets, reviewed decisions,
and typed Project/global Creative Skill snapshots. Analytics supports selected
Project and All Projects scopes, 7/30/90/all-time views, organic/paid/funnel
sections, readiness/freshness, leaderboard, learning curve, and full rule
editing/tombstones. Performance candidates never activate automatically.

Future Post and Landing generations record the exact active Project/global skill
snapshot IDs and digests. Global rules accept spirit principles only; Project
rules accept UI/copy/image/domain families and are subordinate to the approved
Brief and live catalogs. The public Landing shell sends only bounded
`landing_view`, `primary_cta_click`, and `contact_click` events; Meta Pixel stays
separately consent-gated. Instagram insights and TikTok `video.list` readiness
are independent from publishing. TikTok photo Analytics remains unavailable
until its audited real public-post canary.

The companion bridge release replaces the retired `studio_edit_learning`
mode with `creative_performance_learning` and `creative_visual_analysis`, and
adds one ephemeral, digest-checked approved-PNG attachment for visual analysis.
The bridge never persists those PNG bytes in a job and advertises its
multimodal mode explicitly.

Canonical contracts, metric definitions, privacy, precedence, failure behavior,
and rollout gates are in
[`analytics-and-creative-learning.md`](analytics-and-creative-learning.md).
The accepted release passes 45 companion-platform tests, the disposable PostgreSQL migration/idempotency
rehearsal, 276 Validation tests, 14 Owner Gateway tests, 40 Commander tests with
five expected isolated-container skips plus the demo, 101 Owner web unit tests and its
production build, eight public Landing unit tests and its production build, all
84 Owner desktop/360px/WebKit browser flows, all 20 public Landing browser
flows, the Studio deterministic visual audit, and the canonical skill verifier.
Analytics has no horizontal overflow and never activates a rule automatically.

The first rollout stopped before migration when the Codex CLI rejected open
nested objects in the performance-learning output schema. Recovery restored the
accepted PTW/platform source, mounted skills, six prior images, and both Hosting
sites; migration count remained six. The corrected schema closes every object
recursively and passed the exact CLI boundary before the one permitted retry.
Fresh bridge jobs 845–853 then completed on attempt 1, including performance
learning, visual analysis, generation, and exact-reference enhancement.

The accepted in-place rollout applied additive migrations 007 and 008, preserved
every pre-existing Commander business row and five immutable approved PNGs, and
left all six release services healthy. Live acceptance recorded one real
cookieless Landing view and one immutable rollup, refreshed the existing
Instagram publication into one insight snapshot, and exposed both through the
Analytics workspace. Instagram/TikTok publication, Meta deployment, control,
and stage-run counts remained `1/0/2/0/5`; no post or ad was created or changed,
and no spend occurred.

## Modular Instagram and TikTok publishing — live and accepted

Instagram is now behind a provider-neutral publishing engine while retaining its
legacy request/response aliases, tables, IDs, graph lineage, and public media URL.
The matching `/api/v1/tiktok` family adds pinned `@natal_cast` OAuth, encrypted
rotating tokens, fresh creator snapshots, explicit compliance controls,
server-derived AIGC, Direct Post photo publishing, status reconciliation, and a
non-replayable uncertain boundary around `content/init`. Migration
`007_tiktok_publication_v1.sql` keeps TikTok authority separate and additive.

The Owner Studio uses one reusable publishing shell with provider field
descriptors. TikTok remains disabled until client credentials, its exact callback,
verified media prefix, owner authorization, and audit state are configured. No
real TikTok post has been sent; public acceptance still requires one owner-selected
approved Post to publish successfully to `@natal_cast`.

## Meta campaign control and preset recovery — live and accepted

The next additive release repairs Ads preset recovery: the Owner Console rejects
invalid name, geography, age, and daily-budget fields before sending a request;
the Gateway and Validation return a bounded `invalid_preset` envelope with safe
field detail for a rejected request. Numeric entries such as `20`, `035`, and
`0200` normalize to integer values before submission. Owner cache generation is
v10.

The candidate also adds PTW-lineage-only Meta lifecycle control. Original
deployment, audience, and creative specifications remain immutable; proposed
control actions, live snapshots, 7-day KPI insights, and recommendations are
append-only authority records. Controls are reviewed first and then explicitly
owner-confirmed, revalidate immediately before execution, serialize by Project,
and reconcile uncertain provider outcomes by known object ID. Activation,
pause, Ad Set budget/schedule, and replacement paused audience/creative flows
are available only for PTW-created objects. Insights can recommend on-target,
above-target, or insufficient data, but never change spend automatically.

Migration `006_meta_ads_control_v1.sql` is installed. The accepted serial release
created a root-only checksummed PostgreSQL backup, proved every pre-existing
business row unchanged, and passed all nine live bridge canaries, Pexels,
schema, dependency, skill, 1 GB resource, approved-Post, Owner unit/build, all
81 desktop/mobile/WebKit flows, Firebase publication, and the live Owner audit.
Commander, Validation, Owner Gateway, and all three platform services run tag
`meta-control-20260913-b8ae473`; the dedicated GOD, Plan, and release services
remain on their previously accepted image. Owner Hosting version
`6c0c21b898ee88ad` is live with cache v10.

Two guarded attempts stopped safely before acceptance. The first rejected old
platform archive tags before cutover. The next exposed the serial deployer's
obsolete single-application-tag assumption after accepted selective releases;
the corrected rollback now preserves Commander, Validation, and Gateway image
lineage independently. A later post-migration check tried to normalize the
unchanged dedicated GOD service to the Validation image; it rolled back all
application and platform images while retaining the additive migration and an
unchanged authority fingerprint. The accepted correction leaves GOD untouched.

No Meta campaign was activated and no spend occurred during release. The owner
can now select an approved Website deployment and separately confirm the first
bounded activation and later pause from PTW.

## Unified Commander workspace — live and accepted

Live native model discovery, Plan questions/answers, targeted Build replies,
in-flight steering, alternate model/effort selection, cancellation and restart
recovery pass. The accepted candidate includes the preserved Phone Metrics
hero-title formatting and optional CTA controls. The bootstrap preserving
release passed all nine fresh structured/media provider canaries, Pexels,
schema, dependency, resource, approved-asset and data-preservation checks. It
then passed 95 Owner unit tests, the production build, all 81 desktop/360px/
WebKit flows, Firebase publication and the live Owner audit.

Rollout testing corrected disposable-database readiness to query the fully
initialized target over TCP, isolated the binary artifact stream from helper
stdin, and added explicit accepted skill-permission repair after recovery Git
checkout. Hosted preparation now retains full Git ancestry so a rollback cannot
block the next Deploy by hiding the accepted base. These guards have focused
regressions, with 38 Commander tests (container-only cases run separately).
Combined candidate checks pass
248 Validation tests, 95 web unit tests, 13 Gateway tests, all affected Phone
Metrics and Commander browser flows, and the authoritative Studio visual audit.
The combined source preserves the independently accepted Meta LPV update. Owner
cache v9 is installed. Release bookkeeping now reconciles an exact candidate
that was accepted through the bootstrap operations path and distinguishes it
from both a genuinely failed rollout and a live rollout awaiting source
promotion.

The final documentation-only acceptance was initiated with the one-click
Deploy action in the same Commander conversation. It uses the immutable
accepted-base request branch, candidate branch, CI verification, restricted
receiver and durable timeline record without rebuilding or restarting an
unaffected service. This is the normal path for subsequent GOD-mode changes.

The owner-authorized redesign is published through the preserving operations
release. Commander has its own route and navigation,
Markdown timeline, history drawer, reply targets, persistent drafts, inline
questions and a composer with native Plan/Build, runtime models and efforts.
Send steers active work; UUID reconciliation handles retries and completion
races. SQLite migrations retain old conversations without a 30-turn cutoff.
Native app-server history is ephemeral; questions/answers, settings and release
links survive restart. Production Codex is pinned to tested standalone 0.147.0.

Both explicit chat deployment and one-click Deploy create the same durable
owner-message-linked handoff without a second confirmation. Candidate and
accepted-base request branches separate new source from the trusted release
workflow. Infrastructure is eligible; migrations use ordered checksums,
backup-bearing disposable rehearsal and declared transformation/compatibility
checks. The accepted receiver owns recovery through Hosting/configuration
acceptance and records rollback or recovery failure durably. Plan has a separate
token and a read-only checkout; coding workers retain no publishing keys.

Verification so far: 241 Validation tests, 13 Gateway tests, 94 web unit tests,
81 desktop/360px/WebKit flows, Commander tests/demo, skill verification and
production build. The Linux/amd64 GOD image passes Commander and runtime tests;
the stock Commander test image lacks Git, so Git-bearing contracts are tested
in that built GOD image. A real Codex canary passes model discovery, native Plan
question/answer and targeted Build continuation. The OS rejects Plan checkout
writes; the real migration runner passes disposable idempotency, transaction
rollback and checksum-tampering checks. Pending hosted Phone Metrics edits have
been preserved separately and must not be overwritten during bootstrap.
The real receiver also passes five isolated-container scenarios with simulated
services: success, pre-cutover failure, post-cutover rollback, infrastructure
failure, and explicitly failed recovery with retained artifacts.

## Natal Meta Pixel measurement — live and verified

The dedicated public Landing shell now covers the apex and every `ai|la|wa`
route with one Meta Pixel integration. Pixel `1056720310312959` is owned by the
production UAH Ad Account and named `Natal Service Website`. The browser makes
no Meta request before an explicit visitor choice; Allow loads Meta's canonical
browser library and records one `PageView` for the current route, while Reject
persists the choice without initializing the Pixel. A fixed responsive consent
panel covers the English umbrella and uses the published Landing language when
available. The public Firebase CSP permits only the required Meta script,
measurement image, and connection origins in addition to the existing public
API boundary.

Verification passes eight public-shell unit tests, the production TypeScript/
Vite build with bundle markers for the exact Pixel ID and library, and all 20
desktop/tablet/mobile WebKit browser flows. The browser acceptance proves zero
Meta requests before consent and an external Meta request after Allow. Preserving
release `4bf3c92` changed no application container, retained every health and
authority check, and published Firebase public-Landing version
`7daa02c978069292`. The apex audit and real headless-browser checks passed on
both `/` and `/la/natal-service`: each sent zero pre-consent Meta requests, then
loaded the exact Pixel and contacted Meta after Allow. The Pixel remains listed
under production Ad Account `509909256695612` without exposing its token.

## Landing-page-view Ads automation — verified candidate

PTW Website Ads now freeze the current published Landing URL and create
OUTCOME_TRAFFIC / LANDING_PAGE_VIEWS / WEBSITE structures with native Learn more,
impressions billing, and the Natal Service Website Pixel attached as the Ad's
offsite-conversion tracking source. Campaign, Ad Set, and Ad remain PAUSED. The
Ads workspace displays the exact Pixel and blocks Website staging when it is not
assigned to the configured Ad Account.

The paid configurator no longer treats the Ad Account `promote_pages` response as
the assignment authority. It verifies the system user's Ad Account and Page,
the Page-to-Instagram binding, and the Ad Account's Instagram actor separately,
matching Meta's actual asset assignment model. The final candidate passes 245
Validation tests, 34 Commander tests (five expected container-only skips), 94
Owner unit tests, 15 affected Playwright desktop/mobile/WebKit flows, the
production web build, the Commander demo, and skill verification. Deployment
and one real PAUSED Meta structure remain pending. The first preserving rollout
was correctly rejected when its external image-enhancement canary failed; the
deployer restored the prior healthy Validation image and retained the previous
authoritative deployed revision. One guarded full retry remains allowed.

After the corrected helper saved the production secret, the live connection
still reported `configured: false`. The host directory/file use the intended
GID 10001 and restrictive modes, but the Validation image assigned its service
user GID 999, preventing traversal of the read-only bind mount. The live image
makes UID and GID 10001 explicit and locks that cross-file contract in the
release tests. The Linux/amd64 candidate reports identity `10001:10001`,
reads a synthetic root-owned mode-440 secret through the intended directory
permissions, and passes all 11 Instagram publication plus both configurator
tests. Preserving release `84dfd6a` restarted only Validation and passed every
provider, resource, authority, database, and approved-asset check. The live
process reports `configured: true`, `verified: true`, `media_ready: true`, and
the expected Natal Service Instagram actor without exposing the token.

The first live Page-discovery correction exposed a second configurator defect:
curl expanded Meta's nested `{id,username}` field expression and therefore
discarded the linked Instagram object even after matching the correct Page.
The live follow-up disables curl URL globbing and adds a regression at the
actual command boundary. The failed hidden-prompt attempt wrote no secret; the
existing token and Meta assignments remain valid. All 231 Validation tests, 24
Commander checks plus the demo, canonical skill validation, shell syntax,
compilation, and whitespace checks pass. Both configurator tests also pass in
the actual Linux/amd64 Validation candidate image. Preserving release `dff9d6d`
completed in 41 seconds with no service restart; all audits passed and the
deployed helper contains the required `--globoff` option.

## Meta system-user Page discovery fix — live and verified

A fresh Meta system-user token can list the assigned Natal Service Page and its
linked professional Instagram account through `/me/accounts`, but the previous
organic configurator followed with a direct Page read that Meta rejects with
HTTP 400. The old example Page ID was also stale. The live fix uses the
successful discovery boundary for configuration and runtime verification,
requires `pages_show_list`, and records the current Page ID without storing any
token or paging cursor. All 231 Validation tests, 24 local Commander checks plus
the demo, canonical skill validation, shell syntax, compilation, and whitespace
checks pass. The actual Validation candidate image passes all 11 Instagram
publication tests and both configurator tests. The generic Commander image
passes 23 of 24 checks; its sole git-dependent planner check cannot run because
that older image lacks `git`, while the same check passes locally. Production
was released through the preserving path at revision `3dee45b`; only Validation
restarted, all release canaries and audits passed, and the approved asset and
database checks remained intact. The later configurator and container-identity
corrections now make the saved production credential readable and verified.

## Studio manual preview and optional CTA — live

Both Post templates now wait for **Update preview** before rendering draft field
changes. Pending edits and failed requests retain the last successful image;
request-state tracking labels edits made during a render as not yet previewed.
Phone Metrics v25 accepts empty CTA copy and omits the entire blue CTA band,
including through Save, Approve, and reload. Preview itself remains read-only.
Owner cache v7 delivers the new controls to installed consoles.

The preserving release `studio-preview-20260910-ce8706f` completed in 493 seconds,
replacing only Validation and publishing Owner cache v7. All nine fresh provider
canaries, Pexels, authority preservation, dependencies, resource checks, and three
immutable approved PNGs passed. The actual affected Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b` changed from HTTP 400 to HTTP 200 for
empty-CTA preview. A rejected incomplete headline followed by a corrected request
also recovered to HTTP 200. Its saved state digest and three immutable versions
are unchanged; hiding CTA changes no upper-canvas pixels.

Verification passed all 229 Validation tests locally and in the Linux image,
24 built-image Commander tests and demo, 93 Owner unit tests/build, 81 full
browser flows across desktop/360px/iPhone WebKit, canonical skills, whitespace,
and authoritative PNG geometry/pixel checks. The live Owner bundle is identical
to the built artifact and includes both new controls. Hosting version
`dc2a438482dc7d21` is live.

## Mobile GOD deployment — live

Hosted Settings now exposes **DEPLOY NEW CHANGES** after a GOD coding turn. A
second confirmation freezes the exact candidate, retains its request UUID, and
shows queued/running/success/failure state across reloads and service restarts.
The coding runtime still has no GitHub key, VPS SSH key, Docker socket,
production environment, database, or deployment capability. A separate 128 MB
controller shares only the isolated checkout, deployed-revision marker, private
state, and a repository-scoped candidate-push key. Cross-container file locking
prevents a coding turn and release snapshot from racing.

Candidates containing migrations, CI/workflow files, deploy scripts,
Dockerfiles, Compose, or other privileged operations paths are rejected. The
public-repo GitHub runner runs the complete Python, web, browser, skill, and
whitespace gates, builds selective Linux/amd64 artifacts off the 1 GB VPS, and
reaches production only through a dedicated `ptw-release` SSH key whose forced
command is the preserving receiver. The receiver independently revalidates the
deployed base, candidate ancestry, protected paths, checksums, plan, maintenance
lock, authority snapshot, rollback, health/dependency/resource checks, and final
revision. Hosting bytes are built off-server and deployed with the existing
root-owned service account; only its Firebase Hosting IAM role was added, and no
Firebase credential enters GitHub.

Production acceptance passed in 146 seconds. The selective rollout reused
Commander, Validation, and all platform images; started the release controller;
replaced only Owner Gateway and hosted GOD images; and published Owner cache v6.
The live private controller reports a configured empty candidate, its public
Gateway route rejects unauthenticated access, both controller and GOD mounts are
free of the Docker socket, GOD cannot see the repository key, and the live lazy
bundle contains the mobile control. An attempted arbitrary command through the
CI SSH key was rejected by the forced receiver. Verification passes: 89 Owner
unit tests/build, 81 full desktop/360px/iPhone WebKit flows, 18 built-GOD chat
and release tests, 12 Gateway tests, 24 Commander/release tests, the Commander
demo, canonical skill validation, shell syntax, workflow YAML, and whitespace.

## Temporary GOD chat images — live

Commander conversations accept up to four PNG, JPEG, or WebP images per request,
bounded to 8 MB each and 20 MB total. The browser supports image-only requests,
mobile previews, removal before Send, and idempotent retry with the same request
UUID. Owner Gateway authenticates every upload and temporary-preview hop. Hosted
Commander decodes the claimed format, rejects unsafe dimensions or animation,
strips metadata, normalizes pixels to a bounded PNG, verifies its digest, and
passes the temporary path to Codex only for that request.

Pixel bytes never enter the Git checkout, release candidate, chat SQLite,
Firebase, or PostgreSQL. They live briefly below the private Commander state
volume and are deleted after completion, failure, Stop, timeout, launch failure,
or service restart. Chat history retains only the safe filename, size, and digest;
later turns do not receive an earlier request's pixels. The redundant GOD-mode
introductory paragraphs were removed from Settings.

## Phone Metrics optional CTA — local candidate

Phone Metrics v26 makes the full-width post CTA band independently optional.
Studio now edits its retained label, background color, text color, font, and
size; hiding the band removes its renderer node and semantic role without
discarding those saved values. Existing v8/v9 mutable drafts retain the previous
visible cobalt/white default during their one-save uplift, while immutable
versions remain unchanged. The hero title now also matches supporting text with
select-and-bold, select-and-colour, and an independently persisted word colour;
existing v10 drafts receive the default hero accent during their one-save uplift.
This candidate has not been deployed from the hosted development checkout.

## Selective release pipeline — live

The production path is canaried with a docs-only candidate that cannot change runtime behavior or domain data.
A fresh mobile acceptance run verified the corrected forced receiver after its post-rollout status fix.

The release path now plans changes from the exact deployed commit, builds only
affected Linux/amd64 PTW images in parallel, streams only those checksumed
archives, and restarts only affected services. The VPS recomputes and validates
the plan before rollout; unknown runtime paths select a full build. Commander,
Validation, Owner Gateway, and GOD persist independent image references, while
the unchanged platform is reused as one compatibility unit. Hosted GOD now has
a dedicated small image. Non-provider changes use a quick dependency audit;
Validation/platform changes retain live bridge and Pexels canaries. Unapplied
migrations still require the backup-bearing serial path. The intended ordinary
release time is 2–4 minutes and every stage reports elapsed time. Production
acceptance passed. The first Validation release completed in 7m19s end to end:
5s preflight, 43s service cutover, 351s for nine real structured/media provider
canaries plus Pexels, 14s dependency/resource audits, and 11s approved-Post and
commit verification. Cached image builds were subsecond and the resumed release
reused both verified candidate images without uploading them again. The 5–10
minute target now holds even for the most expensive Validation path; ordinary
single-component releases skip unrelated images, services, Hosting, and provider
execution.

The rollout recovered the owner's persisted Save checkpoint through the normal
domain service. Its fourth append-only learning run completed, created one
pending global proposal, and remained complete after Validation was replaced.
The privacy filter now distinguishes generic Studio vocabulary such as `logo`
from private asset provenance. The saved Creative was never rolled back or
rewritten. There are no incomplete mutable operations.

## Hosted Commander GOD mode — live and restart-verified

Settings exposes Commander in both local and hosted consoles. The hosted
contract keeps Firebase owner and App Check verification at Owner Gateway, then
uses the existing service secret to reach a private `commander-god` API. Its
root process can write only an isolated shallow clone under
`/opt/ptw/commander-workspace`; runtime environment files, the production
checkout/data, Docker, deployment, publishing, Git push, and external messaging
remain outside its mounts and execution policy. The published Codex credential
and standalone binary are read-only. Each turn refreshes `auth.json` into a
private writable runtime home. The hosted CLI uses its externally-sandboxed
execution mode because the locked-down container is the execution boundary;
local Commander retains its nested workspace sandbox. Conversations persist in
a dedicated volume, retain request-ID reconciliation, serialize turns, and mark
interrupted work without replay after restart. Production Validation still
mounts no coding routes. Owner cache v6 forces mobile clients to install the
restored Settings control.

Verification passes in the Linux image for 13 runner/API lifecycle and security
tests plus 11 Gateway tests; all 220 Validation tests, 18 Commander release tests,
the Commander demo, 88 web unit tests, 78 desktop/360px/iPhone WebKit flows,
canonical skill validation, shell syntax, production build, and whitespace checks
pass. Release `god-mode-sandbox-20260910-faf77f9` passed its preserving
deployment, provider, Pexels, dependency, resource, authority, and approved-Post
checks; Owner cache v6 remains live. A real private hosted turn read `AGENTS.md`,
reported Git HEAD `faf77f9` and a clean checkout, and made no edits. Restarting
only `commander-god` under the maintenance lock retained that completed chat and
reply, and the checkout remained clean. Hosted GOD mode is available.

## Legacy Creative Save incident — resolved in production

Three owner Save requests returned HTTP 409 before persistence because the
Creative service exposed the older stored snapshot hash over its normalized
editor hash. The deployed service now gives renderer fields precedence and uses
bounded legacy state validation. Explicit unchanged legacy Saves persist the
normalized files; GET remains read-only and genuinely stale edits still fail.
The UI places Save feedback beside the controls, focuses and scrolls to failures,
retains pending input, separates preview errors, and uses the Gateway's 480-second
deadline. Owner cache v5 is live.

The preserving rollout passed provider, Pexels, authority-preservation,
dependency, resource, and approved-Post checks. One exact unchanged Save
normalized the affected workspace; it returned HTTP 200, retained both immutable
version IDs and render hashes, and completed its learning run. A Validation
restart retained the same state, checkpoint, versions, and renders. A second
identical Save returned HTTP 200 without another checkpoint or version. The three
rejected browser drafts were unavailable in PostgreSQL and were not invented.
Local verification covered 218 Validation tests, real HTTP with disposable
PostgreSQL, 18 Commander tests and demo, 88 web unit tests, 78 browser flows, and
the deterministic Studio visual audit. See the incident log.

## Legacy Post restore compatibility incident — resolved

The full release passed provider, migration-preservation, resource and Hosting
checks, but authenticated Ads/Instagram source reads exposed a v8-to-v9 Post
configuration digest mismatch. The old snapshot digest still matches exactly;
no stored image or owner record was lost. The deployed database adapter verifies via
the existing legacy-aware validator and avoids persistence on read-only restore.
The new release canary checks actual project sources and immutable PNG digests
against PostgreSQL before either preserving deployer reports completion. Tests
cover repeated restores, original bytes/digest preservation, and tampering.
The Hosting audit also retries HTTP-200 HTML fallback responses until the entry
and App assets have JavaScript MIME. See the incident log for diagnostics.

## Instagram publishing and website Ads milestone

Approved Posts now expose a version selector, verified approved PNG preview,
editable caption, organic Instagram publication/history, and an exact-version
handoff to Website Ads. Both renderers and their promotional CTA/editor controls
are unchanged. Website ads freeze the current published Landing event/version/URL,
use Traffic / LINK_CLICKS / IMPRESSIONS / native Learn more, and create PAUSED
objects. Direct remains available with separate project/objective/category
campaign identity. Paid launch and schedules belong to Ads Manager.

Organic publishing stores a deterministic JPEG and its source/delivery digests,
serves only an expiring opaque media URL, and persists container/media identity
plus append-only attempts. Restart and uncertain publish responses never replay
media_publish. Publishing permissions are independent of advertising; approved
PNG download, copy, and external-tool handoff remain available without Meta.
Schema 005 adds PostgreSQL publication records and preserves existing Direct
records. The migration deployer now fingerprints baseline columns for every old
business table, including Landing, and rejects active publication workers.
Canonical behavior and routes: [`meta-ads.md`](meta-ads.md).

Local verification passes: 86 Owner Console unit tests and production build,
75 browser flows across desktop/360px/iPhone WebKit (Meta mocked), 217 Validation
tests in the repository environment, 10 Gateway tests, 18 built-image Commander tests
and demo, deterministic Studio geometry/colour audit, canonical
skills, and disposable migration/persistence checks. The latter exercise the
actual deployment SQL with psql variables/stdin, preserve old rows and image
bytes, and verify Direct/Website identities, publication recovery, immutable
attempts, and graph lineage. The initial runtime-image suite lacked git; its
seven git-dependent tests passed locally. The complete 216-test runtime suite
then passed with git/bash installed only in the disposable test container.
Owner cache generation is now
`ptw-shell-brief-studio-landing-ads-v4`.

Production release and the preserving compatibility hotfix are complete.
Both rounds of nine fresh generation canaries and Pexels passed, together with
authorization, dependency, resource, source-access, and Hosting audits. All prior
business rows remain unchanged. The root-only PostgreSQL backup precedes schema
005; the 24-hour resource audit is scheduled. Actual production reads verify one
Project, both immutable approved PNGs, and the current published Landing at
`https://natal-service.com/la/natal-service`. The temporary media origin is ready.
Meta credentials remain absent, so export is available but no real Instagram
publication/permalink or paused website ad has been accepted in Meta. No reset
was performed. Runtime revision: `a4af6b286ecb51f4ee07bedbb9584f1b2f511240`;
platform revision remains `630d7636be057d16b22207fc0b1eea13711b4441`.

## Preview and contact release

The full preserving release also fixes three owner-reported Post/Owner Console
symptoms. Phone Metrics now binds each PNG preview to the exact draft state and
hides stale pixels while a changed in-phone title is rendering. Recent iPhone
thumbnail loads coalesce concurrent Firebase ID/App Check acquisition and retry
one read once; live diagnosis proved all three PostgreSQL-backed PNGs and their
Validation digests were intact while no browser history GET reached the Gateway.
The Owner Hosting boundary adds `X-Frame-Options: DENY`, and its live audit now
requires enforcing `frame-ancestors 'none'`, no PTW-owned report-only CSP, and
the independent frame guard. Owner cache generation
`ptw-shell-brief-studio-landing-ads-v4` displaces the affected client bundle.
Google Identity/reCAPTCHA report-only diagnostics
remain third-party and are not grounds to weaken PTW security headers.

Landing renderer v5 adds an optional, owner-supplied direct Instagram profile
link and renders its handle with an Instagram icon. The supplied
`https://www.instagram.com/natal_service/` form is accepted; arbitrary hosts,
non-HTTPS URLs, nested paths, query strings, and fragments remain rejected.
Older Landing documents omit the field without changing their digest, and the
AI composer continues to leave every owner contact endpoint empty.

Release-candidate verification passes: 81 Owner Console unit tests and its
production build, 69 browser flows across desktop/360px/iPhone WebKit, six
public Landing tests and its production build, 193 built-image Validation tests
plus seven git-dependent local tests, nine built-image Owner Gateway tests, 16
Commander tests plus demo, the deterministic Studio visual audit, canonical
skill validation, and whitespace checks. The seven Validation-image failures
were limited to the image not containing the `git` executable and passed in the
repository virtual environment.

## Landing Save conflict incident

Production diagnosis found that Landing Save/Approve used the generic
15-second browser deadline while synchronous Landing learning was allowed 480
seconds by the Gateway. The affected page had already persisted one completed
save checkpoint and no immutable version; repeated requests from the stale
browser state then correctly returned HTTP 409. The web hotfix aligns the
client deadline with the Gateway and reads the current page once after the exact
stale-state conflict, reconciling only an exact configuration/content match and
preserving pending owner input whenever the server document differs.

Verification passes: 70 Owner Console unit tests, production build, 60 browser
flows across desktop/360px/iPhone WebKit, Commander release-contract tests,
canonical skill validation, and the authenticated-free live boundary audit.
The audit now tolerates only a bounded Firebase document/entry/lazy-bundle
propagation window and requires the incident-specific reconciliation marker.

## Post and Landing visual mode milestone

Post Phone Metrics v24 and Landing now offer **Visual mode: Phone frame &
buttons / Image only**. The optional saved `visual_mode` defaults to the existing
phone view. Post contains the complete raw artwork in the device area, keeping
surrounding copy, metrics, and CTA. Landing removes its app phone overlay and
shows the hero artwork with existing crop/placement controls. Phone settings,
content, assets, history, and immutable versions survive toggling. No generation
is needed to switch. This milestone is now deployed.

Landing's generic HTTPS/booking contact option is also replaced by a
bounded direct Telegram bot link. The persisted `url` key remains unchanged for
contract compatibility, but new validation accepts only
`https://t.me/<bot_username>` with a username ending in `bot`; the editor and
shared private/public renderer label and display it as Telegram. Email and phone
remain available, no bot handle is fabricated, and Commander's emergency
Telegram bot is not reused. This change has not been deployed.

Verification passes: 85 focused Studio and 21 Landing Python tests, 77 web
unit tests, six browser flows across desktop/360px/iPhone WebKit, deterministic
Studio geometry audit, Owner Console and public Landing builds, 16 Commander
tests in the built Validation image plus demo, skills, and whitespace checks.
The local launcher was refreshed; authenticated reads confirmed v24 and fresh
phone/image previews of the same existing Creative without changing saved state.

## Commander GOD-mode foundation

Local Settings retains ChatGPT Authorization, adds the English/Ukrainian
language switcher moved from navigation, and includes a repository-wide Commander
coding chat. The local authorization endpoints read CLI sign-in status and
support owner-initiated device login without exposing CLI output or credentials;
local status does not claim a provider test passed. The owner
can request features, fixes, new tabs, Telegram code changes, and skill updates.
It invokes local Codex against this checkout, retains conversations and turns in
`.local/commander-chat`, supports follow-up messages and Stop, and reconciles
duplicate message UUIDs. Only one coding turn runs at a time. Stop, timeout, and
API disappearance terminate the worker group; restart marks unfinished turns
interrupted without replaying edits. Already-applied edits remain reviewable.

Every turn loads the current canonical `skills/commander-god-mode/SKILL.md`
and records its digest. The agent maintains the narrowest relevant PTW skills
after verified reusable lessons, with canonical sync/validation and separation
from Product Brief, Post, and Landing learning. Missing skill disables execution.

The local milestone is deployed. The launcher enables
`PTW_COMMANDER_CHAT_MODE=1` and the corrected `VITE_LOCAL_APP=true` flag. The
runner uses a workspace-write sandbox with shell network access disabled and
does not inherit user MCP/config or provider-secret environment variables.
Local credentials plus loopback host/client/origin checks protect those routes.
The hosted extension described at the top keeps its runner in a separate private
service and checkout; production Validation continues to mount neither variant.

Local verification passes: 11 chat runtime/HTTP tests (also in the built Linux
image), seven existing Tune tests, 72 web unit tests, production web build,
three mocked browser checks across desktop/360px/WebKit, 16 Commander tests in
the built image plus demo, skill validation, and whitespace checks. A real
Codex canary created and byte-verified a file in a disposable checkout. The
refreshed local app reports the chat and canonical skill ready through real
browser/HTTP reads. Existing production release verification below applies to
the already-deployed Image Reference milestone.
## Image Reference milestone

The Owner Console now exposes one optional upload/preview/remove control next
to Post Phone Metrics and both Landing image prompts. All three reuse the shared
image-generation request/pipeline contract, with bounded PNG/JPEG/WebP decoding,
metadata removal, text-plus-image provider input, and digest-only provenance.
References never become Project assets or checkpoint/learning inputs and clear
after the operation or navigation. Existing image/history survive failed work.

Companion bridge changes store
only an ephemeral handle in job parameters, the worker consumes pixels once from
a bounded in-memory store, and its temporary files use production tmpfs. PTW
requires the advertised ephemeral capability before transmitting any reference.
The repositories retain their separate histories and deploy under one matched
versioned release tag.
See the [Post Studio contract](post-studio.md#phone-metrics)
for limits, expiry, and release ordering.

Release checks pass: the 179-test Validation suite, 9 Gateway tests, 68 web unit
tests, 33 focused browser
checks across desktop/360px/iPhone WebKit, 43 companion platform tests, 16
Commander tests in the built Validation image and demo, the deterministic Studio
visual audit, production web build, and canonical skill verification. Browser
traffic is mocked; provider/HTTP/database-write boundaries have separate tests.
The preserving rollout additionally runs fresh real structured/media and Pexels
canaries and rejects the release with image rollback if any one fails.

## Current milestone

PTW now has four project owner destinations: **Brief / Бриф**, **Post / Допис**,
**Landing / Лендінг**, and **Ads / Реклама**.
The Post destination is the project-scoped Studio creative workspace. There is
no separate Studio page and no automated Post subsystem.

An owner first creates and persists an empty Project with a manual name, then
enters the idea inside that Project to create its first Product Brief. Brief
generation never replaces the owner-entered Project name. The owner reviews the completed Brief and
approves it only after choosing one common Studio template. Phone Metrics also
requires a saved creative direction: one style and one background treatment.
The owner may reset and replace that direction in the hero editor; existing
images remain untouched until another generation. Approval returns HTTP 202 with the
idempotently reserved creative, navigates to
`?page=posts&project=<project_id>&creative=<creative_id>`, and starts
`queued → composing → generating image → draft`. The image stage appears only
for `phone_metrics`.
For an already-approved Brief, **Open or create its creative** first resolves
the Project's ordinal-1 Creative and opens it without resubmitting approval. The
template chooser remains only as recovery for the exceptional approved-Brief
state with no first Creative. The API still rejects a different template or
Phone Metrics direction for an immutable existing reservation.

Landing is a private responsive, fixed-section workspace created from a selected
immutable approved Post version and its approved Brief. It captures Post style
once, and the v5 composer AI-populates only bounded Hero/three features/app
screen/visual directions/three FAQs content. Theme, layout, presentation,
components, image styles, phone layout, routing, identity, and asset policy stay
server-owned and preserve the current workspace configuration. It leaves
owner evidence and contacts empty, then generates text-free Hero and visual-break
art. The rebuilt v4 renderer adds bundled typography, a balanced hero, benefit
cards, optional proof, bounded landscape art, an actionable contact panel, and
collapsed FAQs. The section inspector supports direct visual editing, all bounded
layout controls, crop focus, page language, and a selectable CTA destination.
One shared renderer powers 1280/768/360px and fullscreen previews. Save/Approve
shows Landing-only learning; approval requires essential copy, both visuals,
and one valid contact endpoint. Evidence is optional, complete when supplied,
and absent from Preview when empty. Approval validates before persisting state.
Every app keeps the canonical Natal logo/name. Landing adds three coordinated
page themes and bounded button, card, icon, and contact-panel styling. Each image
uses the same ten Post style presets and two background treatments; saved choices
feed automatic generation, manual generation, and exact enhancement with the
current page palette and slot-specific crop guidance.
The hero now demonstrates a Brief-grounded app task inside the same canonical
phone frame as Post Studio. Owners edit screen titles, descriptions, actions, and
three UI rows; Light/Dark/Glass themes and Overview/Booking/Checklist layouts are
independent of page and image styles. Screen choices and content save through the
existing bounded contract and immutable versions. New composition requires an app
feature screen, including for physical services. Preview selection stays local,
and the phone action uses the page CTA destination.
Landing now has a separate local publication milestone. One permanent
`ai|la|wa/<slug>` URL is reserved per Project on first Publish, and every
append-only event points to an exact approved immutable Landing version.
Republish atomically switches the stable URL, an older event is the rollback
path, and Unpublish preserves the reservation while public reads return 404.
The public snapshot/asset API exposes no internal IDs, provenance, history,
learning data, or unselected assets. It has no lead handling, forms, directory,
or Post-skill influence. The shared public shell has one consent-gated Meta
Pixel; individual Landing snapshots do not carry analytics configuration.

The dedicated `apps/landing-web` Firebase SPA imports the exact Landing renderer
in non-editing mode. Its English `/` umbrella contains no links or CTA;
`/ai|la|wa/<slug>` fetches the sanitized current snapshot. Invalid and
unpublished paths use a branded visual 404 with Hosting HTTP 200. The shell has
no Auth or service worker, ships noindex/noarchive plus disallow-all robots, and
uses self-hosted Natal assets. Named Firebase targets keep it separate from the
private Owner Console. Firebase version `185107aab38614ab` is live on both
`natal-landings-86123.web.app` and the verified apex `natal-service.com`.
The owner elected not to attach `www.natal-service.com`; the apex is the only
supported public hostname.

Ads is a separate Project workspace over immutable approved Post versions. It
creates or reconciles one Project Campaign, one Ad Set per immutable audience
preset digest, and one Creative/Ad per deployment through Meta Marketing API
v26.0. Campaign, Ad Set, and Ad are fixed to PAUSED; Instagram Feed, Instagram
Direct, engagement/conversations/impressions, lowest-cost bidding, and disabled
creative enhancements are server-owned. The owner can edit deterministic ad
copy before staging, inspect verified assets/PNG, Meta IDs, append-only history,
status/issues, and retry or sync. Every immutable approved Post appears as an
explicit Ads source card with its digest-verified preview and a link back to its
Post Studio creative. A readiness checklist separately reports the token,
permissions, Ad Account, Page, Instagram actor, and approved-Post gates. Direct
links open Meta Business Settings, System Users, App Dashboard, asset settings,
Token Debugger, and Ads Manager even while staging is disabled. There is no
activation, spend, organic post, insights, batch launch, or Facebook Page/Ad
Account creation surface.

Audience preset v2 adds an in-app Meta city search and immutable city-radius
targeting. The owner selects a verified `adgeolocation` city key and a 17–80 km
radius; city Ad Sets omit country targeting so a local service cannot
accidentally broaden delivery to the entire country. Country-only v1 presets
remain readable and stage with their original semantics.

Local Meta credentials are optional and load only from mode-600/400
`.local/local-studio.env`. Production reads an isolated root-owned mode-440
`/opt/ptw/secrets/meta-ads/config.env` mounted only into Validation. The
system-user token never enters persistence,
browser responses, or logs. Missing/wrong configuration disables staging while
the rest of PTW remains usable. Current local secrets contain no Meta variables,
and the production Meta secret file is absent, so both connections report the
intended safe disabled state. The real PAUSED canary has not run and no Meta
objects were created.

The lower owner navigation includes a compact Settings control; language selection
now lives inside Settings.
It opens a dedicated `?page=settings` destination rather than a dialog over the
Brief. Its ChatGPT Authorization card returns only an authorization status and, during
an owner-initiated device login, the official device URL/code. A private
root-owned `codex-auth` service updates the existing Codex CLI store and runs a
working test request before marking the status authorized. It keeps the primary
credential root-only and atomically publishes a separate group-readable copy
through a dedicated read-only worker directory mount, so a Codex file replacement
cannot leave the worker pinned to an old inode. No access/refresh token,
auth-file content, or CLI output reaches the web API, frontend, or logs.

Every owner-visible API and persisted background failure uses one localized
four-part contract: outcome, plain-language explanation, the next safe action,
and bounded technical context. A successful list/detail read does not hide an
item whose stored state is `failed`. Raw provider and server output never reaches
the owner; failed Brief, Studio, phone-image, Landing, and Landing-learning work
remains explicitly retryable.

All structured local and production generation paths require a deterministic
domain validator; schema-only acceptance is prohibited. A canonical request
fingerprint binds idempotency to mode, model, the complete system prompt, input,
output schema, prompt version, and referenced artifact digests. The key is
bounded without discarding collision resistance. This prevents a changed
contract, prompt, model, input, or image from replaying an older successful job.
Image generation and exact-reference enhancement use the same rule. Only a
completed response rejected by domain validation may receive one correction;
transport, timeout, cancellation, CLI, and provider failures remain on their
original attempt. Recovery clears stale current errors but retains append-only
failure history.
Every structured request also enforces a local 512 KB prompt/input/schema
contract budget before submission and records only per-part byte counts in
provenance. Landing uses a stricter release budget, a shared runtime/canary
payload builder, a maximum of eight recent global and eight recent Project
lessons, frozen Post copy without its configuration/assets, and no live catalog
in the prompt. Complete append-only lesson history remains authoritative.
Validation serializes bridge submissions to the single production worker. The
worker execution timeout is bounded below the client deadline so a queued
parallel request cannot exhaust its deadline before execution starts. Repeated
Landing deadline failures at both 300 and 360 seconds proved that timeout growth
was not a safe remedy; promotion now requires the compact content-only contract
to finish on fresh attempt 1.
The bridge worker also pins the server-owned reasoning effort to `low` instead
of inheriting an ambient CLI default; strict domain validation, not unbounded
reasoning time, determines acceptance.

Normal backend releases use `scripts/deploy_ptw_preserving.sh`. It refuses an
active mutable operation, requires six matching versioned Linux/amd64 images and
exact repository revisions, snapshots every authoritative database row, runs
domain canaries and audits, and persists release tags only after the snapshot is
unchanged. Any incomplete exit restores the prior application and platform
images plus their persisted tags. This path never invokes the separately
confirmation-gated destructive reset, and it refuses any unapplied migration so
the backup-bearing in-place gate cannot be bypassed.

Migration-bearing data-preserving releases additionally use the confirmation-
gated `scripts/publish_ptw_in_place_serial.sh` entrypoint with exactly
`DEPLOY PTW IN PLACE`. It deploys the public shell first, then creates a
root-only checksummed PostgreSQL backup, fingerprints every existing business
row while writers are stopped, applies migration 004, proves preservation, and
cuts services over serially. `RESET PTW PRODUCTION` remains a mutually exclusive
destructive path. Domain transfer, DNS edits, and old-site disablement remain
separately authorized operations. All Compose one-offs disable TTY/stdin. Both
inner and outer cleanup paths cover shell errors and termination signals,
re-fingerprint authority after rejected deployment, restore and verify all six
prior image tags plus persisted tags, and reject active mutable work before the
backup window.

A replacement Brief creates a separate first creative. Another creative from
the same Brief is available only after the latest creative has an immutable
approved version. Cross-Project creative access fails closed.

## Studio authority

The Post template registry contains only `phone_metrics` at 1080×1350. Unknown
or retired IDs fail at the registry boundary and have no compatibility renderer.

Phone Metrics exposes independent visibility toggles for its canonical
upper-left and in-phone Natal lock-ups. Both are shown by default and remain
renderer-owned, so owners can omit either mark without replacing its artwork.

The template exposes an independent bounded font-family and font-size control
for every editable semantic text role. The catalog provides Inter, Roboto
Condensed, Manrope, Montserrat, Source Sans 3, Oswald, Cormorant Garamond,
Cormorant Garamond Italic, Lora, and Lora Italic. Renderer-owned phone chrome,
Natal artwork, and system UI text remain fixed; only the two Phone Metrics logo
visibility states are owner-tunable.

Each creative stores Project and approved-Brief lineage, ordinal, selected
template version/digest, current bounded state, generation provenance, assets,
checkpoints, and immutable versions. Templates remain common code; creatives do
not copy or modify template implementations.

PostgreSQL is the complete production authority. It stores project-scoped
creative metadata, digest-checked renderer files and PNG bytes, append-only
generation runs, immutable edit checkpoints, append-only learning runs,
learning proposals/decisions, and immutable global/Project skill snapshots.
Explicit graph edges connect Project, Brief, creative, asset, version,
checkpoint, run, and skill entities. The local authority provides the same
contract with append-only metadata below `.local/owner-briefs` and
per-creative renderer files below `.local/studio-workspace/creatives`.

This is a clean baseline plus Landing and Meta Ads extension schema. Migrations
`001_ptw_brief_v1.sql`, `002_ptw_landing_studio_v1.sql`,
`003_ptw_meta_ads_v1.sql`, and additive `004_public_landing_v1.sql` exist. Old singleton Studio rows,
assignment flows, schema adapters, bare mutation routes, and historical Post
tables are not accepted or migrated. `/api/v1/posts` and bare
`/api/v1/studio` remain absent.

## Studio agents and performance learning

Composition uses the approved Brief, selected live template catalog, canonical
composer skill, and current typed Project/global Creative Skill snapshots. The
live catalog and Brief remain higher precedence, and every generation records
the exact snapshot IDs and digests. Output is validated against the selected
template's exact configuration/content shape. Renderer-owned numeric bounds,
enums, colors, typography, device limits, Landing content lengths, and
privacy-sensitive blank fields share constants with runtime normalizers. A
changed contract cannot replay a response from an older schema.

Save and Approve now persist only changed checkpoints and immutable versions;
they make no learner call. Performance learning starts explicitly from Analytics,
freezes its dataset, and returns inactive typed candidates for owner review.
Release acceptance covers both Brief modes, the active Phone Metrics Post and
its manual Agent, Landing composition, performance learning, safe visual analysis, new image
generation, and exact-reference enhancement. Every structured canary must pass
domain validation on fresh attempt 1 and report a valid byte budget.

For `phone_metrics`, composition automatically starts a fresh, text-free hero
generation governed by `studio-phone-hero-generator`. The prompt includes the
saved creative direction, a Brief-derived subject description, and active typed
global/Project Creative Skills. The direction remains available to a future
legend generator, which is not yet implemented.
A complete bounded prompt may contain up to 9,000 characters so the maximum
subject, selected style/background, enhancement rules, canonical skill, and
accepted lessons fit the same provider contract.
A failure keeps a deterministic editable draft and exposes a separate retry.
Manual generation can create a fresh image or enhance the exact selected raw
hero. The three newest raw hero images remain digest-checked and selectable.
Legacy Phone Metrics drafts retain their existing hero but must save a direction
before further generation, enhancement, or retry. The saved direction can be
reset from its edit icon and replaced without creating learning data.

Intermediate template, configuration, content, import, asset, generation,
enhancement, and selection edits accumulate without learning. **Save creative**
or **Approve creative** creates one immutable checkpoint only when state changed;
no-op saves are idempotent.

The candidate bridge contract has five structured modes: `product_brief`,
`product_brief_revision`, `studio_creative_generation`,
`creative_performance_learning`, and `creative_visual_analysis`. It retains one
bounded `content_non_human_graphic_generation` media mode. Production still has
the previous contract until the separately gated bridge-first rollout.

## Verification status

The production Studio Save/Approve HTTP 400 incident was traced against Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b`. Requests at 2026-09-09 08:39–08:41 UTC
crossed the durable workspace boundary before response finalization: PostgreSQL
contains two immutable versions with the same state/render digests and two
checkpoints, while the workspace row retained a null latest checkpoint. The
Database authority rejected the service's derived `approved_version_count`
patch because that count is selected from immutable version rows rather than
stored on the workspace row. The earlier complete HTTP/domain workflow used the
loopback authority, and the database-workspace test stopped at direct version
persistence, so neither crossed this production adapter finalization seam.
The correction makes the database adapter accept-but-not-store the derived
field, adds an adapter-specific regression, and compares normalized draft data
before approval so an uncertain semantically identical retry cannot append
another version. The existing duplicate immutable records remain append-only
incident evidence and are not deleted.
The first preserving rollout was correctly rejected after candidate restart
recovered the two queued checkpoints, appending learning authority and touching
the restored workspace cache. All six prior images and persisted tags were
restored and verified. The deploy preflight now rejects any Studio checkpoint
without a completed learning run, so restart recovery must finish on the current
release before an authority snapshot and a fresh rollout.

The restarted preserving rollout passed a byte-identical Commander authority
snapshot, fresh attempt-1 bridge jobs 572–580 for both Brief modes, both Post
templates, Landing composition, both learning paths, new image generation, and
exact-reference enhancement, plus Pexels, schema, dependency/auth/worker, skill,
and 1 GB resource audits. All six services run
`studio-approval-20260909-59be4a3` and are healthy. One authenticated internal
HTTP reconciliation of the original Approve action returned 200, reused completed
checkpoint `01a08553-b1b5-77a4-b470-2473b94242f3`, returned
`version_created=false`, and kept exactly two versions. A subsequent Validation
restart retained both version IDs and every state/render/version digest, kept the
same latest checkpoint, and left zero queued learning and zero active creatives.
The public approval route returns 401 rather than 404 without credentials; the
live Hosting/Gateway/CORS/PWA audit passes with no unexpected post-cutover 4xx,
5xx, traceback, or service error. The two duplicate versions created during the
incident remain immutable evidence.

Release verification passed 181 clean Validation tests, 16 built-image Commander
tests and the demo, 68 Owner Console unit tests, 60 desktop/360px/iPhone WebKit
browser checks, the production build, four-migration disposable PostgreSQL
idempotency/preservation, the deterministic Studio visual audit, canonical skill
verification, shell syntax, and whitespace checks.

The Phone Metrics direction-save incident was reproduced against production
Creative `01a07f55-20a5-755c-bbec-17a3f158ef4b`: Owner Gateway logged the exact
`POST .../creative-direction` as HTTP 404 at 2026-09-08 14:39:50 UTC, while the
same internal Validation route returned its expected unauthenticated HTTP 401.
The Creative remained a draft with its existing selected image and direction;
the rejected public request changed no authoritative row. The cause was a
missing public Gateway proxy, hidden by browser tests that mocked every API
request. The fix adds that authenticated proxy, exact Gateway/Validation
GET/POST route parity, body/token/actor forwarding coverage, a live 401-vs-404
route-registration audit, a complete Phone Metrics browser/UI workflow on
desktop/360px/iPhone WebKit, and a real HTTP/domain workflow covering auth,
idempotency, stale state, invalid input, cross-Project isolation, generation,
enhancement, history, selection, Save/learning, approval/version, and restart
persistence. The canonical incident skill now forbids calling fully mocked
browser traffic complete system E2E and makes these boundaries release gates.
PTW revision `0ec8445e40958a059ee1f029264c6a7017dc31e7` is deployed as
backend release `creative-direction-20260908-0ec8445`. The first preserving
candidate was correctly rejected when exact-reference provider job 531 failed;
the authority snapshot stayed byte-identical and all six prior images and
persisted tags were restored and verified. A fresh known-good-stack canary then
passed jobs 532–540, and the restarted preserving rollout passed fresh jobs
541–549 for all structured modes, both Post templates, Landing composition,
both learning paths, new image generation, and exact-reference enhancement.
Pexels, ChatGPT/Codex authorization, the schema-bound worker, dependency, skill,
and 1 GB resource audits also passed. All six services now run the one new tag
and are healthy; the live public route-registration probe returns HTTP 401, with
zero post-cutover direction-route 404s. The affected Creative still has state
digest `b68f5ff2391aa206e4a7632c5b924be337c0e965d24e561411228c8e80872685`,
the same saved `minimal_sculptural` / `isolated_key_element` direction, one
asset, zero versions, and the same five append-only generation runs. The
follow-up resource timer remains active with a concrete next elapse.

Release verification passed 169 Validation tests; 8 Owner Gateway tests; 16
Commander tests and the demo; 67 Owner Console unit tests; 57 desktop, 360px,
and iPhone WebKit browser/UI checks; all 39 platform tests; the exact Phone
Metrics workflow in the Linux/amd64 Validation image; the Studio geometry/pixel
audit; four-migration disposable PostgreSQL idempotency/preservation; canonical
skill validation; Python compilation; shell syntax; and whitespace checks.

The approved-Brief reopen conflict was diagnosed against production Brief
`01a07c66-b00a-7ffe-a44f-a5fd2d738515`. Four owner requests returned HTTP 409
at 2026-09-08 13:40:53, 13:41:01, 13:57:57, and 13:58:27 UTC because the Brief UI reopened a blank
template/direction chooser even though its ordinal-1 Phone Metrics Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b` already existed. PostgreSQL retained
exactly one approval and one first Creative; the Creative remains a draft and
the conflicts added no replacement. PTW revision `8c76246` fixes the client
resolution path, adds unit and desktop/mobile/iPhone WebKit browser regressions,
and updates the canonical Owner Console incident skill. The 67 web unit tests,
production build, and all 54 Chromium/mobile/WebKit browser checks pass. The
release guard now adds an incident-specific contract marker to the built/live
audit, advances the PWA shell cache generation, makes Playwright mandatory for
every Owner Console Hosting release, and provides a tracked clean-main web-only
deployer that cannot touch VPS services or PostgreSQL. The 16 Commander tests
(two dependency skips outside the image), Commander demo, skill verification,
Python compilation, shell syntax, and whitespace checks also pass locally.
PTW revision `80019c5` is deployed as Owner Console Hosting version
`a7a47a45ede67c7e`. Both Firebase default origins serve entry bundle
`index-D5YU1IIQ.js`, App bundle `App-uXl8cPRc.js`, the incident marker, and PWA
cache `ptw-shell-brief-studio-landing-ads-v2`; Gateway health, unauthenticated
rejection, and CORS pass. There were no matching approval POSTs after the
14:11 UTC cutover. PostgreSQL still has one approval, one ordinal-1 draft
Creative `01a07f55-20a5-755c-bbec-17a3f158ef4b`, zero approved versions, and
unchanged `contains=1` / `derived_from=2` Brief lineage counts.

Landing phone verification is recorded in `.local/landing-phone`, with
before/after captures, three screen themes at 1280/768/360px, and iPhone WebKit.
The 66 Owner Console and 6 public-web unit tests, 51 Owner Console and 16 public
browser checks, both production builds, full 169-test Validation suite, 15
Commander built-image tests, and 6 Owner Gateway tests pass. All 39 tests for
the exact current platform revision pass. The Commander demo, four-migration disposable
PostgreSQL idempotency/preservation check, canonical skill verification, Python
compilation, shell syntax, and whitespace checks pass. Local Ads smoke testing used one real saved Project and its approved
PNG at desktop and 360 px; missing Meta credentials produced the intended safe
disabled state with no horizontal overflow.

The production PostgreSQL Landing reservation path now records its approved
Post `derived_from` edge with the correct typed argument order. The affected
Project was preserved: the failed transaction had added no page, its exact
approved Post retry completed a draft with both visuals and three lineage
edges, duplicate reservation was idempotent, and restart recovery retained the
same IDs/digests with an empty queue. No reset ran.

Production advertises the exact four structured JSON modes and one bounded media
mode. Real canaries passed for all modes, fresh image generation, exact-reference
enhancement, and Pexels. All six versioned services are healthy; ChatGPT/Codex
reports `authorized` only after its real working test passes. The public Hosting
audit confirms Brief/Post/Landing, Settings authorization, the current service
worker, App Check, CORS, authenticated rejection, and Gateway health.

The confirmation-gated production reset at PTW revision
`210ebca733c723008f8f751f93c03b6f2d039786` installed migrations `001` through
`003` and immediately left all owned Brief, Studio, Landing, Ads, and graph
business tables empty. Its before/after snapshot confirmed that independent
platform database counts did not change. The independent platform is now at
revision `b3907db6b7dd4435fa58065dc96902e5536a9dc8`; all six application services
run the shared `contract-budget-20260908-153b1dc` release tag and are healthy. The
non-reset city-targeting rollout at PTW revision
`a92fbc758d6a25cf7dff35111891ee97ed2757dc` preserved the exact Project and
Brief IDs plus their pre-rollout row counts. Bridge, image generation,
enhancement, Pexels, dependency, and 1 GB resource canaries passed. Both
emergency stops are false, the 1 GB resource audit passed, and the scheduled
24-hour follow-up audit is active. Firebase Hosting version
`9046603eb4d5b84d` is live, and its public audit confirms the Ads-aware service
worker plus healthy Gateway/authentication boundaries.

The data-preserving path-based Landing rollout completed at PTW revision
`9a5043ea257832966676c3816bd9fb528f7b479b`. It created and checksummed a
root-only pre-migration PostgreSQL backup, installed migration 004, and proved
every pre-existing business-table fingerprint unchanged before serial cutover.
Project `01a07c66-b00a-7364-8fda-7de87c12a907` remains named `Natal Service`;
the new publication tables are empty until an owner explicitly publishes an
approved Landing. Real provider, generate/enhance, Pexels, dependency,
Telegram, and 1 GB canaries passed, and the persistent follow-up audit is due
2026-09-09 11:22 UTC. Owner Hosting version `57692ac4789cc5d0` and public
Hosting version `185107aab38614ab` are live. Public root/lane rendering,
noindex/robots/CSP, exact CORS, public 404s, private 401s, backup checksum, and
all six healthy versioned services were independently rechecked.

The Firebase/GoDaddy apex cutover completed at 2026-09-08 13:34 UTC. The exact
ownership TXT now names `natal-landings-86123`, while the existing Firebase apex
A record and all mail records remain unchanged. The apex has valid TLS and
passes the public root, all three lane rewrites, CSP, robots, and noindex audit.
The owner explicitly declined the optional `www` attachment, so its historical
certificate mismatch is outside the supported apex-only release. The legacy
`natal-dashboard-dev` Hosting site remains intact during the soak.

The systemic contract/recovery rollout completed at PTW revision
`153b1dc6417a4c26b36ca9af4f8aac5d00d8b591` without a migration or reset. Its
first preflight stopped before service cutover because `psql -c` did not expand
the migration-name variable; the old six services, persisted tags, and database
remained untouched. The tracked preflight was changed to stdin SQL, covered by
a regression test, committed, and rerun from the beginning. The accepted run
kept the full authority snapshot byte-identical and completed fresh bridge jobs
514–522 on attempt 1. The Landing contract was 8,444 bytes, all structured/media
and Pexels canaries passed, and dependency plus 1 GB audits passed. Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b` remained a draft at state digest
`b68f5ff2391aa206e4a7632c5b924be337c0e965d24e561411228c8e80872685`, with zero
immutable versions and five append-only generation runs before and after a
controlled Validation restart. Active mutations remained zero. The transient
`ptw-validation-24h-audit.timer` is active/waiting for its
2026-09-09 11:22 UTC follow-up.

The Phone Metrics replay incident is closed at PTW revision
`76110344697854085ac03676dc1d7da744f7cf82`. Pre- and post-cutover strict-schema
canaries passed composition on attempt 1 plus both image operations. A single
retry recovered Creative `01a07f55-20a5-755c-bbec-17a3f158ef4b` in place as a
draft with texture intensity `0.08` and a completed phone image. Its three
original failed composition runs remain append-only beside one completed
composition and one completed phone-image run. A Validation recreate preserved
the same Creative ID and state digest, with exactly one Creative for the Brief
and no approved version. No reset ran.

## Next work

Observe the scheduled 24-hour resource audit and continue normal owner review
of Analytics evidence and inactive Creative Skill candidates. TikTok photo
acceptance stays gated by an owner-selected approved public post and must not be
inferred from the deployment or private-only readiness.

Exercise an owner-directed Post or Landing generation with a temporary reference
image, verify the requested visual change, and confirm that navigation or
completion clears the upload while the generated result remains an ordinary
Project image.

Production now contains Project `Natal Service`
(`01a07c66-b00a-7364-8fda-7de87c12a907`), approved Brief
`01a07c66-b00a-7ffe-a44f-a5fd2d738515`, and recovered Phone Metrics Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b`. The Creative is a draft with no
immutable approved version. The owner must inspect/edit it in Post and use the
explicit Approve action before it may appear as an Ads deployment source; PTW
must not infer that approval.

The public apex transfer is complete. Keep the legacy Hosting site intact until
the apex has completed its 24-hour soak and the owner separately authorizes
retirement. `www` is intentionally outside the supported release by owner
decision and does not block the soak. The next public workflow is owner review
and approval of the existing Post, creation and approval of its Landing, and an
explicit first Publish with a permanent lane/slug reservation.

The Meta App, system user, Ad Account, Facebook Page, and professional Instagram
account are assigned. The owner must rotate the token disclosed during setup and
run the hidden-prompt configurator so PTW can discover the Instagram actor ID
without putting the replacement token in chat or shell history. Then stage one
`[PTW LOCAL]` deployment and sync it back to verify that Campaign, Ad Set, and Ad
all remain PAUSED. The same fresh token and verified actor ID can then be written
through the configurator's VPS mode, followed by a Validation-only restart and
one production connection read. Production code is deployed, but Meta staging
remains disabled until that isolated secret file exists.
