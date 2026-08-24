---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, Ad Creatives and authenticated images, dormant Landing, Admin, Commander, the validation API, the platform bridge, PostgreSQL, and the existing Telegram emergency boundary. Use when a workspace fails, stale UI is served, readiness regresses, an artifact fails, or a retired route reappears.
---

# PTW Owner Console Incident

Trace the public symptom through browser → Hosting/Caddy → Owner Gateway →
Validation API → PostgreSQL or the independent structured bridge/Pexels API. A
healthy gateway alone does not prove Stage 1–2 readiness.

## Public boundary

- Verify hashed bundles, bumped service-worker cache, Firebase Auth persistence,
  App Check, exact Owner CORS origins, and unauthenticated rejection.
- Navigation is Product Briefs, Ads, Landing, Admin. Landing shows only
  `Stage 3 pending`.
- Legacy Positioning, research, public Landing/lead, and Ads-stub APIs must
  return 404.
- Image delivery is owner-authenticated and returns the stored JPEG with its
  authoritative ETag.

## Stage checks

- Product Briefs: raw idea only; inferred `uk` or `en`; one strict hypothesis;
  three to five benefits; non-empty strong offer; no market/SEO/YouTube call;
  immutable corrections; owner approval of promise and offer.
- Ads: one `ad_creative_batch` bridge call receives only the approved Brief;
  exactly five fixed angles; CTA/offer continuity; five unique creative and
  asset UUIDs; all-or-nothing persistence.
- Pexels: root-owned key, ten-result bound, category fallback, unique source
  photo IDs, allowed CDN/MIME/size/dimensions, photographer/source/license
  attribution, and deterministic 1080×1080 JPEG SHA-256.
- Feedback: resolve the creative UUID; persist append-only HumanFeedback and
  WeightUpdate entities with `evaluates` and `adjusts` edges; create only a
  pending editable lesson proposal.
- Admin: keep Jobs, Docs/System, emergency stop, reset phrase, and break-glass
  terminal owner-authenticated.

## Failure handling

Restart recovery may fail interrupted Brief or batch attempts and release only
their guard. A failed five-asset preparation stores no creative or asset rows.
Retry only failed targets; approval remains idempotent with one batch per Brief.
Do not bypass schema validation, the global operation guard, App Check, owner
approval, source lineage, or authenticated artifact delivery.

Reuse the existing Telegram bot only for established notifications/emergency
controls. Do not add a webhook, poller, worker, creative notification, or new
command. Inbound commands remain `/help`, `/status`, and `/stop` only.

## Release acceptance

Render Compose before cutover. Require a root-owned `PEXELS_API_KEY` without
printing it. Run schema-bound canaries for `product_brief`,
`product_brief_revision`, and `ad_creative_batch`, then a non-persisting Pexels
download/render canary before the irreversible reset.

After deploy, run the dependency and live-console audits, then an exact-owner
desktop/360 px journey: create Brief, correct, approve with honor confirmation,
observe five Ads, load each authenticated image and attribution, submit feedback,
inspect dormant Landing, and inspect Admin. Verify restart recovery, retired
routes/containers/tables, canonical skills, no extra provider calls, and no OOM.

Never run Landing-specific suites during the Stage 1–2 milestone.
