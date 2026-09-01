# Static social recipe and render adapters

Status: production Result adapter plus separate local Universal Ad Studio

## Boundary

`StudioRecipeV2` is the static visual contract used by the channel adapters.
`instagram_static_ad_v1` retains its 1080×1080 placement, renderer identity,
template digests, and byte-exact historical replay. The local
`tiktok_photo_post_v1` adapter adds a 1080×1920 placement and five separate
version-3 vertical snapshots. Historical v1 recipes and renders remain immutable
and keep their original renderer behavior. The separate owner-only Universal
Ad Studio exposes one `universal_ad` structure through
`ptw.studio.universal-ad-config.v4`; it does not mutate deployed
`StudioRecipeV2` snapshots or add a publication/video path. See
[`universal-ad-studio.md`](universal-ad-studio.md).

The local universal template reuses the generic primitive preview renderer as
an internal implementation detail. Its API cannot import templates, mutate a
tree, upload references, or record calibration iterations. Immutable local
versions remain outside the historical Result JPEG path.

For local agent access and later learning, every Universal Studio role has one
stable namespaced component ID. Its canonical component-settings JSON maps that
ID to renderer node IDs, fixed asset-slot IDs, stable leaf setting IDs, and the
exact selected typed values. Current/draft and immutable-version endpoints,
resolved preview manifests, Tune run context, and the owner JSON export all use
that same metadata contract. This does not alter production `StudioRecipeV2`,
its component UUID authority, or the Instagram adapter.

The channel-neutral Result core gives the adapter a validated candidate,
server-assigned visual-element UUIDs, the automatically provisioned canonical
Natal brand kit, and approved sources.
Each adapter resolves real photography from approved Project assets or Pexels,
applies one of five Git-owned component templates, validates it, renders the exact JPEG, and
returns recipe/render IDs and digests. Platform placement, safe area, copy
limits, template registry, and dimensions never enter the generic orchestrator.

The internal catalog defines media, logo, headline, body, offer, CTA, badge,
and shape tools with stable IDs, handlers, exact parameter schemas, defaults,
bounds, profile-specific placement allowlists, and tunable paths. Templates identify
components by readable keys, not persisted UUIDs. Application reserves fresh
UUIDv7 instances, resolves only canonical Natal palette/Inter/logo and approved
media bindings, then converts exact sliders to quantized typed patches. There
are no template-specific branches in `StudioRenderer`.

The five component families are deliberately structural: full-bleed photo
tension, opposing split contrast, framed mechanism/proof, full-photo editorial
story card, and typography-first direct offer with a secondary image card.
Each slider controls declared component paths and no others. Optional decoration
is bounded by explicit thresholds.

Active strategy and Studio definitions are synchronized at version 3. The
candidate generator receives the complete immutable Studio snapshot and must
describe that composition rather than propose an alternate one. Visible
headline and mechanism copy bind to `CandidateV2.headline` and
`CandidateV2.primary_text`; v2 snapshots retain their historical hook and
supporting-text bindings during replay. Static localized decoration is rejected,
and the canonical dark Natal logo must have a topmost containing light surface.

## Contract

A recipe binds one Project, approved Brief, immutable Natal brand-kit revision,
one fixed square or vertical-photo placement, ordered UUIDv7 frame instances, approved
source IDs, caption, alt text, guards, renderer version, and canonical digest.
Required visual roles are background, primary subject, headline, supporting
text, offer, CTA, and brand mark. Badge and decorative elements are optional.

The exact protected offer and CTA must be present and readable. Media ownership,
MIME, digest, crop, source, real-photo, brand, safe-area, collision, contrast,
text overflow, caption, and accessibility checks fail closed before a transient
CandidateV2 becomes a reviewable Creative.

Pillow deterministically produces one profile-sized JPEG: 1080×1080 for
Instagram or 1080×1920 for TikTok. Exact bytes, SHA-256,
complete resolved recipe, render attempt, media attribution, enriched manifest,
and graph edges are stored in PostgreSQL. The owner loads those exact bytes
through an authenticated Creative asset route; raw base64 never enters prompts
or browser JSON.

One `studio.layout.template_application.v1` modifier stores the strategy,
Studio template, catalog, and renderer identities; immutable template snapshot;
slider values; component instance map; protected bindings; ordered patch; and
parent lineage. A non-persisting production canary renders all five from one
input, checks structural signatures and pairwise decoded-pixel distinction,
replays every recipe, and verifies manifest completeness.

An explicitly authorized non-human graphic may use the single-call reviewed
graphic bridge. Synthetic people/faces, embedded copy, logos, and watermarks
are prohibited. An ambiguous graphic call terminates the run and is never
retried automatically.
