---
name: landing-page-composer
description: Populate one selected bounded private PTW Landing template from an approved Product Brief and immutable approved Post version. Use only bounded Landing fields and never fabricate social proof or contacts.
---

# Landing page composer

- The Brief owns claims, positioning and V3 brand_identity. For Identity-led,
  continue the Post's self-image promise in a 3–5-word Hero. Explain the
  recognizable product action and practical proof below it. Features, FAQs and
  enabled comparison address the grounded convention, teach competence_cue and
  tie emotional reward to proof_anchor.
  Keep the product identifiable. Use belief/voice for copy and visual_world for
  images. Plain precise language is valid. Apply: catalog, brand and Brief;
  owner direction; Project rules; global spirit; defaults.
  Ignore inactive/tombstoned rules. Use only supplied catalog settings.
- The approved Post is frozen provenance. Preserve its copy direction and mapped
  design; never claim synchronization.
- Return only the exact `content` shape in the supplied JSON schema. Layout,
  theme, presentation, components, image styles and phone layout are server-owned.
  Do not add configuration, sections, code, controls, testimonials, metrics,
  prices, guarantees, urgency or lead forms.
- Populate one concise Hero, three honest feature pairs and three Brief-grounded
  FAQs. Match CTA to the Brief offer; use a 2–5-word action label. Put established
  duration, price and offer details in support. Keep features scannable.
- Use the Brief's Ukrainian or English language, independently of Console
  language. The server owns CTA routing; never invent its endpoint.
- Natal is the fixed identity. Use its renderer-owned logo/name; never derive
  branding from product copy, artwork or page themes.
- Every offering, including physical services, is experienced through a Natal
  app. For `project_landing`, `app_feature` describes one Brief-grounded task,
  such as solar consumption, safari booking or medicine inventory. Supply a
  screen title, description, action label and three row labels; optional details
  describe inputs/categories. Leave unestablished values empty. Never
  invent availability, readings, results, prices or capabilities.
- Editable UI uses Post Studio's canonical phone frame. Hero art follows the
  current mode; outer hardware and controls remain renderer-owned.
- Preserve supplied theme, palette, typography, components, image styles and
  mockup layout. Subject directions describe subject, action and setting. They
  are suggestions; direct owner image requests override presets. Match Hero
  colors/lighting to the supplied gradient without changing owner-selected colors.
- Social proof requires verified owner evidence for this exact product/domain.
  Reference/template testimonials never become Project copy. Return a heading
  and empty `items`; the server preserves verified proof. Invent no customers,
  ratings, logos, results, credentials or measurements.
- Contacts are owner evidence. Return heading/supporting copy and empty email,
  phone, Telegram bot-link (`url`) and, when present, Instagram fields. Never
  invent profiles, copy reference contacts or use Commander's emergency bot.
- Supply distinct 8–600-character Hero and visual-break subject directions.
  Keep Hero subjects safe in square/4:3 crops
  and visual-break subjects in the central band of a shallow landscape crop.
  Show purposeful action and 1–2 occasion cues; avoid flattery or invented luxury.
- Save/Approve establishes provenance, not performance. Only reviewed Analytics
  or owner Skill revision activates a snapshot. Post `metric_provenance` may hold
  unvalidated numeric hypotheses; never turn them into Landing facts or proof.

## App Showcase

For `app_showcase`, the exact schema replaces `app_feature` with three
`app_screens`, each with a short title, caption and 8–600-character direction.
When Hero has `eyebrow` and `bullets`, write a line above the title, three
distinct Brief-grounded benefits, and text for the text/bullets switch. Avoid
unverified outcomes, numbers and proof.
Describe related Brief-grounded tasks with consistent palette and language.
These are static screen interiors. Use realistic lists and compact controls
with consistent typography, spacing and navigation. Keep labels short. The
server supplies `screen_design` and portrait geometry; leave the camera-safe
top clear. No hardware, status bars, camera or new logo: the renderer supplies
the frame and Natal identity. Screen values are illustrative inputs, never
fabricated results. `visual_break` holds the supporting photo; Hero has no
generated backdrop. Retain the features/FAQs and proof/contact boundaries.

## Optional marketing sections

If `content.marketing` exists, populate introduction, comparison heading and six
rows, four walkthrough steps, photo/benefit copy, four service values and CTA copy
in the Brief's language. Reuse supported benefits. Never invent prices, legal
protection, response times or availability. Unsupported items remain empty with
`enabled: true`; Studio supplies completion hints and hide controls. Preserve
item counts. Store/legal URLs remain empty for owner destinations. Reference
feedback stays visible as labelled illustrative expectations from this product's
benefits when proof is absent. Preserve that section when adapting domain copy;
never invent customers, ratings or past experience. Supplied `feedback_examples`
may contain hypothetical wants; use only supplied schema fields.

`walkthrough_visual_direction` describes one cohesive 4:3 composition of three
or four complete, staggered, front-facing phones with coherent readable UI.
Keep hardware inside safe margins, devices large and margins modest. Match the
language, palette and supplied `screen_design`. Avoid distortion, repeated frames,
cards or checkerboards. Outer space/gaps are transparent; white screens stay opaque.
This slot includes hardware; `app_screen_1/2/3` contain only screen interiors.
Exclude store badges, external captions, Natal logos and evidence from this image.
Generate/Enhance uses existing slot history and references.

The service injects owner-authorized Natal contact defaults after validation.
Generated endpoints stay empty. Empty store targets and early-stage social icons
use the renderer's shared early-access form; the model does not author that form.

## Visual and runtime boundaries

Fit proportionally: never stretch screens, clip phone hardware, or crop faces,
hands or the task from photos. Keep legacy squares visible and portrait screens
filled. Preview/public rendering share these rules. They are engineering
constraints, not performance learning: never score images or add semantic retries.
Failed/stale image work retains selected artwork; approved versions are immutable.

Stay below 7 KiB, reserving correction room in the 8 KiB prompt budget. Run the skill verifier and a real
canonical-prompt invalid-first/valid-second bridge regression after edits; never
raise budgets or weaken validators to accommodate prose.
