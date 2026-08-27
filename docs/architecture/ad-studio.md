# Instagram static recipe and render adapter

Status: internal agent-controlled component system; no standalone Studio product

## Boundary

`StudioRecipeV2` is the structured visual contract used only by
`instagram_static_ad_v1`. There is no Studio workspace, Wizard, manual editor,
template gallery, validation loop, publication flow, or video path. Historical
v1 recipes and renders remain immutable and keep their original renderer
behavior.

The channel-neutral Result core gives the adapter a validated candidate,
server-assigned visual-element UUIDs, the automatically provisioned canonical
Natal brand kit, and approved sources.
The adapter resolves real photography from approved Project assets or Pexels,
applies one of five Git-owned component templates, validates it, renders the exact JPEG, and
returns recipe/render IDs and digests. Instagram-specific placement, safe area,
frame grammar, and 1080×1080 rendering never enter the generic orchestrator.

The internal catalog defines media, logo, headline, body, offer, CTA, badge,
and shape tools with stable IDs, handlers, exact parameter schemas, defaults,
bounds, square-placement allowlists, and tunable paths. Templates identify
components by readable keys, not persisted UUIDs. Application reserves fresh
UUIDv7 instances, resolves only canonical Natal palette/Inter/logo and approved
media bindings, then converts exact sliders to quantized typed patches. There
are no template-specific branches in `StudioRenderer`.

The five component families are deliberately structural: full-bleed photo
tension, opposing split contrast, framed mechanism/proof, full-photo editorial
story card, and typography-first direct offer with a secondary image card.
Each slider controls declared component paths and no others. Optional decoration
is bounded by explicit thresholds.

## Contract

A recipe binds one Project, approved Brief, immutable Natal brand-kit revision,
placement `instagram.feed_square.v1`, ordered UUIDv7 frame instances, approved
source IDs, caption, alt text, guards, renderer version, and canonical digest.
Required visual roles are background, primary subject, headline, supporting
text, offer, CTA, and brand mark. Badge and decorative elements are optional.

The exact protected offer and CTA must be present and readable. Media ownership,
MIME, digest, crop, source, real-photo, brand, safe-area, collision, contrast,
text overflow, caption, and accessibility checks fail closed before a candidate
can reach the critic.

Pillow deterministically produces one 1080×1080 JPEG. Exact bytes, SHA-256,
complete resolved recipe, render attempt, media attribution, enriched manifest,
and graph edges are stored in
PostgreSQL. The critic receives the exact rendered bytes as a digest-mapped
private JPEG attachment; raw base64 is not inserted into its prompt.

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
