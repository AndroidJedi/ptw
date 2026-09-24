---
name: studio-creative-composer
description: Populate one selected PTW Studio template from an approved Product Brief and accepted Studio lessons. Use for project creative composition; do not invent template fields, evidence, or unsupported claims.
---

# Studio Creative Composer

Turn one approved Product Brief into one editable Studio creative using the
selected live template catalog.

- Treat the Product Brief as the complete source of marketing claims. Preserve
  its language, promise, offer, CTA intent, and evidentiary limits.
- Treat the supplied template catalog as the field and value authority. Return
  only the exact configuration and content fields in the output schema; never
  add primitives, asset slots, controls, or arbitrary template properties.
- Preserve the supplied locked Natal symbol/name colors exactly. They are the
  Project brand default, not Brief-derived copy or a Creative Skill preference;
  never infer, revise, or learn them.
- Apply the exact typed skill snapshots supplied in `INPUT_JSON` using this
  precedence: fixed catalog/brand and Brief constraints, explicit owner
  direction, active Project rules, active global spirit, then template defaults.
  Ignore tombstoned or inactive rules; never reinterpret a target outside the
  live catalog.
- Write concise, renderable copy. Do not invent testimonials, evidence, prices,
  guarantees, urgency or scarcity.
- For `phone_metrics`, populate exactly three bottom `stats` cards with prominent
  numeral-bearing values and short domain-specific labels. Prefer quantities
  established in the Brief; otherwise propose plausible, distinct numeric benefit
  hypotheses for later validation. Do not substitute slogans or numbered workflow
  steps. These are unvalidated copy hypotheses, never measured results.
- Return `metric_basis` in card order: `{origin, evidence}` with origin
  `brief_supported` or `ai_hypothesis`. A supported quantity needs an exact Brief
  substring containing the same Arabic numeral(s) used in the card value;
  hypotheses use empty evidence. A spelled-out quantity is not support for a
  digit-form card value. Never claim that generation or plausibility verifies a
  figure.
- Supply a subject/action/setting suggestion for the image worker. Its current
  style/background are defaults; do not bake competing style instructions into
  suggestions. Direct owner image requests override defaults. People, hands,
  devices and complete interactions are legitimate subjects. Text/UI/logo content
  is omitted by default but allowed when explicitly requested within artwork.
- Compose the image direction and available background controls as one palette.
  Match warm/cool lighting and supporting hues; keep text and subject contrast.
  Prefer a Brief-grounded interaction to an unrelated metaphor. For an existing
  hero, match editable background colors to its palette, preserving locked colors.
- The generated baseline and later Save/Approve checkpoints are provenance, not
  performance evidence. Only a reviewed Analytics learning run or a direct owner
  Skill revision may create a new active snapshot.
