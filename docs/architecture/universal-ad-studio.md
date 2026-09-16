# Project-scoped Post Studio

The owner sees Studio as **Post / Допис**. Every creative belongs to one Project
and derives from one approved Product Brief. Studio has no owner-wide singleton
or separate Studio page. Approved versions expose an Instagram publishing/export
panel and an exact-version handoff to **Instagram tests / Instagram-тести**.
[Instagram manual validation](instagram-manual-validation.md) records are separate from editing and learning.
Both renderers and their promotional image CTA controls remain unchanged; a paid
ad's native clickable CTA is configured separately in Ads.

Landing / Лендінг is a separate page workspace documented in
[`landing-studio.md`](landing-studio.md). Its explicit publication checkpoint
provides the canonical website URL used by Ads. Private draft routes remain protected.

## Brief-to-creative workflow

Brief approval requires a template choice. The server transactionally records
approval and reserves ordinal 1 for that Brief, returning HTTP 202. The browser
opens the creative progress view while composition advances through queued,
composing, optional iPhone-image generation, and editable draft.

The Studio composer receives only:

- the approved Brief;
- the selected live template catalog and defaults;
- the canonical composer skill;
- the latest digest-verified accepted global skill snapshot;
- the latest digest-verified Project skill snapshot.

Its strict JSON may populate only fields already supported by the selected
template. Invalid fields, values, counts, or schemas fail the run and leave a
retryable creative. The common catalog is always authoritative over skills.

A corrected/replacement Brief receives a new creative. Creating another
AI-composed creative from the same Brief is allowed only after the latest sibling
has an immutable approved version. The owner can also clone a selected approved
Post into a new same-template draft without AI; configuration, content, and the
approved raw-asset snapshot are inherited, while identity and approval history
start fresh.

## Common bounded templates

`universal_ad` v13 is a 1080×1080 composition where only the background is
required. Hero title, supporting text, offer, CTA, screened photographic sticker,
Natal identity, and the benefits group are optional; each of the three benefits
is optional independently. Hidden values remain editable state, disappear from
semantic/render output, and the remaining blocks reflow deterministically.

Both templates expose a separate bounded font family and size for every
editable text role. The common ten-family catalog includes neutral, condensed,
geometric, display, serif, and true editorial-italic choices; all font files
and their OFL licenses are checked in so host and container renders use the
same pixels. Repeated phone metrics and app actions share role-level typography,
while their copy and visual surfaces remain independently editable. Natal
identity keeps fixed renderer-owned geometry and typography; only its bounded
symbol and name colors are owner-editable. iPhone system chrome stays fixed.

`phone_metrics` v27 is a 1080×1350 composition with an off-white material
background and optional Natal lock-up, eyebrow, hero, supporting copy,
front-facing black iPhone, in-phone title, full-width CTA band, and three metric
controls. Each metric and each of the three in-phone actions is independently
optional. Remaining metrics/buttons redistribute across their bounded row. The CTA retains
its saved label and typography while hidden and exposes bounded background and text colors.
Empty CTA copy also removes the entire band. Save and Approve accept empty copy;
nonempty CTA copy remains bounded to 60 characters.
Every metric exposes
bounded value/label, Filled or Outlined style, text and surface colours, and
Square, Rounded, or Pill shape.

The post hero title and supporting text each accept the same bounded inline
markup: selected words can be made bold or assigned that role's independent
word colour. Markup delimiters are editor syntax only and never appear in the
authoritative PNG.

The phone app screen has a fixed status bar, complete cellular and Wi-Fi
signals, battery, an independently optional canonical Natal lock-up, optional eyebrow/title, generated hero,
supporting copy, three owner-tunable app actions, and home indicator. The three
actions expose bounded text, Filled/Elevated/Outlined/Text-only style, text and
surface colours, and Square/Rounded/Pill shape. Their defaults match the
approved screenshot: cobalt primary, elevated white secondary, and blue
text-only tertiary.

The post-level and in-phone Natal lock-ups each have an independent visibility
toggle. Both remain visible by default, use only the canonical renderer-owned
asset, and cannot be uploaded or replaced. One shared pair of bounded colors
applies to every visible lock-up in a creative: `logo.symbol_color` recolors the
whole symbol, including its former dark inner stroke, while `logo.name_color`
recolors only the `NATAL` word. Alpha, dimensions, typography, spacing, and
geometry remain byte-derived from the verified canonical PNG. Canonical colors
return the original PNG bytes unchanged.

Save or Approve stores a changed color pair as an append-only Project default
linked to that edit checkpoint. Preview and intermediate configuration requests
never update the default. New AI-created Posts and explicit template replacements
inherit it, and the composer schema locks both values so Brief or Creative Skill
learning cannot override them. Existing drafts stay unchanged; an approved clone
retains its selected immutable version's colors even when the current Project
default is newer. Landing continues to use its separate unchanged canonical logo.

Local template v24 adds **Visual mode: Phone frame & buttons / Image only**.
The optional `configuration.visual_mode` accepts `phone` or `image`; omitted
values retain the phone view without rewriting stored configuration. Image mode
contains the selected raw artwork in the existing device area, preserving its
aspect ratio and transparency with no hardware, app UI, fade, or screen texture.
Surrounding Post copy, metrics, and CTA remain. Switching back restores the saved
phone settings; image generation/history and immutable Save/Approve paths remain
shared. This change is local only.

The phone frame is a checked-in, SHA-256-verified WithFrame asset and is never
fetched at runtime. The screen, UI, and frame are composited as one deterministic
layer. Full-bleed hero art reaches the top underneath renderer-owned chrome,
keeps its subject lower, spans the full screen width, and uses an eased
image-derived fade into the lower background. Alpha cutouts keep their
transparent screen surface and never stretch subject pixels upward into the
fixed header.

Current drafts use Universal config v8 and Phone Metrics config v13. Earlier
mutable supported drafts receive a one-save uplift with previously implicit
elements and canonical logo colors retained. Uplift-only schema/renderer changes
do not manufacture an owner edit checkpoint; immutable approved versions are
never rewritten.

Template application replaces the current mutable configuration/content/assets
inside that creative and inherits the current Project logo colors. It never
rewrites an immutable approved version. Payloads must use the current exact
schema after that bounded uplift.

## Phone hero generation

After `phone_metrics` composition, Studio automatically starts one fresh hero
generation. Before the creative starts, its owner selects one saved Phone-Hero
style and either a contextual scene or an isolated key element on a
clean tonal field. The canonical phone-hero skill, selected creative direction,
Brief-derived subject description, and accepted global/Project visual lessons
are included in both local Codex and production bridge prompts. The saved
direction is reusable provenance for a future caption/legend generator; Studio
does not implement that generator today. Their complete assembled prompt is
bounded at 9,000 characters so every individually valid input combination also
fits the provider boundary.

Generated pixels must contain no phone, readable text, numbers, logo, UI,
buttons, metrics, charts, or unsupported claim. Renderer-owned UI is added
afterward. Provider credentials and temporary paths never reach the browser.

Manual generation supports:

- fresh generation with no reference;
- generation from one optional uploaded Image Reference plus the owner direction;
- enhancement using exactly the selected raw hero PNG and its digest;
- selection among the newest three distinct digest-checked raw heroes;
- separate retry after automatic image failure.

The style/background choice is saved on the creative and governs every later
generation until replaced. Its edit icon resets the picker so the owner can
save a replacement; existing images and history remain untouched until the
owner explicitly generates again. Existing Phone Metrics drafts created before
this capability retain their current image, but must save one direction before
a further generation, enhancement, or image retry.

A failed image request preserves the composed draft and deterministic fallback.
The selected raw hero is the input to the next enhancement. A fourth successful
generation evicts only the oldest raw hero file.

## Save, approve, and performance learning

**Update preview** explicitly renders pending edits in either Post template.
Typing and control changes send no render requests or validation errors. The
last successful image remains visible with a pending-changes notice until the
owner requests an update. A failed render retains that image and can be retried;
edits made during a render remain marked as not previewed. Opening a creative
and completing a saved-state or asset operation still refresh the saved preview.
Preview never saves, approves, or starts performance learning.

Live edits never teach the agent. The initial AI composition is provenance, not
an owner lesson. A changed **Save creative** or **Approve creative** stores the
lightweight immutable before/after checkpoint and changed paths; approval also
writes the immutable creative version. Neither action invokes a learner, opens a
learning dialog, queues a retry, or creates a Project/global rule. A no-change
checkpoint creates no event.

Performance learning is an explicit action in Analytics. It compares eligible
complete approved creatives, freezes its dataset, and produces inactive typed
candidates for owner review. Active Project and global Creative Skill snapshots
are read at generation time and their exact IDs/digests are recorded in
generation provenance. See
[Analytics and reviewed Creative Skills](analytics-and-creative-learning.md).

## Persistence and APIs

PostgreSQL stores one row per creative plus its renderer snapshot/files, assets,
immutable versions, generation runs, and edit checkpoints. Historical
Save/Approve learning rows remain preserved but inactive. Performance runs,
decisions, and typed Creative Skill snapshots use the shared Analytics authority.
Explicit graph edges retain Project and Brief lineage. Renderer files in
production are disposable cache rehydrated from PostgreSQL.

Public routes are:

- `GET /api/v1/studio/templates`;
- project creative list/create;
- creative-scoped detail, retry, creative-direction replacement, configuration,
  Save, template apply, assets, Pexels, preview, component metadata, phone
  generation/select/history/retry, approval, and versions.

Bare Studio detail/mutation routes and `/api/v1/posts` do not exist. Local
loopback exposes the same creative-scoped contracts. Restart recovery resumes
queued/interrupted composition and image work without duplicating creatives,
assets, or completed checkpoints. Save-era learning recovery is retired.

## Visual and Tune gates

`skills/studio-ui-visual-audit/scripts/audit_universal_studio.py` verifies both
templates at authoritative resolution, including copy bounds, device alignment,
network glyphs, button variants, textures, hero top coverage/fade, and
text-free artwork. The browser/UI E2E suite checks desktop, 360px, and iPhone
WebKit flows, creative progress, direction replacement, fresh generation,
enhancement/history selection, Save/Approve checkpoint behavior, and no horizontal
overflow. It is paired with real HTTP/domain-service tests, exact
Gateway-to-Validation route parity, authenticated forwarding assertions, and a
live route-registration probe; mocked browser traffic alone is not accepted as
complete system E2E evidence.

`STUDIO_TUNE_MODE=1` remains loopback-only. It may modify Studio implementation
files through its guarded worktree and requires explicit owner approval before
copy-back. Runtime performance learning writes immutable database/local skill
snapshots; it never rewrites Git skills or mounted read-only skill directories.

## Shared Image Reference input

Every manual image-generation prompt uses the shared `ImageReferenceInput` control
and `validation_pipeline.image_reference` request/pipeline contract. This covers
Post Phone Metrics and both Landing visual slots. Future generation surfaces must
reuse these boundaries. An optional `reference_image` object contains only
`mime_type` and `bytes_base64`; it is mutually exclusive with `enhance_current`.
Without it, automatic and manual generation keep their existing behavior.

PNG, JPEG, and WebP uploads are bounded to 8 MiB, one frame, 64–8192 input pixels,
and 16 megapixels. The server applies EXIF orientation, preserves aspect ratio,
fits within 2048 pixels, strips metadata, and supplies a PNG to the provider.
The prompt tells the agent to interpret the image together with the owner's
instruction; it adds no style/composition/object reference modes. Existing
text-free destination constraints remain in force.

The file is operation input, never an asset, configuration field, checkpoint,
version, or learning attachment. Browser selection creates a local object URL
only; the request includes pixels only on Generate. Completion or failure,
page/creative navigation, removal, and unmount clear the reference/preview.
Failures preserve the current generated image and require re-upload for a
reference retry. Generated results use ordinary asset/history/version behavior.
Only a reference SHA-256 is retained as generation provenance.

## Instagram validation handoff

Every approved Post version can be cloned without AI, exported through the
Instagram-only Post surface, or selected as one of 2–6 immutable paid-test arms.
Manual packages and paid arms bind the exact approved PNG/version digest to one
unique tracked Landing URL. TikTok and automated Meta Ads surfaces are inactive;
see [`instagram-manual-validation.md`](instagram-manual-validation.md).

The companion platform bridge must advertise
`image_reference_retention: ephemeral` before PTW sends reference bytes. It
replaces uploaded bytes with a server-owned handle and digest/dimension metadata
before inserting a job. Its bounded memory pool holds at most two references
for up to ten minutes; an authenticated worker consumes each once into its
existing temporary directory (tmpfs in production). Completion, failure, client
cleanup, expiry, or restart remove the input. A lost input fails explicitly
instead of generating without it. This requires deploying the companion bridge
and worker together with Validation; older bridges reject reference operations
at the capability preflight without receiving the image.
