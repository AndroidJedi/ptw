# Instagram static recipe and render adapter

Status: internal Result adapter; no standalone Studio product

## Boundary

`StudioRecipeV2` is the structured visual contract used only by
`instagram_static_ad_v1`. There is no Studio workspace, Wizard, manual editor,
template gallery, validation loop, publication flow, video path, or legacy
recipe compatibility.

The channel-neutral Result core gives the adapter a validated candidate,
server-assigned visual-element UUIDs, Project brand kit, and approved sources.
The adapter resolves real photography from approved Project assets or Pexels,
maps components to a static recipe, validates it, renders the exact JPEG, and
returns recipe/render IDs and digests. Instagram-specific placement, safe area,
frame grammar, and 1080×1080 rendering never enter the generic orchestrator.

## Contract

A recipe binds one Project, approved Brief, immutable brand-kit revision,
placement `instagram.feed_square.v1`, ordered UUIDv7 frame instances, approved
source IDs, caption, alt text, guards, renderer version, and canonical digest.
Required visual roles are background, primary subject, headline, supporting
text, offer, CTA, and brand mark. Badge and decorative elements are optional.

The exact protected offer and CTA must be present and readable. Media ownership,
MIME, digest, crop, source, real-photo, brand, safe-area, collision, contrast,
text overflow, caption, and accessibility checks fail closed before a candidate
can reach the critic.

Pillow deterministically produces one 1080×1080 JPEG. Exact bytes, SHA-256,
recipe, render attempt, media attribution, and graph edges are stored in
PostgreSQL. The critic receives the exact rendered bytes as a digest-mapped
private JPEG attachment; raw base64 is not inserted into its prompt.

An explicitly authorized non-human graphic may use the single-call reviewed
graphic bridge. Synthetic people/faces, embedded copy, logos, and watermarks
are prohibited. An ambiguous graphic call terminates the run and is never
retried automatically.
