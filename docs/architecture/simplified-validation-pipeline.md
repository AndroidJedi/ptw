# PTW Simplified Validation Pipeline — Phase 1

Status: Phase 1 production cutover complete; Natal Ad identity update pending deployment
Updated: 2026-08-24

## Scope

Phase 1 exists to test whether people react positively to one value proposition:

```text
raw idea → Product Brief → owner approval → five Ad Creatives
```

It does not build the product. It does not perform market research, SEO,
YouTube analysis, AI image generation, ad publication, traffic purchase,
campaign/UTM work, analytics, conversion tracking, or Landing generation.
Landing is a dormant Stage 3 placeholder; its three Natal template families and
source assets remain on disk.

## Stage 1 — Product Brief

The only initial business input is `{request_id, raw_idea}`. Output language is
inferred from dominant Ukrainian Cyrillic or Latin characters and defaults to
English when ambiguous. One structured call produces one hypothesis:

```text
brief_id: UUIDv7 (server assigned)
schema_version: 1
language: uk | en
product: string
target_audience: string
main_pain: string
promise: string
key_benefits: string[3..5]
cta: string
trust_strategy: string
offer: string
```

Every Brief must contain one strong, low-friction, honor-able promotion such as
a free first consultation, free assessment, promo code, discount, or early
access. The promotion is marketing, not a change to the proposed product.
Fabricated testimonials, ratings, customer counts, results, credentials,
urgency, and scarcity are rejected.

Correction accepts one base `brief_id`, request UUID, and owner instruction. It
creates a complete immutable replacement with a new UUID. The replacement
`supersedes` the base and `derived_from` its owner feedback and permanent
owner-idea Source. It requires fresh approval.

Approval explicitly confirms that the exact promise and offer can be honored.
The approval, one creative batch, and reservation of the global generation
guard commit atomically. Repeated approval never creates a second batch.

## Stage 2 — Ad Creatives

Stage 2 business input is exactly the approved Product Brief. It never receives
the raw idea, research, market context, previous creatives, performance data,
Landing copy, or campaign data. One structured call returns exactly five
complete creatives in this order:

1. emotional
2. practical
3. curiosity
4. authority
5. problem-first

Each creative contains hook, primary text, image description, exact Brief CTA,
an exact schema-bound Brief offer field, desired emotion, image category,
English image search query, and left/center/right crop focus. The offer wording
must remain visible in the copy, while surrounding sentence punctuation may
follow normal grammar. The server assigns `creative_id` and keeps the `brief_id`
on every record.

Natal is the immutable umbrella identity for every creative. The generator
silently drafts multiple headline candidates for each proposed visual, checks
image/headline semantic alignment, and returns only the strongest hook without
changing the strict schema. Acceptance requires emotion match, narrative
completion, industry specificity, visible human tension, and a frame that can
pass the half-second scroll test without its text overlay. Visual direction
must also retain direction, movement, meaningful symbolism, and immediate
emotional clarity.

## Real-photo artifacts

Pexels is the sole active stock-photo adapter. Its credential stays only in the
root-owned runtime environment. For each creative the adapter searches at most
ten square results, skips small or reused photos, and tries one broader category
fallback. It rejects unsupported MIME, oversized data, images outside the
Pexels CDN, undecodable data, and dimensions below 1080×1080.

The Validation image contains the canonical Inter font and Natal logo. Pillow
performs a deterministic focus crop and applies the Natal near-black, white,
and cyan palette plus the canonical logo, hook, offer, and CTA. It then stores
the exact 1080×1080 JPEG bytes and SHA-256 in PostgreSQL. Source page,
photographer, photographer URL, Pexels license, and attribution remain attached
to the authenticated artifact. If any of five assets fails, no creative or
asset row is persisted.

## Authority and lineage

`db/migrations/001_ptw_validation_v1.sql` is the only reset baseline. It has
generic graph/source/feedback/weight/audit/Plan-Execute/control tables plus
Brief, approval, attempt, provider invocation, batch, creative, asset, and the
two lesson-proposal tables. No active Positioning or Landing table exists.

Required edges are:

- Product Brief `derived_from` owner-idea Source.
- Replacement `supersedes` base and `derived_from` feedback.
- Batch `derived_from` approved Brief and `contains` five creatives.
- Creative `derived_from` Brief and `contains` its exact asset.
- Asset `derived_from` permanent Pexels Source.
- HumanFeedback `evaluates` the resolved Brief or creative.
- Append-only WeightUpdate `adjusts` that feedback.

PostgreSQL entities, edges, attempts, invocation provenance, source attribution,
and JPEG bytes are the complete authority.

A terminal failed Ad batch reserves one append-only audit event and makes at
most one direct `sendMessage` through the existing allowlisted PTW bot. The
result is appended as sent, failed, ambiguous, or emergency-stop suppressed;
ambiguous sends are never retried automatically. This adds no webhook, poller,
worker, inbound command, or completion notification.

## APIs and workspaces

Owner-authenticated routes provide Brief create/list/detail/correct/retry/
approve, batch list/detail/retry, creative feedback, authenticated image
delivery with immutable ETag, and bounded skill proposals. Old Positioning,
Ads-stub, active Landing, lead, catalog, export, and public Landing APIs are not
registered and return 404.

The PWA navigation is Product Briefs → Ads → Landing → Admin. Ads shows all
five finished posts, UUIDs, retry state, copy, Pexels attribution, digests, and
one feedback control per creative. For a failed batch it shows the validation
rule, approved offer when relevant, atomic rollback outcome, and Telegram
notification status. After a successful retry, the latest failed attempt remains
visible in a recovered-incident summary. Authenticated creative loads verify
the `image/jpeg` media type, exact stored SHA-256, exposed ETag, and browser
decode result before display; failures show the Creative UUID, exact reason,
and a bounded retry. PTW does not create inline `data:image/png` Ad resources.
Landing says `Stage 3 pending` and performs no API call.

## Deployment boundary

The independent `/opt/ptw/platform` repository must add the three validation
bridge modes without sharing Git history or database credentials. Before the
irreversible reset, run strict-schema canaries for all modes plus a
non-persisting Pexels download/render canary. Build matching Linux/amd64 images
off-host and deploy serially with a non-`latest` tag.

The reset may drop only `ptw_commander.public` and requires the exact phrase
`RESET PTW PRODUCTION` immediately before destruction. Production remains on
its previous release until that phrase is supplied in an explicit cutover turn.
