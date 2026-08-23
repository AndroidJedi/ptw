# Commander current state

Updated: 2026-08-23
Branch: `codex/web-only-commander`

## Last completed milestone

PTW v2 is deployed in production as Marketing Positioning, Landing, Ads, and a
compact Admin workspace. The application release is `ptw-v2-24e82ef` from
commit `24e82ef5fb5990d7f2657a2f20f42c29b6ca3c8b`; Commander, Marketing
Positioning, and Owner Gateway all run the same prebuilt Linux/amd64 release.
The independent platform bridge runs `ptw-v2-f944c0f` from commit
`2f2ee9aa114de62137508ff132396568950f7335`.

The owner-authorized irreversible reset dropped and rebuilt only
`ptw_commander.public`. Production now contains one owner-created Positioning
project with one completed, approved revision; it contains no Landing draft
sets or leads. The clean v1 baseline plus the additive Positioning notification
migration contains 27 v2 domain tables plus the migration table and no Idea
Laval, Branding, or legacy Ads tables. The reset verified that the independent
`/opt/ptw/platform` database counts were unchanged.

Firebase currently serves:

- Owner Console version `1fd43880dc096c7c`, application bundle
  `App-icGGmCnv.js`, and service-worker cache
  `ptw-shell-v26-owner-input-positioning`.
- Natal placeholder version `a1eeff5fc3b37265`, whose active root says
  “No landing published yet”; retired `/builds/*` content is no longer served.

## Production verification

- Fresh strict, schema-bound platform canaries passed for
  `marketing_positioning_document`, `marketing_positioning_revision`, and
  `natal_landing_revision` after the structured-output schemas were updated to
  include explicit types for every constant field.
- Both Owner Console origins pass bundle, Auth, App Check, CORS, dependency,
  health, retired-route, and old-domain API audits.
- Vitest 10, the production web build, and six Playwright journeys passed on
  desktop Chromium, 360 px Chromium, and iPhone WebKit. The journeys cover the
  empty state, Positioning creation/correction/approval, all three Landing
  templates, scoped edits, publication, lead capture, Ads stub, Admin, and old
  route redirects.
- Built-image suites passed: Commander 7, Marketing Positioning 14, and Owner
  Gateway 24. The disposable PostgreSQL 16 reset/integration suite passed and
  preserved the independent platform-count fixture.
- A clearly labelled direct notification was sent through the existing PTW bot
  without creating a fake lead or notification-attempt row and without adding
  another poller.
- The first real Positioning attempt failed on retired DataForSEO research. The
  active flow now synthesizes directly from the permanent owner-idea source,
  marks unsupported market claims as assumptions, and contains no DataForSEO
  configuration or live fallback. A strict-schema failure on the first retry
  was also retained; the next retry completed with all deterministic quality
  gates passing.
- Positioning now sends terminal completion/failure notifications directly
  through the existing PTW bot and allowlisted chat. Both retained terminal
  attempts were delivered and persisted before the Positioning service restart;
  the restart created no duplicate notification.
- Individual service restarts preserved the completed revision, approval, and
  notification records while all readiness checks remained healthy. Immediate
  1 GB resource audits passed with swap active and no new OOM event.
- A locked follow-up audit is scheduled by `ptw-v2-24h-audit.timer` for
  2026-08-24 13:13:25 UTC.
- Canonical desktop/container skill links and the PTW skill verifier pass.

## Operational guardrails learned during cutover

Production scripts now load the root-owned Commander, Owner Gateway, and
platform environments before Compose interpolation. They remove retired
DataForSEO settings before Compose starts Positioning, validate the trusted
proxy CIDR and lead HMAC secret before reset, keep `pull_policy: never` for
preloaded release images, use exact retired-container names in audits, and
permit exactly the two Firebase Owner Console origins without a wildcard.

## Next work

The first Marketing Positioning revision is complete and approved. The next
real action is to use that exact approved revision to populate and inspect the
three private Landing templates, edit blocks if needed, and publish one exact
snapshot. Ads can inspect its two prepared concepts but remains a truthful
read-only stub until generation and publishing are implemented.
