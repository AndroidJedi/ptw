# Commander current state

Updated: 2026-08-23
Branch: `codex/web-only-commander`

## Last completed milestone

PTW v2 is deployed in production as Marketing Positioning, Landing, Ads, and a
compact Admin workspace. The application release is `ptw-v2-8ee1f1a` from
commit `8ee1f1af2d1d50b3b5c7163bfb49ed7ada543866`; Commander, Marketing
Positioning, and Owner Gateway all run the same prebuilt Linux/amd64 release.
The independent platform bridge runs `ptw-v2-f944c0f` from commit
`2f2ee9aa114de62137508ff132396568950f7335`.

The owner-authorized irreversible reset dropped and rebuilt only
`ptw_commander.public`. Production intentionally contains zero Positioning
projects, Landing draft sets, leads, and notification attempts. The clean v1
baseline contains 26 v2 domain tables plus the migration table and no Idea
Laval, Branding, or legacy Ads tables. The reset verified that the independent
`/opt/ptw/platform` database counts were unchanged.

Firebase currently serves:

- Owner Console version `76f051ae4c63d774`, application bundle
  `App-6eT3CgU7.js`, and service-worker cache
  `ptw-shell-v25-marketing-workspaces`.
- Natal placeholder version `a1eeff5fc3b37265`, whose active root says
  “No landing published yet”; retired `/builds/*` content is no longer served.

## Production verification

- Fresh strict, schema-bound platform canaries passed for
  `marketing_positioning_research_plan`, `marketing_positioning_document`,
  `marketing_positioning_revision`, and `natal_landing_revision`.
- Both Owner Console origins pass bundle, Auth, App Check, CORS, dependency,
  health, retired-route, and old-domain API audits.
- Vitest 10, the production web build, and six Playwright journeys passed on
  desktop Chromium, 360 px Chromium, and iPhone WebKit. The journeys cover the
  empty state, Positioning creation/correction/approval, all three Landing
  templates, scoped edits, publication, lead capture, Ads stub, Admin, and old
  route redirects.
- Built-image suites passed: Commander 7, Marketing Positioning 10, and Owner
  Gateway 23. Platform bridge tests passed 80 cases.
- A clearly labelled direct notification was sent through the existing PTW bot
  without creating a fake lead or notification-attempt row and without adding
  another poller.
- Individual service restarts preserved the empty database and all readiness
  checks. Immediate 1 GB resource audits passed with swap active and no new OOM
  event.
- A locked follow-up audit is scheduled by `ptw-v2-24h-audit.timer` for
  2026-08-24 13:13:25 UTC.
- Canonical desktop/container skill links and the PTW skill verifier pass.

## Operational guardrails learned during cutover

Production scripts now load the root-owned Commander, Owner Gateway, and
platform environments before Compose interpolation. They validate the trusted
proxy CIDR and lead HMAC secret before reset, keep `pull_policy: never` for
preloaded release images, use exact retired-container names in audits, and
permit exactly the two Firebase Owner Console origins without a wildcard.

## Next work

Production is deliberately empty. The next real action is for the owner to open
or reload the Owner Console, create the first Marketing Positioning project,
approve its completed revision, and use that approved revision to populate the
three Landing templates. Ads remains a truthful read-only stub until generation
and publishing are implemented.
