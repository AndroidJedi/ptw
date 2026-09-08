# Commander current state

Updated: 2026-09-08
Branch: `main`
Deployment: systemic contract/recovery release `contract-budget-20260908-153b1dc` is live; Meta staging is disabled until a fresh secret is configured

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

The lower owner navigation includes a compact Settings control next to language.
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

Both templates expose an independent bounded font-family and font-size control
for every editable semantic text role. The catalog provides Inter, Roboto
Condensed, Manrope, Montserrat, Source Sans 3, Oswald, Cormorant Garamond,
Cormorant Garamond Italic, Lora, and Lora Italic. Renderer-owned phone chrome,
the Natal identity, and system UI text remain fixed.

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

The approved-Brief reopen conflict was diagnosed against production Brief
`01a07c66-b00a-7ffe-a44f-a5fd2d738515`. Two owner requests returned HTTP 409
at 2026-09-08 13:40:53 and 13:41:01 UTC because the Brief UI reopened a blank
template/direction chooser even though its ordinal-1 Phone Metrics Creative
`01a07f55-20a5-755c-bbec-17a3f158ef4b` already existed. PostgreSQL retained
exactly one approval and one first Creative; the Creative remains a draft and
the conflicts added no replacement. PTW revision `8c76246` fixes the client
resolution path, adds unit and desktop/mobile/iPhone WebKit browser regressions,
and updates the canonical Owner Console incident skill. The 67 web unit tests,
production build, 51 pre-existing browser checks plus the three targeted
approved-Brief browser checks, full 169-test Validation suite, 15 Commander
tests, Commander demo, skill verification, Python compilation, and whitespace
checks pass locally. This web-only fix is committed and pushed but not deployed;
the protected production release still requires explicit owner authorization.

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

After explicit owner authorization, deploy the owner-console web-only revision
`8c76246`, audit the hashed bundle/service-worker and authenticated boundaries,
then use the production Brief action once and require direct navigation to the
existing Creative with no `/approve` POST or new database rows.

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
