# Commander current state

Updated: 2026-08-24
Branch: `codex/web-only-commander`

## Last completed milestone

The Simplified Validation Phase 1 implementation is complete and committed in
the PTW checkout as `d40bd5b` and in the independent platform checkout as
`f5c0bd3`. The platform release-transfer guard is committed as `6ed6d8d`:

```text
raw idea → Product Brief → owner approval → five Ad Creatives
```

Marketing Positioning and the Ads stub have been replaced by the
`validation_pipeline` runtime. Its only structured bridge modes are
`product_brief`, `product_brief_revision`, and `ad_creative_batch`. Stage 1
infers Ukrainian or English from one raw idea and produces one strict,
immutable Product Brief with three to five benefits and an explicit
low-friction offer. Owner approval confirms the promise and offer can be
honored, atomically creates one batch, and reserves generation. Stage 2 sends
only that approved Brief to one structured call and creates exactly five
complete creatives in the fixed angle order.

Pexels is the only photo adapter. Selection is bounded to ten square results
plus one broader category fallback, never reuses a photo within a batch, and
rejects rate limits, unsafe URLs or redirects, invalid MIME, oversized data,
small images, and undecodable bytes. Pillow produces deterministic 1080×1080
JPEGs with the hook, offer, and CTA. PostgreSQL stores the authoritative bytes,
digest, source page, photographer, license, attribution, and complete lineage.

The Owner Console navigation is Product Briefs → Ads → Landing → Admin. Brief
corrections and creative feedback create editable, owner-gated lesson
proposals bounded to the corresponding generator's `owner-lessons.md`. Ads
shows five authenticated artifacts and prominent Pexels/photographer links.
Landing is an inactive `Stage 3 pending` placeholder and makes no runtime API
call. Active console chrome, iconography, terminal, and diagrams are strictly
black, white, and neutral gray; state meaning does not depend on hue. Reviewed
Ad photography remains unaltered. The three Natal templates and dormant
Landing source remain on disk.

The database is one clean 19-table reset baseline. It contains generic graph,
source, feedback, weight, audit, Plan/Execute, guard, and control authority plus
Product Brief, approval, attempts, provider invocation, creative batch,
creative, asset, and lesson-proposal tables. Legacy Positioning, active
Landing, Idea, Branding, and Ads tables are absent.

## Verification

- Validation Linux/amd64 built-image suite: 22 passed, including strict Brief/creative
  shapes, offer enforcement, language inference, bridge input isolation,
  Pexels selection/fallback/rate-limit/download safety, deterministic JPEGs,
  authentication, ETags, retired API 404s, and the explicit Compose environment
  boundary.
- Disposable PostgreSQL 16: two integration tests passed for immutable
  corrections, idempotent approval, atomic five-asset persistence, restart and
  retry behavior, graph edges, feedback/weights, proposal promotion, and legacy
  table absence.
- Baseline/reset verification passed twice with 19 application tables and the
  independent platform fixture unchanged at three rows.
- Owner Gateway built-image suite: 18 active non-Landing tests passed.
- Commander built-image Telegram boundary: one passed; the deterministic
  `ptw-validation-v1` demo was regenerated successfully.
- Owner web: 10 Vitest tests, production TypeScript/Vite build, and six
  Playwright journeys passed on desktop Chromium, 360 px Chromium, and iPhone
  WebKit. Build-time source checks and computed-style assertions enforce the
  monochrome chrome invariant. The service-worker cache is
  `ptw-shell-v28-monochrome-validation`, and the built module graph contains no
  retired Positioning/Landing route.
- Canonical Product Brief and Ad Creative skills pass the Skill Creator
  validator; the PTW skill/link/mount validator passes. The retired Marketing
  Positioning skill and desktop link are absent; Natal is explicitly dormant.
- The independent bridge was changed only in the separate
  `/Users/serhiiholovaschuk/Projects/ptw-platform-validation` checkout. Its
  complete suite passes 84 tests and its capabilities expose the three new
  modes while rejection tests cover the retired modes.
- All five off-host Linux/amd64 images and checksum-bearing archives were
  rebuilt from clean commits with the pinned non-`latest` release tag
  `phase1-5f47722-6ed6d8d`. The platform archive also contains a verified Git
  bundle whose HEAD is exactly `6ed6d8d`; a disposable import fast-forwarded
  successfully from production's current `2f2ee9a` revision.
- Shell syntax checks, Python compilation, `git diff --check`, and release
  script guards pass. Landing-specific suites were intentionally not run.
- The Ad offer-punctuation incident correction is deployed and its recovery-
  history follow-up is release-ready locally: 25 Validation tests, 15 active
  Owner Gateway tests, three disposable-PostgreSQL integration tests, 12 Owner
  web unit tests, the production TypeScript/Vite build, and 12 desktop/360 px/
  iPhone journeys pass. Exact offer and CTA fields are schema-bound; failed and
  recovered-batch UI states and the audited existing-bot callback are covered.

## Production state

The owner-authorized Simplified Validation Phase 1 cutover completed on
2026-08-24. Production uses the five matching Linux/amd64 images tagged
`phase1-5f47722-6ed6d8d`; the application repository is at the environment
isolation release and the independent platform repository is at `6ed6d8d`.
Fresh strict canaries passed for `product_brief`, `product_brief_revision`, and
`ad_creative_batch`, followed by a successful non-persisting Pexels
search/download/render canary.

The confirmation-gated reset replaced only `ptw_commander.public`. The clean
baseline has 19 application tables plus the migration metadata table, with zero
Briefs, batches, creatives, entities, and relationships. Legacy Positioning,
active Landing, Idea, Branding, and Ads tables and containers are absent, and
the independent platform database counts were unchanged.

Commander, Validation, Owner Gateway, platform API, and platform worker are
healthy. Validation receives only its explicit eight-variable runtime allowlist;
retired research, Landing, and YouTube settings are absent from both Validation
and Owner Gateway. Dependency/schema/bridge audits, canonical skill checks, the
existing Telegram emergency-boundary canary, serial restart recovery, and the
immediate 1 GB/OOM audit pass. The persistent 24-hour resource audit is
scheduled.

The public audit passes the cache-busted v28 monochrome bundle, Auth/App Check,
exact CORS origin, unauthenticated rejection, Product Brief/Ads/Landing/Admin
markers, and retired-route 404s. A real exact-owner signed-in Stage 1–2 browser
journey remains the final interactive acceptance item.

The offer-punctuation incident backend is on `incident-063101c` and Hosting is
on the v29 failure-reason bundle. The original failed attempt produced one
audited Telegram message, retry attempt 2 completed the same batch with five
verified 1080×1080 JPEGs, and restart plus immediate 1 GB/OOM audits pass. A
v30 follow-up that keeps the failed attempt visible after successful retry is
verified locally but not yet deployed.

## Next work

Deploy the v30 recovered-failure-history follow-up and repeat the public and
restart checks. Then complete the exact-owner signed-in desktop/360 px journey:
create and correct a
Brief, approve its promise/offer, inspect five authenticated Ads and attribution,
submit feedback, and inspect dormant Landing and Admin. Review the scheduled
24-hour resource audit. Stage 3 Landing, traffic, publishing, campaigns, UTMs,
analytics, and conversion tracking remain out of scope.
