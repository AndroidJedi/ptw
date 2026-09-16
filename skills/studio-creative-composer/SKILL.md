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
- Write concise, renderable copy. Do not fabricate metrics, proof,
  testimonials, urgency, scarcity, prices, or guarantees.
- For `phone_metrics`, use three honest benefit-oriented labels when the Brief
  contains no measured metrics. Leave actual numeric proof out rather than
  manufacturing it, and supply one text-free subject description for the phone
  hero worker. When INPUT_JSON contains `creative_direction`, it is selected by
  the owner and controls the visual style/background treatment; never replace,
  omit, or contradict it in the subject description.
- The generated baseline and later Save/Approve checkpoints are provenance, not
  performance evidence. Only a reviewed Analytics learning run or a direct owner
  Skill revision may create a new active snapshot.
