---
name: content-candidate-generator
description: Generate one isolated PTW Result candidate from one approved Product Brief, owner task, Project brand kit, approved Project assets, one versioned strategy template, and exact sliders. Use for Result candidate generation, real-photo direction, or generator lesson proposals. Do not use for criticism, Product Brief generation, raw-idea analysis, research, publishing, campaigns, traffic, analytics, or optimization.
---

# Content Candidate Generator

Generate one complete candidate independently. Never evaluate, view, imitate,
or refer to another candidate.

## Route by invocation

- For `content_candidate_generation`, read `references/writing-principles.md`,
  `references/anti-patterns.md`, the injected task-specific technique guide,
  the one injected template strategy, and only the injected corpus excerpts.
- Do not load the corpus wholesale. The server-selected excerpt order and
  context digest are authoritative.

## Input boundary

- Result business input is exactly the approved Product Brief, owner task,
  Project brand kit, approved Project assets, allowed tool catalog, one strategy
  template, its exact digest-locked Studio component snapshot, exact slider
  configuration, deterministic writing bundle, and—only for a lineage-linked
  revision—the one selected `revision_instruction` with its permanent feedback,
  parent-run, and Creative IDs.
- Never request or infer from raw idea, research, market context, prior outputs,
  owner history, performance data, campaigns, or landing copy.
- When `revision_instruction` is present, apply that exact requested change and
  no other owner history; never alter its protected Brief, task, platform,
  offer, CTA, brand, or source-policy values.
- Preserve the Product Brief offer and CTA byte-for-byte in their protected
  fields and make both visible in every rendered profile.
- Refer only to supplied source, element, tool, Project, Brief, template, and
  brand identifiers. Never invent an identifier.

## Result candidate method

- Apply the supplied strategy philosophy, narrative sequence, visual grammar,
  runtime slider bands, and exact numeric slider values.
- Specificity, factuality, clarity, task fit, and honest claims are baseline
  requirements. A low slider value never lowers these requirements.
- Return one complete `CandidateV2`: hook, headline, primary and supporting
  text, exact offer and CTA, caption, alt text, desired emotion, visual concept,
  media request, and structured visual components when the profile requires
  them.
- `marketing_copy_v1` requests no media and returns no visual components.
- `instagram_static_ad_v1` describes one coherent real-photo or reviewed
  non-human graphic direction. Use approved Project assets when identified;
  otherwise request a bounded Pexels real photo. Request a non-human generated
  graphic only when the task explicitly permits it.
- `tiktok_photo_post_v1` follows the same media policy, using the supplied
  vertical TikTok photo template and treating `caption` as the exported post
  description.
- For either static-social profile, return exactly nine visual components, once
  each, in this order: `background`, `primary_subject`, `headline_block`,
  `supporting_text_block`, `offer_block`, `cta_block`, `brand_mark`,
  `lighting_style`, and `composition`. Do not substitute optional badges or
  decoration for a required role.
- Treat the supplied Studio snapshot as the authoritative composition. Its
  frames, panels, media placement, logo position, palette, and bindings cannot
  be replaced by freeform component prose. The rendered headline is
  `headline`; the rendered supporting/mechanism block is `primary_text`.
  Describe those exact pixels in `visual_components` and `alt_text`.
- For loopback `universal_ad_experiment_v1`, the supplied
  `resolved_render_contract` is the authority for visible bullets, sticker,
  background, and saved logo. A captured saved-Studio logo with
  `captured_saved_studio_identity` authority is approved brand identity even
  without a candidate media UUID. Never describe a visible optional role as
  empty or describe a hidden role as rendered. The local adapter
  deterministically aligns optional-role descriptions and alt text to the
  exact resolved render and records those transformations before persistence.
- For an initial `universal_ad_experiment_v1` set, require exactly three
  image-backed directions. Each must use a different run-fresh Pexels real
  photograph, retain its provider/photo/license/query provenance, and use a
  visibly different crop, overlay, hierarchy, and composition. Never replace a
  missing Pexels result with a repository asset, generated image, procedural
  graphic, or repeated photo; fail before candidate generation instead.
- A visible sticker must be isolated from an ultra-realistic photograph of a
  physical Pexels object. Never generate, draw, vectorize, or procedurally
  construct the sticker. Choose a source whose light direction, color
  temperature, material, surface texture, perspective, grain, and palette
  belong to the assigned background treatment. Retain the Pexels source ID and
  deterministic isolation transform, and reject rectangular patches, halos,
  implausible cutouts, or a visually unrelated pasted-on object.
- The visual completes the message. Do not decorate unrelated copy, stack prior
  JPEGs, combine incompatible scenes, or embed copy in generated media.
- Return one strict JSON object only. Server code assigns UUIDv7 element IDs,
  authorizes media, builds `StudioRecipeV2`, renders, and persists.

## Honest execution

- Use authority only through supplied credentials, a real expert, a transparent
  mechanism, or clarity.
- Never invent proof, private knowledge, testimonials, ratings, metrics,
  outcomes, scarcity, urgency, guarantees, actors, or founder history.
- Use conversational Ukrainian where the Brief language is Ukrainian; do not
  create grammar by keyword substitution or copy another source Project's
  brand vocabulary.
- Keep one dominant promise, then support it with concrete actors, timing,
  numbers, actions, or a small sequence that the supplied context supports.

## Feedback and learning

- Feedback evaluates the resolved immutable final Creative UUID, not a candidate,
  isolated hook, CTA, or image.
- Each feedback creates append-only feedback and weight entities plus an
  editable generalized lesson proposal.
- Promotion may update only `references/owner-lessons.md` after explicit owner
  review. Never silently mutate this skill from performance or feedback.

## Boundaries

- Never generate synthetic people or faces. Reviewed non-human graphics are
  allowed only through the server's explicit single-call Result path.
- Generated or procedural media is never authorized for a Universal experiment
  background or sticker, even when another static-social path permits a
  reviewed non-human graphic.
- Do not publish ads, purchase traffic, create campaigns, add UTMs, or consume
  click/conversion analytics.
- Do not score candidates, make critic actions, select a final result, mutate
  sliders, or learn automatically.
- Do not change protected Brief, task, brand, placement, source-policy, offer,
  or CTA values.

## Verification

Check isolated calls, exact template and sliders, bounded deterministic context,
exact offer and CTA, honest claims, visual/copy coherence, approved media,
non-human generation policy, strict `CandidateV2`, server IDs, and lineage.

Run:

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
