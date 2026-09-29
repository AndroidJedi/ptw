---
name: landing-page-composer
description: Populate one selected bounded private PTW Landing template from an approved Product Brief and immutable approved Post version. Use only bounded Landing fields and never fabricate social proof or contacts.
---

# Landing page composer

- The approved Product Brief is the marketing-claim authority. Apply supplied
  typed snapshots in this order: fixed catalog, brand and Brief constraints;
  explicit owner direction; active Project rules; active global spirit; defaults.
  Ignore inactive/tombstoned rules. Use only supplied catalog settings.
- The approved Post is frozen provenance. The server preserves mapped design;
  bounded frozen copy provides tone and continuity. Never claim synchronization.
- Return only the exact `content` shape in the supplied JSON schema. Layout,
  theme, presentation, components, image styles and phone layout are server-owned.
  Do not add configuration, sections, HTML, CSS, scripts, controls, testimonials,
  metrics, prices, guarantees, urgency or lead forms.
- Populate one concise Hero, exactly three honest feature title/description
  pairs and three Brief-grounded FAQs. Match the CTA to the Brief offer. Use a
  short action label, usually 2–5 words; put established duration, price and offer
  details in supporting copy. Lead features with benefits and keep copy scannable.
- Use the Brief's Ukrainian or English language, independently of Console
  language. The server owns CTA routing; never invent its endpoint.
- Natal is the fixed umbrella identity for every app. The renderer supplies its
  canonical logo/name. Never derive a brand from product copy or draw branding
  into artwork. Page themes do not replace Natal.
- Every offering, including physical services, is experienced through a Natal
  app. For `project_landing`, `app_feature` describes one Brief-grounded task,
  such as solar consumption, safari booking or medicine inventory. Supply a
  short screen title, description, action label and three UI row labels; optional
  details describe inputs/categories. Leave unestablished values empty. Never
  invent availability, readings, results, prices or capabilities.
- The browser renders editable UI inside Post Studio's canonical phone frame.
  Hero artwork follows the current visual mode. People/devices may be subjects;
  outer phone hardware and controls remain renderer-owned.
- Preserve supplied theme, palette, typography, components, image styles and
  mockup layout. Subject directions describe subject, action and setting. They
  are suggestions; direct owner image requests override presets. Match Hero
  colors/lighting to the supplied gradient without changing owner-selected colors.
- Social proof requires verified owner evidence for this exact product/domain.
  Reference/template testimonials never become Project copy. Return a heading
  and empty `items`; the server preserves verified proof and hides its absence.
  Never rewrite unrelated quotes or invent customers, ratings, logos, results,
  credentials, measurements or placeholder claims.
- Contacts are owner evidence. Return heading/supporting copy and empty email,
  phone, Telegram bot-link (`url`) and, when present, Instagram fields. Never
  invent profiles, copy reference contacts or use Commander's emergency bot.
- Supply distinct 8–600-character Hero and visual-break subject directions.
  Owner requests may change style. Keep Hero subjects safe in square/4:3 crops
  and visual-break subjects in the central band of a shallow landscape crop.
  Avoid repeating a scene.
- Save/Approve checkpoints establish provenance, not performance. Only reviewed
  Analytics learning or an explicit owner Skill revision activates a snapshot.
  Post `metric_provenance` may contain unvalidated numeric hypotheses; never turn
  them into Landing facts, testimonials or proof. Product facts come from the Brief.

## App Showcase

For `app_showcase`, the exact schema replaces `app_feature` with three
`app_screens`, each with a short title, caption and 8–600-character direction.
Describe related Brief-grounded tasks with consistent UI palette and language.
These are static screen interiors, not live functionality. Use realistic lists,
compact controls/forms and consistent typography, spacing and navigation. Keep
labels short. The server supplies `screen_design` and portrait geometry; leave
its camera-safe top clear. No hardware, status bars, camera or new logo: the
renderer supplies the frame and Natal identity. Screen values are illustrative
inputs, never fabricated results/proof. Use `visual_break` for the supporting
photograph. Keep hero.visual_direction as a bounded thematic description; no
Hero backdrop is generated. Retain the three features/FAQs and empty proof/contact
boundaries above.

## Optional marketing sections

If `content.marketing` exists, populate introduction, comparison heading and six
rows, four walkthrough steps, photo/benefit copy, four service values and CTA copy
in the Brief's language. Reuse supported benefits. Never invent prices, legal
protection, response times or availability. Unsupported items remain empty with
`enabled: true`; Studio supplies completion hints and hide controls. Preserve
item counts. Store/legal URLs remain empty for owner destinations. Reference
reviews are a private editor placeholder; never generate/adapt public testimonials.

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

Keep this canonical skill below 7 KiB so the 8 KiB runtime prompt budget retains
room for its bounded validation correction. Run the skill verifier and a real
canonical-prompt invalid-first/valid-second bridge regression after edits; never
raise budgets or weaken validators to accommodate prose.
