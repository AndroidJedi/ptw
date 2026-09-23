---
name: landing-page-composer
description: Populate one fixed private PTW Landing page from an approved Product Brief and immutable approved Post version. Use only bounded Landing fields and never fabricate social proof or contacts.
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
  Populate `app_feature` with one Brief-grounded task: a consumption interface for
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
