# PTW owner-reviewed five-Creative architecture

## Flow

```text
approved Product Brief + fixed social task + Project brand/assets
  -> immutable Project learning snapshot
  -> five isolated transient CandidateV2 calls
  -> deterministic validation, recipe materialization, and rendering
  -> five immutable reviewable Creatives
  -> Telegram notification with authenticated web deep link
  -> owner Approve | Regenerate all | Tune selected with comment
```

There is no automated evaluation, score, rank, eligibility decision, comparison,
improvement action, or final selection. The owner interaction is the learning
event. CandidateV2 is only the provider response contract; it is never a durable
review identity.

## Generation boundary

`ContentContextAssembler` selects the approved Brief, fixed task Source,
Project brand kit/assets, bounded tool catalog, deterministic writing bundle,
one strategy/template snapshot, exact sliders, and the immutable active Project
learning snapshot. Instagram and TikTok also load the complete Git-pinned
`post-copy-style` reference. That reference teaches structure and rhythm only;
the Brief remains sole authority for facts, claims, offer, CTA, brand, and
language.

Initial and Regenerate-all runs reserve five Creative UUIDv7 IDs and make exactly
five isolated `content_candidate_generation` calls, with JSON concurrency at
most two and one fresh retry per malformed response. Tune reserves one new
Creative UUID, calls the selected strategy once with the exact 3–2000 character
owner instruction, replaces that slot, and carries the other four IDs unchanged.
The global deadline remains 45 minutes.

The active strategies are `moment_tension@3`, `contrast_reframe@3`,
`mechanism_proof@3`, `human_story@3`, and `direct_offer@3`. Each is digest-bound
to a matching Git-owned Studio component snapshot. Slider-to-component patches
are typed, bounded, quantized, and cannot change protected copy, component IDs,
tool IDs, palette authority, source assets, or undeclared paths.

## Deterministic integrity

Before persistence as a Creative, server code requires:

- complete CandidateV2 schema and exact server allowlisted source IDs;
- byte-exact protected offer and CTA;
- copy dominated by the approved Brief language;
- honest supported claims and no invented proof, urgency, scarcity, or actors;
- approved Project/Pexels media authority and no synthetic people/faces;
- exact required static-social visual roles and protected Studio bindings;
- reproducible recipe/manifest/render digests;
- safe area, overflow, truncation, collision, contrast, legibility, caption,
  and factual alt text;
- five distinct Creative/document/render/media identities for every review set.

These are binary integrity checks, not subjective quality judgments. Any failure
stops generation before owner notification.

## Local Universal profile

The loopback `universal_ad_experiment_v1` profile captures one saved Studio
export and uses the same five strategies. It sources exactly three fresh,
distinct Pexels photos, one deterministic texture, and one solid direction. A
visible sticker comes only from a screened Pexels photograph of a physical
object and retains source/isolation/texture-alignment provenance. Missing or
reused provider media fails closed; no generated, procedural, bundled, or
repeated fallback is allowed.

Every local Creative retains an authoritative 1080×1080 PNG and deterministic
full-size JPEG. The set-level audit checks unique setting signatures, background
and asset identities, optional-role state, and minimum decoded-pixel distance.
There is no reduced analysis derivative and no image attachment transport.

Local authority is append-only below `.local/owner-experiments`. Local
`terminated` is available only for queued/generating runs and kills the exact
Codex process group. Retry creates a new immutable generation run. Production
has no terminate action.

## Review actions and failure semantics

A successful run becomes `awaiting_review` with `generated_creative_ids`,
exactly five `review_creative_ids`, generation kind, learning snapshot identity,
and persisted notification state. Its review set remains actionable until an
Approve transaction completes or a Tune/Regenerate child successfully reaches
`awaiting_review`.

Request UUIDs make each action idempotent. Run locking rejects stale or
concurrent actions with 409. A failed or terminated child marks its review
action failed and does not supersede or strand the parent.

- Approve resolves the selected Creative UUID, appends accepted HumanFeedback,
  WeightUpdate, outcome, preferred strategy/sliders, output-profile-scoped
  layout rule, and graph edges, then marks the run/Creative approved and unlocks
  the authenticated ZIP export.
- Regenerate all appends rejected feedback and WeightUpdates for all five,
  activates exploration exclusions covering Creative/document/render/media/
  provider identities, and creates five fresh directions.
- Tune appends `tune_requested` feedback, a positive preference for the selected
  direction, the exact comment, and one replacement child.

Rules are Project scoped; copy/tune guidance is additionally strategy scoped,
and layout settings are output-profile scoped. Rules and snapshots are
append-only and supersede through graph lineage. Product Brief generation does
not consume Result rules.

## Notification and export

The delivery receipt is persisted before the typed Commander relay is invoked.
Commander resolves the owner chat server-side and sends one text containing
Project, platform, “five posts ready,” and the authenticated Owner Console deep
link. Definite failures retry boundedly; ambiguous sends do not auto-repeat.
Delivery failure leaves the web review available and exposes manual retry.
Telegram accepts no review action and retains only `/help`, `/status`, `/stop`.

Only the approved Creative has an authenticated export. The deterministic ZIP
contains the native post image and `owner-review.json` with Project, Brief, run,
Creative, document, and asset digests. Downloads append an outcome and never
publish to a platform.

## Persistence

The clean baseline persists runs, Creatives, previews, elements and
Creative-element membership, review actions, HumanFeedback, WeightUpdates,
learning rules/snapshots, notification receipts, outcomes, checkpoints,
attempts/invocations, Studio recipes/renders, entities, sources, and explicit
`evaluates`, `contains`, `derived_from`, `adjusts`, and `supersedes` edges.
Bounded lifecycle fields update; domain evidence is append-only.
