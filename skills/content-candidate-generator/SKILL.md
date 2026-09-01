---
name: content-candidate-generator
description: Generate one isolated transient PTW CandidateV2 from one approved Product Brief, owner task, Project brand kit, approved Project assets, one versioned strategy template, exact sliders, and the active owner-learning snapshot. Use for Creative generation or real-photo direction. Do not use for evaluation, Product Brief generation, raw-idea analysis, research, publishing, campaigns, traffic, analytics, or optimization.
---

# Content Candidate Generator

Generate one complete candidate independently. Never evaluate, view, imitate,
or refer to another candidate.

## Route by invocation

- For `content_candidate_generation`, read `references/writing-principles.md`,
  `references/anti-patterns.md`, the injected task-specific technique guide,
  the one injected template strategy, and only the injected corpus excerpts.
- For `instagram_static_ad_v1`, `tiktok_photo_post_v1`, and loopback
  `universal_ad_experiment_v1`, also read the complete injected
  `references/post-copy-style.md`. Apply its direct examples as structural
  style anchors for hook, headline, primary/supporting text, and caption. Keep
  alt text factual and preserve protected offer and CTA byte-for-byte.
- Do not load the corpus wholesale. The server-selected excerpt order and
  context digest are authoritative.

## Input boundary

- Result business input is exactly the approved Product Brief, owner task,
  Project brand kit, approved Project assets, allowed tool catalog, the immutable
  Project-scoped owner-learning snapshot, one strategy
  template, its exact digest-locked Studio component snapshot, exact slider
  configuration, deterministic writing bundle, and—only for a lineage-linked
  revision—the one selected `revision_instruction` with its permanent feedback,
  parent-run, and Creative IDs.
- Never request or infer from raw idea, research, market context, prior outputs,
  unsupplied owner history, performance data, campaigns, or landing copy. Apply
  only the server-supplied active owner rules and immutable run snapshot.
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
- The approved Brief language is authoritative for every user-facing copy
  field. An idea or style anchor in another language never changes the output
  language.
- Keep one dominant promise, then support it with concrete actors, timing,
  numbers, actions, or a small sequence that the supplied context supports.

## Owner feedback and learning

- The provider CandidateV2 is transient. Server code validates and renders it,
  then assigns the immutable Creative UUID used by owner feedback.
- Approve, Regenerate all, and Tune append HumanFeedback, WeightUpdate, Project
  rules, learning snapshots, and graph lineage immediately. Never create lesson
  proposals or mutate this skill from feedback or performance.
- Apply exact strategy-scoped tune instructions, preferred direction/sliders,
  output-profile-scoped layout settings, and exploration exclusions only when
  they are present in the supplied learning snapshot.

## Boundaries

- Never generate synthetic people or faces. Reviewed non-human graphics are
  allowed only through the server's explicit single-call Result path.
- Generated or procedural media is never authorized for a Universal experiment
  background or sticker, even when another static-social path permits a
  reviewed non-human graphic.
- Do not publish ads, purchase traffic, create campaigns, add UTMs, or consume
  click/conversion analytics.
- Do not score, rank, compare, evaluate, or select Creatives. Only the owner can
  Approve, Regenerate all, or Tune through the web review set.
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
