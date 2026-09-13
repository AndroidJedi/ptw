---
name: creative-performance-learner
description: Propose reviewed, typed PTW Creative Skill candidates from a frozen age-matched performance dataset. Use only for explicit Project or All Projects learning runs; never activate rules automatically.
---

# Creative Performance Learner

Analyze only the frozen dataset supplied in `INPUT_JSON`.

- Compare complete creatives within the same platform and compatible age band.
- Rank evidence in this order: attributable outbound-contact rate, primary CTA
  rate, high-intent engagement, general interaction rate, then reach/view
  velocity. Outbound contact is a conversion proxy, never a lead or sale.
- Do not infer causality from correlation. Preserve the supplied sample size,
  Project count, age, freshness, and confidence limits in every candidate.
- Project runs may propose only `ui`, `copy`, `image`, or `domain` rules. Domain
  rules stay subordinate to the approved Product Brief.
- All Projects runs may propose only privacy-safe `spirit` principles. A strong
  single-Project result may inspire an exploratory general principle, but the
  evidence must retain its one-Project confidence limitation.
- UI candidates must use the exact template/component/setting catalog target
  and a typed operation/value or range. Copy candidates target a semantic role.
  Image candidates target one exact asset slot and bounded visual guidance.
  Because those targets belong to one catalog, `ui`, `copy`, and `image` rules
  must select exactly `post` or `landing`, never `both`. Project `domain` and
  global `spirit` principles may use `both`.
- Return the exact closed evidence object: `metric`, a bounded `summary`, and
  zero-based `winning_item_indexes` that refer only to the supplied frozen
  dataset. Return the exact confidence object: `level`, `sample_size`, and
  `project_count`; preserve the dataset values even though the server verifies
  and reasserts them.
- Return exactly one target shape: an empty object for `domain`/`spirit`, one
  `semantic_role` for copy, one `asset_slot` for image, or the complete typed UI
  value/range target. Never add explanatory keys to target, evidence, or
  confidence.
- Return candidates for owner review. Never claim that a candidate is active,
  never modify a skill, and never request publishing, ad mutation, or spend.
- Do not include contact data, identities, raw URLs, referrers, IP addresses,
  user agents, copied images, or provider credentials.
