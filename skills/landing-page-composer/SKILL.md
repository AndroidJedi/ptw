---
name: landing-page-composer
description: Populate one selected bounded private PTW Landing template from an approved Product Brief and immutable approved Post version. Use only bounded Landing fields and never fabricate social proof or contacts.
---

# Landing page composer

- Treat the approved Product Brief as the complete marketing-claim authority.
- Apply supplied typed skill snapshots using this precedence: fixed catalog,
  brand, and Brief constraints; explicit owner direction; active Project rules;
  active global spirit; then template defaults. Ignore inactive and tombstoned
  rules, and never invent settings outside the supplied Landing catalog.
- Treat the immutable Post version as frozen provenance. The server preserves its
  mapped design state; the model receives only bounded frozen Post copy for tone and
  continuity. Never claim that the Landing stays synchronized with the Post.
- Return only the exact `content` shape required by the supplied JSON schema.
  Layout, theme, presentation, components, image styles, and phone-mockup configuration
  are server-owned and are not part of the model response. Do not add configuration,
  sections, HTML, CSS, scripts, fields, arbitrary controls, testimonials, metrics,
  prices, guarantees, urgency, or lead forms.
- Populate one concise Hero, exactly three honest feature title/description pairs,
  and exactly three Brief-grounded FAQs. Keep the CTA consistent with the Brief offer.
- Write a short action label (usually 2-5 words); place duration, price, and offer
  details in supporting copy only when the Brief establishes them. Lead each feature
  with its user benefit and keep descriptions scannable.
- Write in the approved Brief's language (Ukrainian or English), independently of
  the Owner Console language. The server owns CTA routing; AI has no authority to
  invent its endpoint.
- Natal is the fixed umbrella identity for every app. The renderer supplies the
  canonical Natal logo/name; never derive a new brand from a Brief product description
  or generate branding into artwork. Page themes do not replace the Natal identity.
- Every offering is experienced through a Natal app, including physical services.
  For `project_landing`, populate `app_feature` with one Brief-grounded task: a consumption interface for
  solar optimization, a booking interface for a safari, or an inventory for medicine.
  Write a concise screen title, description, action label, and three UI row labels;
  optional row details may describe inputs or categories. Do not invent availability,
  readings, results, prices, or capabilities. Leave unestablished values empty.
  The browser renders editable UI inside Post Studio's canonical phone frame. Hero
  artwork follows the current visual mode. People and devices may be scene
  subjects; outer phone hardware and controls remain renderer-owned.
- The server preserves the current catalog theme, palette, typography, components,
  image-style selections, and phone-mockup layout. Subject directions describe only
  the subject, action and setting. They are AI suggestions, not owner commands;
  direct image requests override preset defaults.
- Social proof is owner evidence. Return its heading and an empty `items` array; never
  invent quotes, customers, ratings, logos, results, credentials, or measurements.
- Contacts are owner evidence. Return heading/supporting copy only and empty
  email, phone, and Telegram bot-link (`url`) fields. If the supplied schema
  contains an Instagram profile field, leave it empty too. Never invent a bot
  username or social profile, and never route visitors to Commander's emergency
  Telegram bot.
- Supply distinct 8-600-character subject directions for the hero and visual-break
  artwork. They describe what to show; direct owner requests may also change style. Keep the Hero
  subject safe within a square or 4:3 crop; keep visual-break subjects within the
  central horizontal band for a shallow landscape crop. Avoid repeating the same scene.
- Proof is optional and absent entries are hidden by the renderer. Never replace an
  empty evidence section with placeholder claims or fabricated social proof.
- The initial baseline and later Save/Approve checkpoints are provenance, not
  performance evidence. Only reviewed Analytics learning or a direct owner Skill
  revision may create an active immutable snapshot.

Source Post metric_provenance may describe unvalidated AI numeric hypotheses.
Do not turn these into facts, testimonials or evidence on the Landing. The Brief
remains the source of product facts.

## App Showcase

When the supplied catalog selects `app_showcase`, its exact schema replaces
`app_feature` with three `app_screens` entries. Each has a short title, caption
and 8–600-character visual direction. Describe three related tasks grounded in
the Brief, with a consistent UI palette and language. These are static generated
screen interiors, not live functionality. Describe crisp readable UI, without
phone hardware or a new logo; the renderer supplies the frame and Natal identity.
Screen values are illustrative inputs, never fabricated results or evidence.
The supporting photograph uses `visual_break`; hero.visual_direction is retained
as a bounded thematic description but no hero backdrop is generated. Keep the
three features, three FAQs, empty proof and owner contact boundaries above.

## Optional marketing sections

When the schema includes `content.marketing`, populate its introduction,
comparison heading and six rows, four walkthrough steps, photo/benefit copy,
four service values and CTA copy in the Brief's language. Reuse supported Brief
benefits; never invent prices, legal protection, response times or availability.
Keep unsupported items as empty strings with `enabled: true`: Studio provides
manual-completion hints and individual hide controls. Do not drop items.
Store and legal URL fields stay empty; the owner supplies destinations.
Sample review layouts are fixed, visibly marked demonstration content and never
Natal evidence. Do not generate or adapt testimonials.

`walkthrough_visual_direction` describes one cohesive 4:3 image containing three
or four complete, staggered, front-facing phone mockups with coherent readable
UI for these steps. Keep hardware entirely inside safe margins, UI language and
palette consistent, and avoid perspective distortion or duplicate frames.
This slot includes hardware; `app_screen_1/2/3` still contain only screen interiors.
Do not generate store badges, external captions, Natal logos or evidence inside
this image. Generate/Enhance uses the existing slot history and reference flow.

Owner-authorized Natal contact defaults are injected by the service after response
validation. Keep generated endpoints empty; never copy reference-site contacts.
Social icons without owner profile URLs remain noninteractive, never `#` links.
