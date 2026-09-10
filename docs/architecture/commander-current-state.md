# Commander current state

Updated: 2026-09-10
Branch: `main`
Deployment: all eight application services are healthy. Owner Gateway, hosted
GOD, and the new release controller run `mobile-god-20260910-e3dadf4`;
Validation remains on `fast-release-20260910-64de1e8`, while Commander and the
three provider services remain on `god-mode-sandbox-20260910-faf77f9`. Schema
005 and both web sites are live with Owner cache v6. Meta credentials remain
unconfigured.

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

## Temporary GOD chat images

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
See the [shared contract](universal-ad-studio.md#shared-image-reference-input)
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
learning data, or unselected assets. It has no lead handling, forms, analytics,
cookies, directory, or Post-skill influence.

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

The common versioned template catalog contains:

- `universal_ad` at 1080×1080;
- `phone_metrics` at 1080×1350.

Phone Metrics exposes independent visibility toggles for its canonical
upper-left and in-phone Natal lock-ups. Both are shown by default and remain
renderer-owned, so owners can omit either mark without replacing its artwork.

Both templates expose an independent bounded font-family and font-size control
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

## Studio agents and learning

Composition uses the approved Brief, selected live template catalog, canonical
`studio-creative-composer` skill, and the latest accepted global and Project
skill snapshots. Output is validated against the selected template's exact
configuration/content shape; the live catalog wins over learned instructions.
Renderer-owned numeric bounds, enums, colors, typography, device limits, Landing
content lengths, and privacy-sensitive blank fields are also present in the
strict provider schemas and share constants with their runtime normalizers. The
request fingerprint is versioned with that complete contract, so a changed
contract cannot replay a completed response from an older schema. If a completed response still fails
deterministic PTW validation, the bridge may make exactly one fresh corrective
attempt; transport, timeout, cancellation, and provider failures never trigger
an unsafe blind second attempt. Release acceptance covers both Product Brief
modes, Universal Post, Phone Metrics, Landing composition, Studio learning,
Landing learning, new image generation, and exact-reference enhancement; every
structured canary must pass domain validation on fresh attempt 1 and report a
valid prompt/input/schema byte budget. Landing additionally has compact
input/schema limits and uses exactly the runtime payload builder.

For `phone_metrics`, composition automatically starts a fresh, text-free hero
generation governed by `studio-phone-hero-generator`. The prompt includes the
saved creative direction, a Brief-derived subject description, and accepted
global and Project visual lessons. The direction remains available to a future
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
or **Approve creative** creates one immutable checkpoint only when state changed.
The `studio-edit-learner` produces an automatic Project lesson and a sanitized
global proposal. The owner chooses **Apply globally** or **Keep project-only**.
No-op saves are idempotent. Learning failure never rolls back the saved creative
or approved version and remains retryable.

The independent structured bridge advertises exactly four JSON modes:
`product_brief`, `product_brief_revision`,
`studio_creative_generation`, and `studio_edit_learning`. It also retains
one bounded `content_non_human_graphic_generation` media mode with at most one
validated PNG reference for image enhancement. Retired candidate/critic modes
are absent.

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
