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

- Validation Linux/amd64 built-image suite: 21 passed, including strict Brief/creative
  shapes, offer enforcement, language inference, bridge input isolation,
  Pexels selection/fallback/rate-limit/download safety, deterministic JPEGs,
  authentication, ETags, and retired API 404s.
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

## Production state and cutover gate

Production has not been modified by this milestone. It remains on the previous
Marketing Positioning/Landing release documented in Git history. No production
database row, service, Firebase release, Telegram behavior, platform database,
secret, or container was changed.

The read-only production preflight on 2026-08-24 found the existing services
healthy, both production worktrees clean, the maintenance lock available, no
kernel OOM entries, and sufficient disk/swap headroom. It also confirmed that
`PEXELS_API_KEY` is not provisioned in the root-owned runtime environment.

The reviewed PTW commit and the matching five-image release set are now ready.
Cutover remains blocked by design until the remaining gates are available in
one explicit release operation:

1. a root-owned `PEXELS_API_KEY` and successful non-persisting Pexels
   download/render canary;
2. fresh schema-bound canaries for all three validation modes; and
3. the exact owner phrase `RESET PTW PRODUCTION` immediately before the
   allowlisted irreversible reset of `ptw_commander.public`.

The serial deploy script restores the prior platform images if either the
bridge or Pexels canary fails before reset. The reset verifies zero Briefs,
batches, creatives, entities, and relationships; legacy tables/containers are
absent; and the independent platform database counts are unchanged. Immediate
and 24-hour 1 GB audits remain part of the production acceptance sequence.

## Next work

Provision the Pexels key and perform the gated cutover only after the owner
supplies the exact reset phrase. Stage 3 Landing, traffic, publishing,
campaigns, UTMs, analytics, and conversion tracking remain out of scope.
