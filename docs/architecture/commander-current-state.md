# Commander current state

Updated: 2026-08-24
Branch: `codex/web-only-commander`

## Last completed milestone

The Simplified Validation Phase 1 implementation is complete. The latest
application milestone is the Ad offer-punctuation incident correction and its
recovered-failure-history follow-up at `d06c409`. The independent platform
checkout remains unchanged at its release-transfer guard `6ed6d8d`:

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

- Validation Linux/amd64 built-image suite: 25 passed, including strict Brief/creative
  shapes, offer enforcement, language inference, bridge input isolation,
  Pexels selection/fallback/rate-limit/download safety, deterministic JPEGs,
  authentication, ETags, retired API 404s, the explicit Compose environment
  boundary, failure notification, and recovered failure history.
- Disposable PostgreSQL 16: three integration tests passed for immutable
  corrections, idempotent approval, atomic five-asset persistence, restart and
  retry behavior, at-most-once failure notification, recovered failure history,
  graph edges, feedback/weights, proposal promotion, and legacy table absence.
- Baseline/reset verification passed twice with 19 application tables and the
  independent platform fixture unchanged at three rows.
- Owner Gateway built-image suite: 15 active non-Landing tests passed.
- Commander built-image Telegram boundary: one passed; the deterministic
  `ptw-validation-v1` demo was regenerated successfully.
- Owner web: 12 Vitest tests, production TypeScript/Vite build, and 12
  Playwright journeys passed on desktop Chromium, 360 px Chromium, and iPhone
  WebKit. Failed and recovered batch panels are covered. Build-time source
  checks and computed-style assertions enforce the monochrome chrome invariant.
  The live service-worker cache is
  `ptw-shell-v30-validation-failure-history`, and the built module graph
  contains no retired Positioning/Landing route.
- Canonical Product Brief and Ad Creative skills pass the Skill Creator
  validator; the PTW skill/link/mount validator passes. The retired Marketing
  Positioning skill and desktop link are absent; Natal is explicitly dormant.
- The independent bridge was changed only in the separate
  `/Users/serhiiholovaschuk/Projects/ptw-platform-validation` checkout. Its
  complete suite passes 84 tests and its capabilities expose the three new
  modes while rejection tests cover the retired modes.
- The three application Linux/amd64 images and checksum-bearing archives were
  rebuilt from the clean `d06c409` commit with pinned non-`latest` tag
  `incident-d06c409`. The independent platform API and worker remain on the
  previously verified `phase1-5f47722-6ed6d8d` release.
- Shell syntax checks, Python compilation, `git diff --check`, and release
  script guards pass. Landing-specific suites were intentionally not run.
- The Ad offer-punctuation incident correction and recovery-history follow-up
  are deployed. Exact offer and CTA fields are schema-bound; failed and
  recovered-batch UI states and the audited existing-bot callback are covered.

## Production state

The owner-authorized Simplified Validation Phase 1 cutover completed on
2026-08-24. Commander, Validation, and Owner Gateway now use matching
Linux/amd64 images tagged `incident-d06c409`; the application repository is at
`d06c409`. The independent platform repository remains at `6ed6d8d`, and its
API and worker remain on `phase1-5f47722-6ed6d8d`. Fresh strict canaries passed
for `product_brief`, `product_brief_revision`, and `ad_creative_batch` after
the incident release.

The confirmation-gated Phase 1 reset replaced only `ptw_commander.public` and
established 19 application tables plus the migration metadata table. Production
has since persisted the owner-created Brief, recovered batch, five creatives,
assets, attempts, and audit lineage. Legacy Positioning, active Landing, Idea,
Branding, and Ads tables and containers remain absent, and the independent
platform database was not changed by the incident release.

Commander, Validation, Owner Gateway, platform API, and platform worker are
healthy. Validation receives only its explicit nine-variable runtime allowlist,
including the non-secret Owner Gateway failure-callback URL;
retired research, Landing, and YouTube settings are absent from both Validation
and Owner Gateway. Dependency/schema/bridge audits, canonical skill checks, the
existing Telegram emergency boundary, serial restart recovery, and the
immediate 1 GB/OOM audit pass. The platform bridge was neither rebuilt nor
restarted for this incident.

The public audit passes the cache-busted v30 failure-history bundle, Auth/App Check,
exact CORS origin, unauthenticated rejection, Product Brief/Ads/Landing/Admin
markers, and retired-route 404s. A real exact-owner signed-in Stage 1–2 browser
journey remains the final interactive acceptance item.

Batch `01a03327-a038-72a6-85ae-e50983b0e6f4` retains failed attempt 1 and its
exact reason after retry attempt 2 completed. The batch has five unique,
verified 1080×1080 JPEGs; every stored creative has the approved exact offer
and CTA. The original failure produced one audited Telegram message with one
reservation/result pair. No retry or success message was sent. Restart checks
preserve the completed batch, recovered reason, notification state, empty
operation guard, and exactly two notification audit events.

## Next work

Complete the exact-owner signed-in desktop/360 px journey: create and correct a
Brief, approve its promise/offer, inspect five authenticated Ads and attribution,
submit feedback, and inspect dormant Landing and Admin. Review the scheduled
24-hour resource audit. Stage 3 Landing, traffic, publishing, campaigns, UTMs,
analytics, and conversion tracking remain out of scope.
