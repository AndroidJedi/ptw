# Universal Ad Studio

Status: implemented locally, including owner-only Tune mode; not deployed

## Product boundary

Studio exposes one universal advertising template. It is a fast configuration
surface for validation creatives, not a template library, reference-matching
tool, or arbitrary component-tree editor. The normal workflow has no example
upload, pixel matching, calibration iteration, primitive creation, layer
mutation, or template import route.

The historical production `StudioRecipeV2` JPEG path remains unchanged. The
universal template renders through the existing generic
`StudioRenderer.render_preview()` primitive path, so text, image fit, focal
crop, alpha, transforms, layering, fonts, deterministic PNG bytes, and visible
bounds are reused rather than reimplemented. The primitive catalog and its two
engineering benchmarks remain internal renderer verification tools; they are
not owner-facing templates.

The loopback app also has an explicit `Tune mode`. It is a development tool,
not another production template or generation path. Its Test generation wizard
collects one project idea, the desired implementation, and optional feedback
for the next iteration. It can revise Universal Studio rendering code, focused
tests, styles, and Studio UI components, including its own wizard UI. It cannot
change the Tune runner, launcher, authentication, production routes, Result
adapter, database, deployment, or publication controls.

`skills/studio-tune-local/SKILL.md` makes the loopback/local checkout the
default target for every owner-requested Studio tuning update. Remote, staging,
production, commit, push, pull-request, and deployment actions remain absent
unless the owner explicitly requests the specific non-local operation.

## Fixed semantic structure

`universal_ad` has exactly seven stable semantic roles:

- background;
- optional sticker;
- hero title;
- supporting text;
- optional bullet list with at most three compact items;
- CTA;
- optional logo.

The internal primitive tree is built by
`validation_pipeline.studio_universal.build_universal_template()` and is never
accepted from an API caller. Variation comes only from
`ptw.studio.universal-ad-config.v1`, whose strict groups control background,
typography, content position and spacing, bullets, CTA treatment, the one
sticker, and the optional logo. Unknown fields and values outside meaningful
bounds fail closed.

Existing Product Brief/Candidate generation remains the copy authority.
`universal_content_from_generation()` maps its headline, primary/supporting
text, CTA, and up to three Brief benefits into the fixed Studio roles without
another provider call or a duplicate generation skill.

## Background and assets

The background supports solid, deterministic paper/grain texture, and photo
modes. Photo layout is full, left, right, top, or bottom with cover/contain,
focal point, and a bounded readability overlay.

There are exactly three external asset slots: `background_image`,
`sticker_object`, and `logo`. Background and sticker searches reuse the
existing bounded Pexels client and retain provider ID, source URL,
photographer, license, query, and transformation provenance. Pexels sticker
objects pass through one deterministic edge-color soft-alpha cutout. The
renderer gives the isolated alpha silhouette a smooth white die-cut contour
approximately 5–8% of the actual fitted visible subject width, followed by a
subtle soft shadow immediately outside that contour. The renderer reserves
transparent room around the subject before expanding its alpha silhouette, so
edge-touching cutouts retain a continuous rounded contour instead of clipping
into a rectangular patch. Only the final edge is narrowly antialiased; neither
the silhouette nor the object is pre-blurred into a glow. There is no
rectangular paper backing. That
transform is suitable for simple object shots; complex scenes must use an
owner-supplied transparent PNG/WebP. There is no second sticker system.

Disabled sticker, bullets, and logo nodes remain semantically mapped but do not
render. Enabling a photo, sticker, or logo without its fixed asset fails the
preview visibly instead of inventing a substitute.

The local Tune snapshot opens with a concrete Ukrainian investment-assistant
experiment: one editorial photo background, one golden hryvnia-symbol sticker,
three benefit callouts, and no logo. The two generated bitmap assets are bundled with Studio
and reported with explicit `bundled_tune_asset` provenance; an owner upload or
Pexels selection in the same fixed slots still overrides them. This is starter
state for the local experiment, not a new template or Instagram behavior.

## Visual layout quality

Primitive text is positioned by its rendered glyph ink rather than nominal font
line boxes. Top-aligned text therefore begins at the requested coordinate, and
shrink fitting accounts for actual ink height, nominal line spacing, and all
wrapped source lines.
Resolved previews report the fitted font size, rendered/source line counts,
truncation, and overflow for each text node. Focused regression coverage keeps
the representative hero title inside its frame and visibly separated from the
supporting block.

The canonical `studio-ui-visual-audit` skill distinguishes raw creative defects
from browser-preview defects and runs a deterministic geometry matrix across the
default, high-density, and centered/minimal configurations. It rejects text
overflow or truncation, edge-touch clipping, semantic-flow collisions, and CTA
safe-area escapes before full-resolution inspection.

## Persistence and routes

`UniversalStudioWorkspace` persists one current configuration, semantic
content, fixed-slot assets, provider provenance, and append-only immutable
versions below `STUDIO_WORKSPACE_PATH`. Each state digest covers configuration,
content, asset digests, and source metadata. Optimistic writes reject stale
state.

The editor presents the seven stable roles in one component dock. Background,
headline, supporting copy, and CTA are always-on cards; bullets, sticker, and
logo are direct optional switches. Detailed visual settings use compact native
disclosures so the live creative remains the primary evaluation surface.
Sticker and logo cannot be enabled before their fixed asset is available.

Editor changes are previewed before save. After a short debounce, the client
posts the current state digest with a complete draft configuration/content pair
to `POST /studio/preview`. The workspace normalizes and renders that pair in
memory without changing persisted state. Stale client responses are ignored,
and explicit `POST /studio/configuration` remains the only current-state write.
The preview panel reports rendering, unsaved-preview success, and failure next
to the creative.

Approval stores the exact PNG, reusable configuration, semantic content, asset
digests/provenance, internal primitive-template snapshot and digest, and render
digest in `ptw.studio.universal-ad-version.v1`. This local version is suitable
as an exact validation-experiment asset; it does not publish or mutate the
production Result lifecycle.

The production authenticated Studio route surface is only:

```text
GET  /studio
POST /studio/configuration
POST /studio/assets/{slot}
POST /studio/pexels
POST /studio/preview
POST /studio/approve
GET  /studio/versions/{version}/render
```

All PNG responses are private, no-store, SHA-256 and ETag explicit. There are
no `/studio/templates`, reference, calibration, or arbitrary-operation routes.

When and only when `STUDIO_TUNE_MODE=1`, the loopback app additionally mounts:

```text
GET  /studio/tune
POST /studio/tune-runs
GET  /studio/tune-runs/{run_id}
GET  /studio/tune-runs/{run_id}/preview
POST /studio/tune-runs/{run_id}/rules
```

Each run mirrors the owner's current tracked and untracked source into an
ignored disposable Git checkout. Codex runs non-interactively with the
`workspace-write` sandbox in that mirror. The host rejects every path outside
the explicit Universal Studio allowlist, rejects deletions and symlink copy-back,
and strips provider/deployment secrets from the agent and verification process
environment. It runs focused Studio Python and web tests, the Owner Console
production build, and whitespace validation, and copies changes back atomically
only if the corresponding owner files have not changed during the run.
Interrupted runs fail durably and never copy a partial unverified diff into the
checkout.

Every completed run also renders the resulting default 1080×1080 Studio creative
inside its retained isolated snapshot. The exact PNG is stored as a run-scoped
artifact with SHA-256, dimensions, private no-store delivery, and an exact ETag.
The Tune completion card loads that authenticated artifact directly beside the
agent report. Existing completed runs are backfilled from their retained snapshots
when first inspected; the card never substitutes a generic or stale workspace
preview.

The review screen keeps the preview and dedicated next-iteration feedback
textarea together before any run report and applies feedback without discarding
the original project idea or implementation. Completed iterations show the exact
run-scoped artifact. Safely stopped iterations show the current Studio render so
the owner still has a concrete visual target; their raw runner traceback remains
available in the durable local run record but is not exposed in the UI. A clear
Back to Studio action closes the dialog, and the persistent Feedback & iterations
control reopens the latest run, preview, report, and feedback workflow after
reload. Starting a genuinely new direction remains a separate explicit action.

The review panel also offers `Save as reusable rule`. This is a separate,
explicit owner approval—not part of ordinary feedback submission. It promotes
the current feedback—or, when the next-feedback field is empty, the feedback
that produced the completed iteration—into
`skills/studio-tune-local/references/owner-approved-rules.md`, records the
content digest on the originating run, and deduplicates equivalent rules. The
canonical skill requires future Tune agents to read those rules and preserve
observable ones with focused regression coverage. The agent itself still cannot
write the skill tree; only the authenticated loopback host action can perform
this bounded local mutation, and production does not mount the route.

## Local use

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
npm --prefix apps/commander-web ci
scripts/run_local_studio.sh
```

Open `http://127.0.0.1:5173/?e2e=1`. The complete visible Owner app runs
locally: Product Briefs and Instagram post use one clearly marked deterministic
demonstration journey, while Universal Ad Studio remains the writable local
workspace. The launcher enables the local-only Test generation wizard when an
authenticated Codex CLI and the local Python/web dependencies are available.
Provider-backed Brief/Result generation is disabled in standalone mode. The
loopback API binds only to `127.0.0.1`; Firebase, PostgreSQL, and production
credentials are not required. Supplying a local `PEXELS_API_KEY` enables the
bounded Studio sourcing controls. No deployment, database mutation,
publication, or automatic promotion occurs.
