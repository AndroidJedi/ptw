---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, owner-reviewed Creatives, Commander, Validation, the platform bridge, PostgreSQL, Pexels, deterministic rendering, and the existing Telegram emergency and notification boundary.
---

# PTW Owner Console Incident

Trace a public symptom through browser → Firebase Hosting/Caddy → Owner Gateway
→ Validation → PostgreSQL or the independent structured bridge/Pexels API. A
healthy Gateway alone does not prove Product Brief, Creative review, export, or
notification readiness.

## Public boundary

- Verify hashed bundles, current owner-review service-worker cache, Firebase
  Auth persistence, App Check, exact Owner CORS origins, and unauthenticated
  rejection.
- The normal Result journey exposes one approved Brief, one create action, five
  authenticated Creative cards, card selection, Approve, Regenerate all, Tune
  with comment, notification state/retry, owner-action/rule history, and an
  approved native post/export. It exposes no task field, subjective evaluation,
  comparison, automatic selection, or manual UUID field.
- Keep Social posts focused on creation and review in production and loopback.
  Never add Project asset upload/Pexels sourcing, a duplicate local-evidence or
  run/snapshot-history panel, or backend integrity/evaluator disclaimers to its
  create form. Asset work belongs to the Studio flow; integrity checks remain
  enforced server-side. For a recurrence, remove associated state, requests,
  handlers, and CSS as well as markup, then cover local mode with a web test.
- Result images and exports are owner-authenticated. Validate stored bytes,
  SHA-256, dimensions, MIME type, proxy equality, and private no-store headers.
- When a Pexels asset is persisted as JPEG, request the CDN representation with
  an explicit JPEG format and verify both the response Content-Type and decoded
  bytes before returning it to a caller. Never infer MIME from the provider URL
  or label provider bytes with a hard-coded MIME before this boundary passes.
- Ads, batches, retired Studio routes, Landing, Admin/Jobs, Positioning,
  publishing, campaigns, traffic, UTM, and public lead routes remain absent.

## Generation and review checks

- Product Brief remains raw idea → strict immutable hypothesis → correction →
  explicit owner approval. Result learning never changes Brief generation.
- Context contains only the approved Brief, fixed task Source, Project brand
  kit/assets, bounded tools, one strategy, deterministic references, exact
  sliders, and immutable Project learning snapshot.
- Initial and Regenerate-all runs call the generator exactly five times. Tune
  calls it once and carries four Creative IDs. Provider CandidateV2 is transient;
  only validated/rendered Creative UUIDs enter persistence and feedback.
- Before `awaiting_review`, require exact protected copy, correct language,
  honest claims, approved/Pexels media, strict nine-role static-social output,
  Studio recipe/render replay, clipping/collision/layout safety, and five
  distinct document/render/media identities. Fail closed on any violation.
- A run has `generated_creative_ids`, exactly five `review_creative_ids`, optional
  `approved_creative_id`, generation kind, learning snapshot, and delivery
  receipt. Valid statuses are queued, generating, awaiting_review, approved,
  superseded, failed, plus local terminated.
- Actions use request UUID idempotency and row locking. Concurrent or stale
  actions return 409. A parent becomes superseded only after a child is fully
  reviewable; failed or terminated children must mark the action failed and
  leave the parent actionable.
- Approve appends accepted HumanFeedback, WeightUpdate, outcome, preferred
  direction/sliders, output-profile-scoped layout rule, graph edges, and export
  unlock. Regenerate all appends five rejection feedback/weights and active
  exploration exclusions. Tune persists exact 3–2000 character instruction,
  positive strategy preference, one replacement, and lineage.
- Rules and snapshots are immutable and Project-scoped. New rules supersede by
  graph lineage; never update a rule or component row silently.

## Notification boundary

- Validation persists the receipt before invoking the typed Commander relay.
  The relay resolves the owner chat server-side and sends one Project/platform
  message containing “five posts ready” and the authenticated console deep link.
- Production requires the authenticated Commander relay. Loopback local review
  must not read production Telegram credentials or fail run admission when the
  relay is absent: persist `not_configured`, generate the five-card web review,
  and create no delivery receipt. Never fake a delivered notification. If both
  endpoint and bridge token are explicitly supplied, use the same typed relay.
- Retry definite delivery failures boundedly. Do not auto-repeat an ambiguous
  send. A failed notification must leave the five-card web review available and
  expose an authenticated manual retry.
- Telegram inbound routing remains only `/help`, `/status`, and `/stop`; every
  other input returns the web-console link and cannot mutate review state.
  Never add another poller/webhook or print/rotate the existing token.

## Failure and restart handling

- Persist checkpoints after generation and rendering steps. On restart resume
  queued/generating child runs and pending/definite-failure notification
  deliveries without duplicating Creatives or ambiguous sends.
- Preserve exact provider request IDs and failed retry provenance. A malformed
  Candidate receives only the bounded fresh retry; ambiguous media generation
  is never repeated.
- Candidate source IDs must be constrained to server allowlists and rechecked at
  the domain boundary. Protected offer/CTA must match Brief, Candidate, recipe,
  rendered text, Creative, and export byte-for-byte.
- When five renders are not distinct, inspect template snapshots, asset/media
  identities, decoded pixels, and Studio bindings. Never introduce subjective
  selection or renderer branches to mask template sameness.
- Any FastAPI route scheduling async background work must be async and covered
  by built-image HTTP regression. Busy admission and persistence must be atomic.

## Release acceptance

Run clean-schema and bridge checks, Pexels policy checks, built-image Validation
and Owner Gateway tests, Commander tests/demo, skill verification, web
unit/build/Playwright desktop and mobile, restart/idempotency/notification
tests, compilation, and `git diff --check`. Before claiming Telegram works in
production, verify authorization, deployed help/routing, provider readiness,
real delivery, persistence, restart behavior, and user-facing failure paths.
