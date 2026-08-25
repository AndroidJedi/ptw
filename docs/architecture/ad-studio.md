# PTW Ad Studio

Status: Studio v2 and the first five-post sample-set rollout are deployed and
verified in production beside the unchanged five-Ad generator
Updated: 2026-08-25

## Boundary

Ad Studio is a Project-scoped, owner-operated composition workspace between
Product Briefs and Ads. It does not replace or add inputs to
`ad_creative_batch`. The current five-angle generator, its Pexels renderer,
learned reruns, and immutable batches remain unchanged until the owner reviews
published Studio examples and separately authorizes a migration.

The Studio is constrained, not freeform: normalized frames can be added,
dragged, resized, reordered, snapped, and timed only inside a selected
placement and its safe zones. Owner Console chrome remains monochrome; the
creative canvas uses the selected Project brand-kit revision.

## Stable catalog and shared recipe

`validation_pipeline/studio.py` owns the append-only semantic tool registry.
Every entry exposes a stable versioned ID, kind, label, parameter JSON Schema,
placement compatibility, renderer handler, defaults, bounds, provenance, and
deprecation state. Existing ID meanings never change. TikTok vertical video is
explicitly a PTW extension of placement-native vertical-video principles, not
a claim derived directly from the Instagram-only references.

`StudioRecipeV1` remains readable for existing drafts. New samples and edits use
`StudioRecipeV2`, which separates ordered visual frames from layout, color, and
effect modifiers and stores validated share caption and alt text. A server-assigned
UUIDv7 revision binds one Project, one approved Brief, one immutable brand-kit
revision, one placement, ordered UUIDv7 tool instances, normalized frames,
optional timelines, source-asset UUIDs, strategy/guard IDs, provenance URLs,
renderer version, and a canonical SHA-256 digest. Frame text supports Unicode
pixel wrapping, auto-fit, explicit line height and maximum lines, horizontal
and vertical alignment, and hard overflow rejection. Offer and CTA are never
truncated. Every edit saves a new
revision and points to its parent through `supersedes` lineage. The exact Brief
offer and CTA are mandatory protected frames; unsupported proof, testimonial,
rating, result, urgency, or scarcity copy is rejected.

## Templates

`StudioTemplateV2` stores typed bindings for Creative hook, photo, and caption;
Brief benefits, trust, offer, and CTA; and the Project brand logo. Applying one
creates fresh UUIDv7 frame instances, resolves bindings server-side, and remains
fully editable. The first canonical sample set contains exactly five ordered
Instagram square templates: emotional, practical, curiosity, authority, and
problem-first.

Templates are immutable, Project-scoped framed compositions. **Save current
template** stores the selected placement, timing, ordered tools, parameters,
frames, and Project source references. It replaces the protected copy with the
literal `{{offer}}` and `{{cta}}` placeholders. Applying a template assigns new
tool-instance UUIDs and resolves those placeholders internally from the
selected approved Brief. The owner never enters database UUIDs manually.

## Sources, rendering, and manifests

Sources are owner-uploaded JPEG, PNG, WebP, MP4, or MOV assets, imported
licensed Pexels photography, packaged canonical-brand assets, or reviewed
non-human generated graphics. Validation performs bounded base64 decoding, MIME
sniffing, image decoding or FFprobe inspection, codec/dimension/duration limits,
and preserves bytes, SHA-256, origin, URI, provider, external ID, photographer,
license, attribution, and metadata. Generated graphics require provider/model,
request, prompt, prompt digest, output digest, and an explicit no-synthetic-people
policy. They may not contain embedded copy, logos, or watermarks. This Studio
allowance does not change the fixed Ad Creative generator's real-photo-only rule.

Pillow creates deterministic static JPEGs, including bounded tint, duotone, and
filter handlers. Project-selected packaged fonts and the selected logo source
control exports. The Validation image also contains bounded FFmpeg/FFprobe
support for H.264 MP4 output without Chromium: uploaded video can be trimmed,
its original audio preserved or muted, UGC caption frames overlaid, and a simple
transition applied. A completed render has one PostgreSQL manifest and one JSON sidecar
endpoint. Its compact recipe UUID, canonical recipe digest, tool IDs, and
manifest schema are embedded in JPEG EXIF or MP4 metadata before the final
artifact digest is calculated. The complete manifest contains every tool
instance, frame/timeline/order, parameter digest, brand-kit/renderer revision,
source origin/license/byte digest, and final output metadata.

Preview and export render real source media and the contained transparent logo
without guides, instance IDs, tool labels, or selection chrome. Edit mode adds
selection, layer, crop/focal, frame, type, color, and share-copy controls around
the same authoritative render history.

Only an explicit **Publish training example** action makes a render eligible
for feedback. Feedback appends HumanFeedback, zero-delta WeightUpdate, graph
edges, and an `ad_studio` lesson proposal. The canonical
`ad-studio-composer` skill and owner lesson file are read through the existing
review-first Plan/Execute flow; nothing learns silently.

## Persistence and rollout

Forward migration `004_ad_studio.sql` adds append-only tables for source assets,
brand-kit revisions, templates, recipe revisions, render attempts, rendered
artifacts/manifests, immutable five-item sample sets, sample-set items, wizard
proposals, publications, and lesson proposals. PostgreSQL
and `contains`, `derived_from`, `supersedes`, `evaluates`, and `adjusts` graph
edges remain authoritative.

The AI bridge retains the three fixed validation modes and advertises separate
`ad_studio_recipe_revision` and `ad_studio_graphic_generation` modes. Preview is
non-mutating. Explicit Apply validates the typed patch and creates one immutable
child recipe and render; generated image bytes cross an authenticated,
digest-checked asset endpoint rather than a shared database or filesystem.

All Studio routes are owner-authenticated and App-Check-protected through Owner
Gateway. A completed `StudioSampleSet` exposes a five-card gallery and a ZIP
with five clean JPEGs, captions, alt text, attribution, and a lineage manifest.
Partial sets remain hidden. There is no publishing to social networks, campaign management,
traffic purchase, music licensing, synthetic voice, UTM, analytics, conversion
tracking, or automatic lesson promotion. Rollout uses additive migrations and
the explicit in-place release path; it must never enter the irreversible
production reset.
