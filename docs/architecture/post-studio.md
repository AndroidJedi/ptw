# Project-scoped Post Studio

Status: canonical

Post Studio is the Project-scoped creative editor. Every Post derives from one
approved Product Brief, stores a registered template identity, and can produce
immutable approved versions. Landing Studio is a separate surface and may use
an approved Post version as Project content lineage; template definitions do
not depend on Project data.

## Template boundary

Post and Landing templates use independent immutable registries:

- `validation_pipeline/post_templates.py` owns Post definitions;
- `validation_pipeline/landing_templates.py` owns Landing definitions;
- `validation_pipeline/template_registry.py` provides the small shared identity,
  capability, definition, and lookup contracts;
- renderer/editor implementations stay behind registry keys and bounded
  normalizers.

A template identity is `{surface, template_id, template_version,
template_sha256}`. IDs need only be unique inside their surface. The active Post
registry contains only `phone_metrics`. Unsupported IDs fail at the registry
boundary and retired implementations are not kept as compatibility renderers.

The Landing registry is independent. A future Landing-template creation agent
may receive one versioned Post-template reference
`{template_id, template_version, template_sha256}`. Resolution exposes only the
Post definition's identity, description, canvas, and component roles—never a
Project, Brief, creative, content, asset, or approved Post version. This permits
one coordinated template-design query while preserving separate Post-only and
Landing-only creation paths.

This registry work is preparatory architecture. It does not add the Templates
gallery, template-creation agent, reference-image analysis loop, or runtime
template authoring.

## Brief-to-Post workflow

Brief approval requires a template choice. The server transactionally records
approval and reserves ordinal 1 for that Brief, returning HTTP 202. The browser
opens the creative progress view while composition advances through queued,
composing, optional phone-image generation, and editable draft.

The composer receives only the approved Brief, selected definition defaults, a
generation-specific compact catalog, the canonical composer skill, and a bounded
surface-filtered view of accepted Creative Skills. Template normalizers and the
strict output schema remain the complete mutation authority. Invalid output
leaves an explicit retryable creative.

A replacement Brief receives a new creative. Another composed creative from the
same Brief requires the latest sibling to have an approved version. The owner
may clone an approved version into a new same-template draft without AI;
configuration, content, and exact raw-asset snapshot are inherited while
identity and approval history start fresh.

## Manual Agent performance contract

Agent mode does not transmit the full editor tree or duplicate the live catalog.
One request contains:

- the owner instruction;
- at most four recent messages within a 4 KiB aggregate budget;
- only catalog-backed editable scalar paths and their current values;
- bounded semantic controls and zero to four ephemeral screenshots;
- current image-slot availability and explicit request invariants.

The response contains at most 64 scalar `{path, value}` edits, bounded image
actions, and one short reply. PTW applies edits to a server-owned copy of the
current state, runs the template normalizers and semantic checks, and returns a
complete browser-compatible draft. Unknown, duplicate, immutable, schema, social
proof, or contact paths are rejected. Screenshots are normalized,
metadata-stripped, digest-bound inputs for one turn and are never persisted in
the creative, checkpoint, version, or chat.

Generation skill context retains immutable snapshot IDs and digests, strips
graph/audit fields, and includes only active rules for the requested surface up
to separate Project/global byte budgets. It reports omitted counts explicitly.
Structured provider calls are preflighted with per-mode byte budgets for system
prompt, input payload, output schema, total contract, and response. Invocation
metadata records the measured sizes. The existing one-worker serialization,
420-second server timeout, and single corrective attempt after a completed but
invalid response remain unchanged.

## Phone Metrics

`phone_metrics` v27 is a 1080×1350 Natal composition with an off-white material
background, optional outer identity, eyebrow, headline, supporting copy,
front-facing iPhone or image-only artwork, optional full-width CTA, and three
metric cards.

The only mutable bitmap is text-free hero artwork inside the visual area. Direct
owner upload to `phone_screen` is rejected; fixed Natal identity and the checked-
in, digest-verified phone frame cannot be replaced. Generation keeps three
selectable raw images and may enhance exactly the selected raw image. Reference
screenshots are operation-only inputs.

Every foreground group and repeated metric/action can be hidden within bounded
configuration. Font family and size are independently bounded per text role.
Headline and supporting copy support bounded inline emphasis/color markup whose
delimiters never appear in the rendered PNG. Natal lock-up geometry and type are
renderer-owned; only visibility and bounded symbol/name colors are editable.

Phone and image-only modes share the artwork area. Compound agent requests must
keep requested artwork visible: removing hardware while changing the picture
uses image-only mode with the visual area enabled. The three lower cards keep
value/label semantics; requests for more numbers use numeral-bearing values and
must not fabricate performance claims.

## Save, approval, and lineage

Preview is an unsaved deterministic render. Save creates a checkpoint only when
state changed. Approve atomically saves pending fields and stores the exact state,
component metadata, raw clone assets, and PNG as an immutable version. Responses
are authenticated, digest-checked, and no-store.

Creatives, workspace files, assets, generation runs, checkpoints, approved
versions, Landing sources, publications, and analytics records remain Project-
scoped graph authority. Migration `012_phone_metrics_only.sql` replaces the old
insert constraint with a `NOT VALID` Phone Metrics-only constraint: it rejects
new or updated unsupported workspaces without scanning, deleting, or rewriting
historical rows. Physical storage names remain intact.

## Local Tune and visual audit

Loopback Tune remains local-only, works in a disposable repository snapshot,
copies back only allowlisted Post Studio files, detects concurrent owner changes,
runs focused verification, and renders a 1080×1350 preview. It never deploys or
publishes.

The visual audit renders Phone Metrics variants and checks clipping, overlap,
overflow, typography bounds, responsive editor presentation, and deterministic
PNG output. Canonical command:

```sh
.venv/bin/python skills/studio-ui-visual-audit/scripts/audit_post_studio.py
```
