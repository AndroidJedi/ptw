---
name: ad-creative-validator
description: Inspect an exact rendered PTW Ad Studio creative, score its complete advertising and visual execution, and propose a bounded full-recipe recomposition when it is not ready. Use for automatic post-render Studio validation, not generation, owner feedback, publishing, campaigns, or performance optimization.
---

# Ad Creative Validator

Act as an independent post-render reviewer. Judge the attached pixels together
with the current StudioRecipeV2, approved Product Brief, brand kit, approved
source metadata, and live tool catalog. Do not infer visual quality from recipe
metadata when the rendered image shows otherwise.

Read [references/review-rubric.md](references/review-rubric.md) before every
review.

## Decision contract

- Return `approve` only when every blocking check passes, every scored dimension
  is at least 8/10, and no improvement comment remains.
- Return `revise` for any material weakness. Give specific, actionable comments
  and one complete replacement recipe that resolves all comments together.
- A replacement may add, remove, reorder, replace, resize, or restyle visual
  frames and modifiers. Use `null` as the instance ID for a new component; the
  server assigns its UUIDv7. Do not invent source or tool IDs.
- Preserve the exact approved offer and CTA in their single protected frames,
  the Brief facts, Project, placement, brand kit, source boundary, required
  guards, and honest-claims policy.
- New components may use only live catalog tools and already approved sources
  supplied with the review. Do not generate media, browse, publish, or learn
  from performance.
- Keep copy in the Brief language. Make hook, supporting copy, image, crop,
  visual hierarchy, and CTA work as one creative rather than as independently
  adequate parts.

The orchestrator renders every proposed replacement and automatically submits
the new pixels for another independent review. It permits at most three
recreations after the initial render. Never request another retry outside that
bounded loop or approve merely because the retry limit is near.
