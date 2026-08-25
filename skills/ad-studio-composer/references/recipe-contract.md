# StudioRecipeV2 and StudioTemplateV2 contract

The server assigns the immutable recipe UUIDv7, Project/Brief/brand-kit IDs,
canvas dimensions, renderer version, and canonical digest. Recipe v1 remains
readable during migration but new samples and revisions use v2.

The submitted document contains exactly:

```text
schema_version: 2
parent_recipe_id: UUID | null
placement_tool_id: catalog placement ID
duration_seconds: 3..30 for motion | null for static
frame_rate: 24 | 25 | 30 for motion | null for static
frames: 1..64 ordered visual frame instances
modifier_tool_ids: layout/color/effect/motion catalog IDs
strategy_ids: catalog strategy IDs
validation_ids: every required catalog guard ID
source_reference_ids: approved ManyPixels provenance URLs
share: {caption, alt_text}
```

Each tool instance contains exactly:

```text
instance_id: UUIDv7
tool_id: non-deprecated visual frame ID compatible with the placement
frame: normalized x, y, width, height inside 0..1
z_index: unique integer
params: tool parameters
timeline: {start, end} for motion | null
source_asset_ids: Project source UUIDs
```

Require exactly one `studio.frame.offer.v1` and one
`studio.frame.cta.v1`; their `text` values equal the approved Brief exactly.
Validate caption and alt text for the same unsupported-proof rules. Caption must
retain the exact offer. Renderers must wrap and fit Unicode text inside its
frame and reject overflow rather than truncate protected copy.
Published artifacts retain the recipe digest, invoked IDs, instance UUIDs,
parameter digests, source lineage, brand-kit revision, renderer version, and
output digest in PostgreSQL, a JSON sidecar, and compact embedded metadata.

Templates are immutable and Project-scoped. A v2 frame/share/source value is
either a validated literal or one typed binding from `brief.offer`, `brief.cta`,
`brief.key_benefits[n]`, `brief.trust_strategy`, `creative.hook`,
`creative.primary_text`, `creative.image_description`, `creative.photo`, or
`brand.logo`. Applying a template requires a completed Creative of the declared
angle from the selected approved Brief and resolves bindings before the recipe
is persisted.

One `StudioSampleSet` contains exactly the ordered angles `emotional`,
`practical`, `curiosity`, `authority`, and `problem_first`. Every item retains
its source Creative, template, root recipe, current render, caption, alt text,
and source lineage. Partial construction is never listed as complete.

One `StudioWizardProposalV1` retains the base recipe digest, instruction,
optional selected instance, typed patch, before/after digest, preview bytes,
skill snapshot digest, generated-source lineage when present, and terminal
Apply/Reject state. Apply is idempotent and creates one child recipe.
