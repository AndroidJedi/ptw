# Universal Ad Studio

Status: local Studio, evaluation, and owner-approved learning loop implemented;
not deployed

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

`universal_ad` has exactly eight stable semantic roles:

- background;
- optional sticker;
- hero title;
- supporting text;
- required protected offer;
- optional bullet list with at most three compact items;
- CTA;
- optional logo.

The internal primitive tree is built by
`validation_pipeline.studio_universal.build_universal_template()` and is never
accepted from an API caller. Variation comes only from
`ptw.studio.universal-ad-config.v4`, whose strict groups control background,
typography, content position and spacing, bullets, CTA treatment, the one
sticker, and the optional logo. Unknown fields and values outside meaningful
bounds fail closed. Never-deployed local v1/v2/v3 workspace configurations are
upgraded deterministically when read, so existing owner setup is not discarded.

Each role also has a stable public component ID (`universal_ad.background`,
`universal_ad.sticker`, `universal_ad.hero_title`,
`universal_ad.supporting_text`, `universal_ad.offer`, `universal_ad.bullet_list`,
`universal_ad.cta`, and `universal_ad.logo`). Catalog metadata maps each ID to
its semantic role, renderer node IDs, fixed asset-slot IDs, and stable leaf
setting IDs such as `configuration.background.overlay_opacity` or
`configuration.cta.style`.

Existing Product Brief/Candidate generation remains the copy authority.
`universal_content_from_generation()` maps its headline, primary/supporting
text, exact Brief offer, CTA, and up to three Brief benefits into the fixed
Studio roles without another provider call or a duplicate generation skill.
The offer and CTA must render byte-for-byte; overlong protected copy is a Brief
correction error and is never truncated.

## Background and assets

The background supports solid, deterministic grain plus stone, marble,
concrete, granite, slate, and travertine textures, and photo modes. Paper is no
longer offered; an existing local paper selection upgrades to stone. Texture
intensity controls the texture layer independently of the base color. Photo
layout is full, left, right, top, or bottom with cover/contain,
focal point, and explicit 75% image / 25% background or 25% image / 75%
background splits. A bounded readability overlay has visible color and opacity
controls; render-level regression coverage proves that opacity changes pixels.
Image mode places the fixed-slot sample-image upload beside its layout controls
instead of requiring the owner to find the separate asset panel.

There are exactly three external asset slots: `background_image`,
`sticker_object`, and `logo`. Background and sticker searches reuse the
existing bounded Pexels client and retain provider ID, source URL,
photographer, license, query, and transformation provenance. Pexels sticker
objects must be ultra-realistic photographs of physical objects selected to
match the assigned background's light direction and softness, color
temperature, palette, material, surface texture, perspective, grain, and
scale. The provider record, search query, and downloaded source must pass a
fail-closed photographic-object screen before isolation: explicit illustration,
icon, vector, render, emoji, logo, symbol, cartoon, or digital-art language is
rejected, and the source must decode as a full-size opaque JPEG photograph.
Generated, illustrated, vector, procedural, screenshot, owner-uploaded, and
bundled sticker fallbacks are forbidden. The selected photograph passes through
one deterministic edge-color soft-alpha cutout. The
renderer gives the isolated alpha silhouette a smooth white die-cut contour
approximately 5–8% of the actual fitted visible subject width, followed by a
subtle soft shadow immediately outside that contour. The renderer reserves
transparent room around the subject before expanding its alpha silhouette, so
edge-touching cutouts retain a continuous rounded contour instead of clipping
into a rectangular patch. Only the final edge is narrowly antialiased; neither
the silhouette nor the object is pre-blurred into a glow. There is no
rectangular paper backing. If a compatible photographed object cannot be
isolated cleanly, the sticker fails unavailable; there is no direct sticker
upload or second sticker system.

The logo slot resolves to the digest-verified canonical Natal transparent PNG
when the owner has not supplied another asset. New workspaces enable it without
a backing surface at the top right by default. Template v10 removes the backing
node and its editor controls entirely. Stored v4 configuration fields remain
read-compatible but `background_enabled` always normalizes to `false`, so an
old version or layout lesson cannot restore the surface. Its dedicated editor
section keeps PNG/WebP upload, logo visibility, top-left/top-right placement,
and bounded width together. An upload replaces the Natal fallback with
`owner_upload` provenance and enables the logo immediately. Copy moves below
the visible transparent mark only when their horizontal regions intersect;
disabling the logo hides the mark.

Disabled sticker, bullets, and logo nodes remain semantically mapped but do not
render. Enabling a photo, sticker, or logo without its fixed asset fails the
preview visibly instead of inventing a substitute.

Bullets offer check, filled-circle, and outlined-circle markers. Their text can
use a font independently from the headline/supporting-copy family; the marker
is a separate Inter symbol node so ✓, ●, and ○ remain valid when an expressive
benefit font is selected. The bundled mood families are neutral Inter, friendly
Manrope, urgent Oswald, and editorial Cormorant Garamond. Each renders Ukrainian
copy from a repository-owned variable font; the three added families retain
their SIL Open Font License files beside the assets.

CTA text and background colors stay owner-controlled and its treatment is one
of filled, gradient, reverse, link, or outlined. CTA placement is below the text
flow, at the safe bottom-left anchor, or at the safe bottom-right anchor.
Sticker sizing now spans small accents through canvas-scale objects. Its presets
include the four corners, right and bottom edge peeks, and attachment to the
hero title, benefit list, or CTA; bounded right and bottom adjustments from -720
through 720 fine-tune every preset. The editor names this
inspector `Sticker placement` / `Розміщення стікера`. Rotation, width, object
scale, and both offsets each trigger a draft render independently. Numeric
fields retain transient typing locally and send only complete in-range values,
so one unfinished entry cannot invalidate later preview updates.

The local Tune snapshot opens with a deterministic textured background, no
sticker, three benefit callouts, and the canonical Natal logo. Background and
sticker slots begin empty; the bounded Pexels API or an explicit owner upload
must populate them before either role can render. No generated or bundled
background/sticker fallback exists. The logo alone reuses the canonical
digest-pinned brand asset with `canonical_natal_brand_asset` provenance.

## Visual layout quality

Logo, copy, bullet, and CTA geometry shares one composition-alignment
rectangle. Its top and left follow the content controls, while its right and
bottom edges are safe canvas anchors. Top-corner logos and bottom CTA presets
anchor inside those same edges. There is no logo contrast-surface geometry.

Primitive text is positioned by its rendered glyph ink rather than nominal font
line boxes. Top-aligned text therefore begins at the requested coordinate, and
shrink fitting accounts for actual ink height, nominal line spacing, and all
wrapped source lines.
Resolved previews report the fitted font size, rendered/source line counts,
truncation, and overflow for each text node. Focused regression coverage keeps
the representative hero title inside its frame and visibly separated from the
supporting block.

The canonical `studio-ui-visual-audit` skill distinguishes raw creative defects
from browser-preview defects and runs a deterministic geometry matrix across
default, high-density, centered/minimal, editorial bottom-left, urgent
bottom-right, and logo-without-background configurations. It rejects text
overflow or truncation, edge-touch clipping, semantic-flow collisions, CTA
safe-area escapes, any reintroduced logo-surface node, and logo/copy collisions
before full-resolution inspection.

## Persistence and routes

`UniversalStudioWorkspace` persists one current configuration, semantic
content, fixed-slot assets, provider provenance, and append-only immutable
versions below `STUDIO_WORKSPACE_PATH`. Each state digest covers configuration,
content, asset digests, and source metadata. Optimistic writes reject stale
state.

The editor presents the eight stable roles in one component dock. Background,
headline, supporting copy, offer, and CTA are always-on cards; bullets,
sticker, and logo are direct optional switches. Detailed visual settings use compact native
disclosures so the live creative remains the primary evaluation surface.
Sticker and logo cannot be enabled before their fixed asset is available; the
canonical Natal fallback means the logo slot is ready in a new workspace. The
logo disclosure owns its upload, show/hide, position, and size
controls instead of splitting those decisions across unrelated panels.

Editor changes are previewed before save. After a short debounce, the client
posts the current state digest with a complete draft configuration/content pair
to `POST /studio/preview`. The workspace normalizes and renders that pair in
memory without changing persisted state. Stale client responses are ignored,
and returning all draft controls to saved values restores the saved render so a
previous draft PNG cannot remain on screen. This includes disabling and then
re-enabling the default logo. Explicit `POST /studio/configuration` remains the only current-state write.
The preview panel reports rendering, unsaved-preview success, and failure next
to the creative.

Approval stores the exact PNG, reusable configuration, semantic content, asset
digests/provenance, internal primitive-template snapshot and digest, and render
digest in `ptw.studio.universal-ad-version.v2`. It also stores the canonical
`ptw.studio.universal-ad-component-settings.v2` manifest: all eight component
IDs with their node/asset IDs and every exact typed setting value. `GET
/studio/versions/{version}` returns this immutable JSON record for replay and
learning; its paired render remains separately digest-checked. This local version is suitable
as an exact validation-experiment asset; it does not publish or mutate the
production Result lifecycle.

`GET /studio` returns the same canonical component-settings manifest for the
current saved state. `POST /studio/component-settings` accepts either the saved
state digest alone or that digest plus one complete draft configuration/content
pair, normalizes it without persisting, and returns a digest-locked manifest.
The editor's `Export config + IDs` action calls this route and downloads
`ptw.studio.universal-ad-export.v4`, containing configuration, content,
template/catalog identities, the base state digest, and the canonical component
metadata. Resolved preview manifests embed the same metadata beside node geometry.

The production authenticated Studio route surface is only:

```text
GET  /studio
POST /studio/configuration
POST /studio/assets/{slot}
POST /studio/pexels
POST /studio/preview
POST /studio/component-settings
POST /studio/approve
GET  /studio/versions/{version}
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

At run creation, the loopback host captures a bounded
`ptw.studio.universal-ad-agent-context.v2` from the current workspace. It
contains state/template/context digests, exact component settings, and fixed
asset identities/digests/provenance. That JSON is included in the run request
digest, retained in `run.json`, and inserted explicitly into the Tune-agent
prompt as the machine-readable current-state authority. The agent therefore
does not need to infer owner selections from UI labels or an excluded `.local`
workspace, and a later learner can recover the exact input behind the run.

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

## Local owner review and learning authority

The loopback app replaces the former hard-coded Brief/Result demo with the
file-backed `LocalExperimentStore` below `.local/owner-experiments`. Digest-
chained append-only revisions and immutable artifacts persist Projects, Briefs,
approved asset pools, runs, Creatives, elements, exact PNG/JPEG renders,
provider invocations, owner review actions, feedback, WeightUpdates, outcomes,
exports, checkpoints, Project rules, notification receipts, and snapshots.
Writes use temporary files, `fsync`, and atomic replacement; request IDs are
idempotent, UUIDv7 is authoritative, and interrupted queued/generating runs
return to their latest persisted checkpoint on restart.

An approved Product Brief and the digest of the current saved Studio state are
mandatory. Unsaved drafts cannot start a run. The local-only
`universal_ad_experiment_v1` adapter materializes the five canonical strategies
as declared bounded setting patches while preserving component IDs, logo
identity, protected offer/CTA, and safe bounds. Adapter v9 gives every strategy
an intentionally different visible palette, hierarchy, CTA treatment,
composition, and optional-role state. Each run sources exactly three fresh,
distinct Pexels real photographs for `moment_tension`, `contrast_reframe`, and
`human_story`, with separate queries, SHA-256 values, crops, overlays, palettes,
typography, and layouts. The other directions remain one deterministic texture
and one solid direct-offer composition. `contrast_reframe` also receives one
separately sourced ultra-realistic Pexels photo object, deterministically
isolated and directed to match its warm tactile treatment. Same-run recovery
reuses the persisted Pexels IDs; later runs exclude every earlier Project
provider ID and digest. Missing provider configuration, repeated photos, failed
isolation, or incomplete provenance fail closed. Generated, procedural,
repository-bundled, or synthetic image substitutes are never authorized.

The initial set fails before owner notification unless all five setting
signatures and background colors are distinct, exactly three image-backed
directions use three different Pexels IDs, image digests, and treatments, the
one sticker has Pexels/isolation/texture-alignment provenance, no logo backing
node exists, multiple
background modes and four font/CTA treatments are present, and every pair
clears minimum declared-setting and decoded-pixel distances.
Strategy-owned layout lessons replay only onto their originating strategy;
legacy unscoped patches remain textual evidence and cannot overwrite every
direction with one selected recipe.

Each run invokes an authenticated Codex CLI in a new empty directory with an
ephemeral session, read-only sandbox, strict JSON output schema, and one fresh
bounded retry. Persisted provenance contains sanitized inputs/outputs, versions,
IDs, and digests, never authentication, image base64, or hidden reasoning.
CandidateV2 generation uses `content-candidate-generator` exactly five times for
Initial/Regenerate-all and once for Tune. The server performs deterministic
validation and rendering; no render is attached to a subsequent model call.

Every transient CandidateV2 first renders an authoritative 1080×1080 PNG for
geometry inspection, then one deterministic full-size JPEG for owner review and
the export package. Server
gates cover role coverage, overflow, truncation,
collision, safe area, contrast, semantic flow, and exact offer/CTA. Awaiting
review displays exactly five Creative UUIDs. Approve creates accepted feedback,
WeightUpdate, outcome, rules, graph lineage, and one immutable ZIP containing
the JPEG, source PNG, caption, alt text, approved Brief, Universal manifest,
asset provenance, owner-review manifest, and file digests. Regenerate all
records five rejections and generates five fresh directions. Tune records the
exact owner instruction and replaces one slot without overwriting Studio.

Owner actions append Project-scoped learning rules immediately. Tune/copy
guidance is strategy scoped and layout rules are additionally output-profile
scoped. New rules supersede through graph lineage, never row mutation; each
later run stores the exact active snapshot and digest. Product Brief generation
does not consume these rules. The Social Posts learning panel reports only
owner actions, rules, snapshots, and outcomes, without market-performance claims.

The irreversible local reset is deliberately narrower than `.local`:

```sh
scripts/reset_ptw_local.sh --scope owner-experiments \
  --confirm='RESET PTW LOCAL RESULT DATA'
```

It refuses active local Result runs and a running local service from this
checkout, validates the exact target, clears only `.local/owner-experiments`,
and proves it is empty. Studio state, Tune work, diagnostics, and archives are
preserved.

## Local use

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-validation.txt
npm --prefix apps/commander-web ci
scripts/run_local_studio.sh
```

Open `http://127.0.0.1:5173/?e2e=1`. The complete visible Owner app runs
locally with mutable, restart-safe Product Brief, Social Posts, Project asset,
release, and owner-reviewed learning workflows beside Universal Studio and its
Tune wizard. An authenticated Codex CLI is required for Brief and transient
CandidateV2 generation. Firebase, PostgreSQL, and production credentials are not
required. A local `PEXELS_API_KEY` is required before Result creation so the
three photo backgrounds and photographed sticker can be sourced. The loopback
API binds only to `127.0.0.1`; no deployment, production
database mutation, publication, market ingestion, or automatic lesson approval
occurs.
