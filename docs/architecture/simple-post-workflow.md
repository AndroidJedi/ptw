# Simple post workflow

The first streamlined post milestone is local-only. It is available through
`scripts/run_local_studio.sh` and stores its authority below
`.local/post-workspace`. It is not exposed by the production Owner Gateway,
does not add production PostgreSQL tables, and is not a publishing workflow.

## Contract

One completed, owner-approved Product Brief may create exactly one post draft.
The generation agent writes concise Brief-grounded semantic content, selects
bounded Universal Studio settings, and produces one concrete English Pexels
query for a real square photograph. It may not invent proof, metrics,
testimonials, urgency, scarcity, or product capabilities.

The draft uses the same strict `ptw.studio.universal-ad-config.v5` and
`ptw.studio.universal-ad-content.v2` contracts, stable component setting IDs,
Pexels provenance, primitive template, and 1080×1080 `StudioRenderer` output as
Universal Studio. The workflow owns a separate per-post workspace; it does not
read or mutate `.local/studio-workspace`.

## Comment tuning

The owner comment below the preview is sent to one structured local agent. The
agent receives the exact current component settings, bounded setting catalog,
asset summaries, and owner comment. It returns only:

- exact `setting_id` and typed `value` commands corresponding to Studio UI
  controls or semantic content fields; and
- optionally one `background_image` or `sticker_object` Pexels query.

The server validates every command with the same Studio normalizers before it
changes the draft. Visual intent may be expressed naturally: for example,
"pick image with thinking human face" is translated into a concrete
photographic query for a thoughtful person with a clearly visible face.
Unrelated settings remain unchanged. Applied commands and the image query stay
ID-explicit in the owner UI and append-only local history.

The initial local step exposes the background, typography, layout, bullets,
CTA, and content settings. Comment tuning also exposes the exact Sticker
component controls. An add/replace sticker comment must resolve to one
`sticker_object` request for a real Pexels photograph of a physical object;
Studio applies its bounded isolation transform, retains source and transform
provenance, requires provider metadata to match the requested subject, and
enables `configuration.sticker.enabled`. The server narrows the structured
schema for that intent so neither a background request nor a previously stored
Sticker can count as success. For a generic add request, the agent supplies two
different fallback objects and the server stores only the first source that
passes every subject and isolation gate. A comment that names its desired
object has no substitutions. A sticker request may never be imitated by
inserting an emoji, glyph, or label into visible copy.

Logo commands remain unavailable because the generic workflow has no approved
project-specific logo and never substitutes Studio's Natal brand default into
another Project.

## Approval boundary

Generation and comment tuning produce only a mutable draft. Explicit owner
approval captures the exact PNG, configuration, content, component settings,
template digest, source asset provenance, Brief ID, Project ID, and state
digest as one immutable asset. An approved post cannot be tuned again. There
is no export, scheduling, publishing, campaign, traffic, analytics, or
optimization action in this milestone.
