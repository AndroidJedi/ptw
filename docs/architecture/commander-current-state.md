# Commander current state

Updated: 2026-08-25
Branch: `codex/web-only-commander`

## Last completed milestone

The latest deployed milestone closes the learned-feedback loop for Stage 2. After
all feedback lessons from a completed Ad batch are promoted or dismissed, Ads
offers one confirmed **Generate learned rerun** action. It creates a distinct
five-creative child batch from the same approved Brief, keeps the original
batch immutable, records `rerun_of` lineage plus the exact skill snapshot, and
prevents duplicate children. The Validation runner now reloads canonical owner
lessons immediately before each generation, so a service restart is not needed
to apply a promoted lesson. Production runs matching application images tagged
`learned-reruns-311dae9`, built from `311dae9`.

The Simplified Validation Phase 1 implementation is complete. The earlier
grouped-lesson milestone replaced per-proposal Save/Plan/Dismiss controls with
one combined lesson action: every feedback and proposal UUID remains append-only,
while all
pending proposals in one generator domain share one editable lesson and one
Plan/Execute command.
The independent platform checkout
remains unchanged at its release-transfer guard `6ed6d8d`:

```text
raw idea → Product Brief → owner approval → five Ad Creatives
```

The latest deployed incident correction replaces the Admin checkbox-like cancel
icon with labelled Run, Restore, and confirmed Cancel controls, makes full job
details available for every status, and prevents cancellation/planner races.
Unexecuted failed or cancelled lesson commands can restore the preserved plan
or regenerate it while restoring the complete linked proposal group.

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
small images, and undecodable bytes. The generator now silently drafts multiple
headline candidates per proposed visual and selects the strongest only after
emotion-match, narrative-completion, specificity, human-tension, and scroll
tests. Pillow produces deterministic 1080×1080 JPEGs with the canonical Natal
logo, Inter font, palette, hook, offer, and CTA. PostgreSQL stores the
authoritative bytes, digest, source page, photographer, license, attribution,
and complete lineage.

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

- Learned-rerun local verification: 20 Owner web Vitest tests and the production
  build pass; 15 Playwright journeys pass on desktop Chromium, 360 px Chromium,
  and iPhone WebKit. The Validation Linux/amd64 image passes 28 tests, the
  Owner Gateway Linux/amd64 image passes 25 focused active non-Landing tests, the
  disposable PostgreSQL 16 baseline applies both migrations, and all three
  integration tests pass for immutable child lineage, idempotency, skill
  snapshots, existing retry/failure history, and atomic assets.
  The live Owner Console cache is `ptw-shell-v34-learned-reruns`.
- Validation Linux/amd64 built-image suite: 26 passed, including grouped lesson
  proposal planning, strict Brief/creative
  shapes, offer enforcement, language inference, bridge input isolation,
  Pexels selection/fallback/rate-limit/download safety, deterministic JPEGs,
  authentication, ETags, retired API 404s, the explicit Compose environment
  boundary, failure notification, and recovered failure history.
- Disposable PostgreSQL 16: three integration tests passed for immutable
  corrections, idempotent approval, atomic five-asset persistence, restart and
  retry behavior, at-most-once failure notification, recovered failure history,
  graph edges, feedback/weights, atomic proposal failure/restoration/promotion,
  and legacy table absence.
- Baseline/reset verification passed twice with 19 application tables and the
  independent platform fixture unchanged at three rows.
- Owner Gateway production-equivalent image: 18 focused active non-Landing
  tests passed for auth/CORS, control-store restoration, destructive gates,
  root-broker boundaries, and existing notification behavior.
- Commander built-image Telegram boundary: one passed; the deterministic
  `ptw-validation-v1` demo was regenerated successfully.
- Owner web: 17 Vitest tests, production TypeScript/Vite build, and 15
  Playwright journeys passed on desktop Chromium, 360 px Chromium, and iPhone
  WebKit. Failed/recovered batch panels and malformed authenticated-image
  resources are covered. Build-time source checks and computed-style assertions
  enforce the monochrome chrome invariant. The prior service-worker cache was
  `ptw-shell-v33-safe-job-controls`. The built module
  graph contains no retired Positioning/Landing route.
- Canonical Product Brief and Ad Creative skills pass the Skill Creator
  validator; the PTW skill/link/mount validator passes. The retired Marketing
  Positioning skill and desktop link are absent. Natal Landing remains dormant;
  its canonical identity is now shared by active Ad rendering.
- The independent bridge was changed only in the separate
  `/Users/serhiiholovaschuk/Projects/ptw-platform-validation` checkout. Its
  complete suite passes 84 tests and its capabilities expose the three new
  modes while rejection tests cover the retired modes.
- The three application Linux/amd64 images and checksum-bearing archives were
  rebuilt from the clean `311dae9` commit with pinned non-`latest` tag
  `learned-reruns-311dae9`. The independent platform API and worker remain on
  the previously verified `phase1-5f47722-6ed6d8d` release.
- Shell syntax checks, Python compilation, `git diff --check`, and release
  script guards pass. Landing-specific suites were intentionally not run.
- The Ad offer-punctuation incident correction and recovery-history follow-up
  are deployed. Exact offer and CTA fields are schema-bound; failed and
  recovered-batch UI states and the audited existing-bot callback are covered.

## Production state

The learned-rerun release completed in place without a reset on 2026-08-25.
Commander, Validation, and Owner Gateway now use matching Linux/amd64 images
tagged `learned-reruns-311dae9`, built from `311dae9`. Migration
`002_lesson_driven_creative_reruns.sql` is applied; the original completed
batch remains immutable and no child batch exists until the owner confirms the
new generation action. The exact promoted Ad owner lesson was reconciled into
the tracked canonical skill with SHA-256
`4b235a16fc2e16fac506e0b555a69815f4df3974e38b786e5d485a4aa85ea6f1`.
The independent platform repository remains at `6ed6d8d`, and its API and
worker remain on `phase1-5f47722-6ed6d8d`. Two fresh strict canaries passed for
`product_brief`, `product_brief_revision`, and `ad_creative_batch`, and the
non-persisting Pexels search/download/Natal-render canary passed after the
in-place release. The live Owner Console exposes one grouped lesson action for
pending proposals. After every proposal for a completed batch is terminal,
Ads exposes **Run the Ad agent again**, a confirmation-gated **Generate learned
rerun** action, and then **Open learned rerun** for the resulting child batch.
The retired Save edit, Plan promotion, and Dismiss controls are not present.

After an ambiguous square cancel control was pressed on Ad lesson command
`f520e7f2-9652-46bd-94eb-f7b58d87b32c`, its already completed planner result
was recovered from immutable command events. The owner subsequently executed
the recovered plan, and its four linked Ad proposals are now promoted together.
The no-reset releases preserved the complete command/event history, the four
proposal rows, and every existing feedback, weight, proposal, and Ad asset row.

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
immediate 1 GB/OOM audit pass. The in-place release performed no reset: all nine
HumanFeedback rows, nine WeightUpdate rows, four Product Brief proposals, five
Ad Creative proposals, and five stored assets matched their pre-release row
fingerprints exactly. All five creative bytes, digests, and decodable 1080×1080
JPEGs were also reverified. The platform bridge was neither rebuilt nor
restarted.

The public audit passes the cache-busted v34 learned-reruns bundle,
Auth/App Check, exact CORS origin, unauthenticated rejection, Product
Brief/Ads/Landing/Admin markers, and retired-route 404s. A real exact-owner
signed-in Stage 1–2 browser journey remains the final interactive acceptance item.

Batch `01a03327-a038-72a6-85ae-e50983b0e6f4` retains failed attempt 1 and its
exact reason after retry attempt 2 completed. The batch has five unique,
verified 1080×1080 JPEGs; every stored creative has the approved exact offer
and CTA. The original failure produced one audited Telegram message with one
reservation/result pair. No retry or success message was sent. Restart checks
preserve the completed batch, recovered reason, notification state, empty
operation guard, and exactly two notification audit events.

All five authoritative creative assets independently pass stored-byte,
SHA-256, 1080×1080 JPEG decode, internal HTTP media-type, ETag, and byte-
equality checks before and after restart. A reported malformed inline PNG is
not emitted by PTW. The live v34 Owner Console surfaces HTTP/MIME/integrity/
ETag/browser-decode reasons with Creative UUID and a bounded retry. CORS exposes
the authoritative ETag and Content-Length to the exact owner origins.

The learned-rerun release preserved all existing feedback, weight, proposal,
batch, creative, asset, and command/event fingerprints. Its immediate 1 GB/OOM
audit passes with 374 MB available memory and 1.67 GB free swap; a fresh locked
24-hour resource audit is scheduled. The operation guard is empty, emergency
stop is false, all three health endpoints return 200, four Ad lesson proposals
remain promoted, and the one historical failed proposal remains visible.

## Next work

Use the completed Ads batch to confirm **Generate learned rerun**, wait for its
distinct five-creative child batch, and open it from the source batch. Then
complete the exact-owner signed-in desktop/360 px journey: create and correct a
Brief, approve its promise/offer, inspect five authenticated Ads and attribution,
submit feedback, and inspect dormant Landing and Admin. Review the scheduled
24-hour resource audit. Stage 3 Landing, traffic, publishing, campaigns, UTMs,
analytics, and conversion tracking remain out of scope.
