# PTW owner-console rules

Status: canonical
Updated: 2026-09-03

## Navigation and trust

- Production navigation contains Product Briefs and owner-only Universal
  Studio. The local app also contains the bounded Post milestone.
- Old page locations and retired domain APIs do not exist.
- Design first for 360 px and one-hand use with 44×44 CSS-pixel targets, no
  horizontal overflow, keyboard access, and reduced-motion support.
- Empty production state is valid. Never seed fake Briefs, metrics, proof,
  testimonials, urgency, scarcity, or assets.

## Product Brief

- One raw idea creates one Project, permanent Source, and complete immutable Brief.
- A correction creates a new UUID and complete replacement with feedback and
  weight lineage. Approval confirms that the promise and offer can be honored.
- Approval does not automatically create another artifact or navigate. In the
  local app, the owner may explicitly open Post after approval.

## Simple local post

- One approved Product Brief creates at most one mutable post draft. Before it
  starts, select `universal_ad` or `phone_metrics`; the selected template is
  then locked on that draft.
- `universal_ad` renders through strict Universal Studio configuration,
  semantic content, component IDs, Pexels provenance, and an 1080×1080
  renderer. `phone_metrics` is a fixed 1080×1350 Natal creative with three
  owner-entered statistics, one local static perspective-phone asset, and
  server-generated text-free screen art.
- Put one owner comment field directly below the preview. Translate it into
  exact bounded Studio setting/content commands and, when requested, one
  semantic Pexels background query. Keep the applied commands ID-explicit.
- A draft is not an asset. Only explicit approval creates one immutable PNG
  asset with its Brief, Project, state, template, configuration, content, and
  source provenance.
- This milestone remains local-only. It has no production route, PostgreSQL
  schema, publishing, export, campaign, traffic, analytics, or optimization.

## Universal Studio

- Studio is a separate two-template workspace: editable square `universal_ad`
  and fixed-composition 4:5 `phone_metrics`. Selecting one replaces mutable
  configuration/content/assets but never rewrites an immutable version.
- Natal is the sole identity in new Studio/Post drafts. Its canonical lock-up
  is always enabled; owner logo upload/toggle/brand substitution are not
  controls. Historical immutable versions remain readable.
- Expose only meaningful bounded controls and fixed asset slots. Primitive
  trees, arbitrary properties, raw template imports, and calibration remain
  internal. The phone frame is a local SHA-256-checked file and never fetched
  at runtime; frame and screen share one composite layer.
- The Studio visual audit renders the phone template at full 1080×1350 and
  fails on texture, Natal placement, left-safe copy, phone/card/CTA drift,
  clipping, overlap, unsafe bounds, or generated screen text.
- Preview and immutable-version renders are authenticated, digest-checked, and
  no-store. Approval stores the exact PNG, configuration, semantic content,
  asset provenance/digests, and internal template digest.
- Loopback Tune mode may modify only Studio code through its guarded local
  workflow. It remains absent from production routes.
- Studio itself does not generate posts. It has no review grid, export,
  notification, publishing, campaign, traffic, UTM, analytics, or optimization
  action.

## Caching and reset

- Cache only public shell resources. Never cache API or authenticated renders.
- Production reset names only `ptw_commander.public`, preserves the independent
  platform database, and requires `RESET PTW PRODUCTION`.
