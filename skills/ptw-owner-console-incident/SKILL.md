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
- Verify active console chrome, the PTW icon, terminal, and Mermaid diagrams use
  only black, white, and neutral grays. Preserve state meaning through contrast,
  borders, patterns, icons, and text; reviewed Ad photos may remain full color.
- Navigation is Product Briefs, Ads, Landing, Admin. Landing shows only
  `Stage 3 pending`.
- Legacy Positioning, research, public Landing/lead, and Ads-stub APIs must
  return 404.
- Image delivery is owner-authenticated and returns the stored JPEG with its
  authoritative ETag.
- Ad Studio has two distinct surfaces: clean Preview and Edit. Preview and
  exported artifacts never contain frame outlines, semantic IDs, tool labels,
  handles, or safe-zone guides. Edit must display the real authenticated source
  media/logo beneath bounded selection chrome; a black canvas or a visible
  `shape`/tool ID is an incident, not a valid preview.
- For clipped Studio copy, compare the browser preview with the authoritative
  render, then verify pixel-based Unicode wrapping, auto-fit bounds, frame
  clipping, media fit/focal settings, and protected offer/CTA overflow. Never
  mask the incident by truncating the approved offer or CTA.
- A visible CTA container does not prove the CTA rendered. After any Pillow
  paste/composite into an RGB canvas, rebind the drawing context before the
  next text layer. Acceptance must inspect the authoritative export and assert
  foreground-text pixels inside every offer/CTA frame; a blank colored button
  blocks the release even when the recipe and manifest contain the exact copy.
- PTW Ad images are fetched as authenticated `image/jpeg` responses and shown
  through browser `blob:` URLs; they are not inline `data:image/png` resources.
  For a load incident, first validate stored bytes, SHA-256, dimensions, HTTP
  media type, ETag, and proxy byte equality. Treat a malformed or truncated
  inline PNG as a separate browser/extension resource unless its provenance to
  PTW is demonstrated. Still expose MIME, integrity, and browser-decode failures
  in Ads with the Creative UUID and a bounded retry.
- Validation Compose injects only its explicit runtime allowlist. Never attach
  whole Owner Gateway, Commander, or platform env files to that container;
  remove retired `DATAFORSEO_`, `POSITIONING_`, `LANDING_`, and `YOUTUBE_`
  settings from the root-owned application env during cutover.

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
  terminal owner-authenticated. Every job must expose its instruction, plan,
  error, and status through an explicit details control. Use labelled Run,
  Restore, and Cancel actions; never represent cancellation with an ambiguous
  checkbox-like icon. Cancellation requires both a browser confirmation and a
  server-validated confirmation payload, applies only to an active job, and
  must not race a completed planner result into a false failed state. An
  unexecuted failed or cancelled lesson plan may restore its preserved plan or
  regenerate it while restoring every linked proposal as one atomic group.
- Keep Jobs as one review-first workflow: describe one job, prepare read-only
  steps, then explicitly run the exact digest-bound steps. Do not expose a
  Plan/Execute mode switch when both choices enter the same planning path.
  Explain feedback lessons as future rules, state that they do not change the
  reviewed artifact or rerun its agent, and keep heavy work serial.

## Failure handling

Restart recovery may fail interrupted Brief or batch attempts and release only
their guard. A failed five-asset preparation stores no creative or asset rows.
Retry only failed targets; approval remains idempotent with one batch per Brief.
Do not bypass schema validation, the global operation guard, App Check, owner
approval, source lineage, or authenticated artifact delivery.

For an offer-continuity failure, compare the approved Brief offer with the exact
structured bridge response, including terminal punctuation. Bind exact CTA and
offer fields in the output schema; require offer wording in visible copy while
allowing surrounding sentence punctuation.

A terminal failed Ad batch may make one audited direct `sendMessage` through
the existing allowlisted bot only after the failure is durable. Reserve the
attempt before sending, never auto-retry ambiguous delivery, suppress under
emergency stop, and expose notification state beside the UI failure reason. Do
not add a webhook, poller, worker, completion notification, or new command.
Inbound commands remain `/help`, `/status`, and `/stop` only.

After retry succeeds, keep the latest failed attempt and its notification state
visible as recovered history; clearing the current batch error must not erase
the owner's explanation.

## Release acceptance

Render Compose before cutover. Require a root-owned `PEXELS_API_KEY` without
printing it. Run schema-bound canaries for `product_brief`,
`product_brief_revision`, and `ad_creative_batch`, then a non-persisting Pexels
download/render canary before the irreversible reset.

Block-framed non-tar release artifacts must declare their exact byte length.
After transport, remove framing padding before checksum verification, bundle
fetch, or another strict parser. Prove the exact platform bundle with a
disposable fetch before streaming it to production.

If the owner explicitly requests a reversible Hosting-only release before the
backend cutover, label it incomplete, verify the cache-busted bundle and service
worker, and expect the full live audit to stop at the legacy API boundary. Never
claim Product Brief/Ads readiness or weaken the backend reset/Pexels gates.

After deploy, run the dependency and live-console audits, then an exact-owner
desktop/360 px journey: create Brief, correct, approve with honor confirmation,
observe five Ads, load each authenticated image and attribution, submit feedback,
inspect dormant Landing, and inspect Admin. Verify restart recovery, retired
routes/containers/tables, canonical skills, no extra provider calls, and no OOM.

Never run Landing-specific suites during the Stage 1–2 milestone.
