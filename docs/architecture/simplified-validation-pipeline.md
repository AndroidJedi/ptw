# PTW Simplified Validation Pipeline — Phase 1

Status: Phase 1, Validation Projects, and additive Ad Studio are deployed
Updated: 2026-08-25

## Scope

Phase 1 exists to test whether people react positively to one value proposition:

```text
raw idea → Validation Project + Product Brief → owner approval → five Ad Creatives
```

It does not build the product. It does not perform market research, SEO,
YouTube analysis, AI image generation, ad publication, traffic purchase,
campaign/UTM work, analytics, conversion tracking, or Landing generation.
Landing is a dormant Stage 3 placeholder; its three Natal template families and
source assets remain on disk.

## Validation Projects

One initial Product Brief request atomically creates one `ValidationProject`,
its permanent owner-idea Source, and its root Brief. The Project is the durable
workspace aggregate: immutable Brief corrections remain inside it, and every
initial or learned-rerun Ad batch inherits Project membership through its Brief.
Project names begin as a normalized raw-idea excerpt, follow the latest generated
Brief product, and stop changing automatically after an owner rename. This adds
no Project input to the Product Brief provider contract.

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
The approval, one initial creative batch, and reservation of the global
generation guard commit atomically. Repeated approval never creates a second
initial batch.

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

After all feedback lessons from one completed batch are promoted or dismissed,
the owner may explicitly generate one learned rerun. The rerun is a new batch
of exactly five creatives from the same approved Brief; it never overwrites or
supersedes the reviewed batch. A `rerun_of` edge and parent/child batch UUIDs
retain its lineage. One child per source batch plus an idempotent request UUID
prevents duplicate generation. A further learning cycle starts from feedback
on that child batch.

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

## Parallel Ad Studio

The Project-scoped Ad Studio is an additive manual-training path between
Product Briefs and Ads. It does not replace the fixed five-Ad generator or pass
Studio history into its provider call. The owner composes framed static or
vertical-motion recipes with visible versioned tool IDs, saves immutable recipe
revisions and reusable Project templates, renders authoritative artifacts, and
explicitly publishes selected renders as training examples. Saved templates
use protected offer/CTA placeholders and rebind them from the selected approved
Brief. Studio v2 adds typed Creative/Brief/brand bindings, validated captions and
alt text, immutable five-angle sample sets, clean Preview versus instrumented
Edit modes, authoritative render history, and review-before-Apply wizard
proposals. Generated media is confined to an explicitly requested, reviewed,
non-human Studio graphic and never enters the fixed Ad generator. See
[`ad-studio.md`](ad-studio.md) for the catalog, recipe, source,
manifest, persistence, and rollout contracts.

## Authority and lineage

`db/migrations/001_ptw_validation_v1.sql` remains the reset baseline;
`002_lesson_driven_creative_reruns.sql`, `003_validation_projects.sql`, and
`004_ad_studio.sql` are
non-destructive forward migrations. Together they retain the generic graph/source/feedback/weight/
audit/Plan-Execute/control tables plus Brief, approval, attempt, provider
invocation, Project, batch, creative, asset, and the two lesson-proposal tables. No
active Positioning or Landing table exists.

Required edges are:

- Validation Project `derived_from` its owner-idea Source and `contains` every
  immutable Product Brief in its revision lineage.
- Product Brief `derived_from` owner-idea Source.
- Replacement `supersedes` base and `derived_from` feedback.
- Batch `derived_from` approved Brief and `contains` five creatives.
- Learned child batch `rerun_of` its reviewed source batch.
- Creative `derived_from` Brief and `contains` its exact asset.
- Asset `derived_from` permanent Pexels Source.
- Studio sample set `derived_from` one completed batch and `contains` its five
  ordered template, root recipe, render, caption, alt-text, and source lineages.
- Studio child recipe `supersedes` its reviewed base recipe; wizard Apply links
  the immutable proposal to exactly one child recipe and render.
- HumanFeedback `evaluates` the resolved Brief or creative.
- Append-only WeightUpdate `adjusts` that feedback.

PostgreSQL entities, edges, attempts, invocation provenance, source attribution,
and JPEG bytes are the complete authority.

Every correction or creative review still creates its own append-only feedback,
zero-delta weight update, and lesson-proposal UUID. The Owner Console appends
all pending proposals within that generator domain into one editable combined
lesson. One action places every included proposal into `planning` under the
same command-session UUID; one successful execution promotes them together and
updates only that generator's `owner-lessons.md`.

Admin exposes the complete instruction, read-only steps, error, and state for
every future-rule job. A ready job has one labelled Apply action. Cancellation
is limited to active work, uses a labelled control plus explicit browser and
server confirmation, and cannot turn a later planner result into a false
failure. An unexecuted failed or cancelled command can restore the same
completed plan, or regenerate one when no completed plan exists, while
restoring all linked proposals as one atomic group.

The Validation runner reads the canonical skill and owner lessons immediately
before every generation instead of only at process startup. A learned rerun
records the SHA-256 of that complete skill snapshot when it is queued and fails
closed if the file changes before execution. The global operation guard keeps
lesson promotion and generation from racing.

A terminal failed Ad batch reserves one append-only audit event and makes at
most one direct `sendMessage` through the existing allowlisted PTW bot. The
result is appended as sent, failed, ambiguous, or emergency-stop suppressed;
ambiguous sends are never retried automatically. This adds no webhook, poller,
worker, inbound command, or completion notification.

## APIs and workspaces

Owner-authenticated routes provide Project list/rename, Brief create/list/detail/correct/retry/
approve, batch list/detail/retry/learned-rerun, creative feedback, authenticated image
delivery with immutable ETag, Studio catalog/brand-kit/template/source/recipe/render/
manifest/publication/feedback operations, five-post sample-set gallery/ZIP, private
source preview, render history, and preview/Apply wizard proposals. Old Positioning,
Ads-stub, active Landing, lead, catalog, export, and public Landing APIs are not
registered and return 404.

The PWA navigation is Product Briefs → Ad Studio → Ads → Landing → Admin. One URL-backed
Project switcher scopes the first four workspaces; Admin remains global. Ads shows all
five finished posts, UUIDs, retry state, copy, Pexels attribution, digests, and
one feedback control per creative. For a failed batch it shows the validation
rule, approved offer when relevant, atomic rollback outcome, and Telegram
notification status. After a successful retry, the latest failed attempt remains
visible in a recovered-incident summary. Authenticated creative loads verify
the `image/jpeg` media type, exact stored SHA-256, exposed ETag, and browser
decode result before display; failures show the Creative UUID, exact reason,
and a bounded retry. PTW does not create inline `data:image/png` Ad resources.
Landing says `Stage 3 pending`, identifies the selected Project from shell state,
and performs no Landing API call.

For a completed batch, Ads shows the learning lifecycle explicitly. Unfinished
feedback says to apply its future rule in Admin. Applied feedback exposes one
confirmed **Generate new Ads with feedback** action. After creation, the source
batch offers **Open new Ads**, while the child identifies its source batch and
shows normal queued/generating/completed states.

## Deployment boundary

The independent `/opt/ptw/platform` repository retains the three core
validation modes and separately advertises `ad_studio_recipe_revision` and
`ad_studio_graphic_generation`, without sharing Git history, database,
filesystem, or credentials. Generated bytes leave the platform only through
the authenticated digest-checked job asset route. Deploy the enforcing worker
before the Studio-capable platform API, then run strict-schema and asset
canaries before migrating or restarting the Validation stack.

Build matching Linux/amd64 images off-host and deploy serially with a
non-`latest` tag. This rollout uses additive `003`/`004` migrations and the
exact `DEPLOY PTW IN PLACE` release confirmation so existing Briefs, batches,
creatives, assets, feedback, and graph rows are preserved. The reset path and
its destructive confirmation are outside this rollout.
