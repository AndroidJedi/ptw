# Project-scoped Post Studio

The owner sees Studio as **Post / Допис**. Every creative belongs to one Project
and derives from one approved Product Brief. Studio has no owner-wide singleton,
separate Studio page, Social Post workflow, publishing, campaign, traffic,
analytics, or optimization surface.

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
creative from the same Brief is allowed only after the latest sibling has at
least one immutable approved version.

## Common bounded templates

`universal_ad` is a 1080×1080 composition with background, optional screened
photographic sticker, hero title, supporting text, benefits, CTA, and fixed
Natal identity.

Both templates expose a separate bounded font family and size for every
editable text role. The common ten-family catalog includes neutral, condensed,
geometric, display, serif, and true editorial-italic choices; all font files
and their OFL licenses are checked in so host and container renders use the
same pixels. Repeated phone metrics and app actions share role-level typography,
while their copy and visual surfaces remain independently editable. Natal
identity and iPhone system chrome keep their fixed renderer-owned typography.

`phone_metrics` is a 1080×1350 composition with an off-white material
background, fixed Natal lock-up, left-safe copy, a front-facing black iPhone,
three equal metric controls, and a full-width CTA band. Every metric exposes
bounded value/label, Filled or Outlined style, text and surface colours, and
Square, Rounded, or Pill shape.

The phone app screen has a fixed status bar, complete cellular and Wi-Fi
signals, battery, Natal lock-up, optional eyebrow/title, generated hero,
supporting copy, three owner-tunable app actions, and home indicator. The three
actions expose bounded text, Filled/Elevated/Outlined/Text-only style, text and
surface colours, and Square/Rounded/Pill shape. Their defaults match the
approved screenshot: cobalt primary, elevated white secondary, and blue
text-only tertiary.

The phone frame is a checked-in, SHA-256-verified WithFrame asset and is never
fetched at runtime. The screen, UI, and frame are composited as one deterministic
layer. Full-bleed hero art reaches the top underneath renderer-owned chrome,
keeps its subject lower, spans the full screen width, and uses an eased
image-derived fade into the lower background. Alpha cutouts keep their
transparent screen surface and never stretch subject pixels upward into the
fixed header.

Template application replaces the current mutable configuration/content/assets
inside that creative. It never rewrites an immutable approved version. Payloads
must use current exact schemas; no historical schema upgrader or alternate
version format exists.

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

## Save, approve, and learning

Live edits never teach the agent. The initial AI composition is provenance, not
an owner lesson. All subsequent configuration, content, template, import,
asset, image-generation, enhancement, and image-selection changes accumulate
until **Save creative** or **Approve creative**.

A changed checkpoint stores immutable before/after snapshots and changed paths,
then starts one append-only learning attempt. Success appends a Project skill
snapshot and a privacy-filtered global proposal. The checkpoint dialog shows
the edit summary, saved Project lesson, and proposed global rule, with
**Apply globally** and **Keep project-only** decisions. Applying globally
appends a global skill snapshot; keeping it Project-only records the decision
without changing the global skill.

A no-change checkpoint creates no event and no dialog. Approval saves pending
changes atomically before writing the immutable creative version. Learning
failure cannot roll back saved state or an approved version and is queued for
retry. Project lessons may retain Project preferences; global rules reject
Project IDs/names, exact campaign copy, asset digests, and unsupported claims.

## Persistence and APIs

PostgreSQL stores one row per creative plus its renderer snapshot/files, assets,
immutable versions, generation runs, edit checkpoints, learning runs,
proposals/decisions, and immutable skill snapshots. Explicit graph edges retain
Project and Brief lineage. Renderer files in production are disposable cache
rehydrated from PostgreSQL.

Public routes are:

- `GET /api/v1/studio/templates`;
- project creative list/create;
- creative-scoped detail, retry, configuration, Save, template apply, assets,
  Pexels, preview, component metadata, phone generation/select/history/retry,
  approval, versions, learning decision, and learning retry.

Bare Studio detail/mutation routes and `/api/v1/posts` do not exist. Local
loopback exposes the same creative-scoped contracts. Restart recovery resumes
queued/interrupted composition, image, and learning work without duplicating
creatives, assets, skill snapshots, or completed checkpoints.

## Visual and Tune gates

`skills/studio-ui-visual-audit/scripts/audit_universal_studio.py` verifies both
templates at authoritative resolution, including copy bounds, device alignment,
network glyphs, button variants, textures, hero top coverage/fade, and
text-free artwork. The browser suite checks desktop, 360px, and iPhone WebKit
flows, creative progress, enhancement/history selection, Save/Approve learning
dialogs, and no horizontal overflow.

`STUDIO_TUNE_MODE=1` remains loopback-only. It may modify Studio implementation
files through its guarded worktree and requires explicit owner approval before
copy-back. Runtime learning writes immutable database/local skill snapshots; it
never rewrites Git skills or mounted read-only skill directories.
