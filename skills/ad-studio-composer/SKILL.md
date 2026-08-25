---
name: ad-studio-composer
description: Compose, revise, template, or inspect PTW Ad Studio recipes, five-angle editable sample sets, reviewed non-human graphics, and published training examples using the versioned framed-tool catalog. Use for manual or agent-facing Instagram/TikTok Studio work. Do not use for changing the existing automatic five-angle Ad batch, publishing, campaigns, traffic, or analytics.
---

# Ad Studio Composer

Create one deterministic, Project-scoped Studio recipe from one approved Product
Brief, one immutable Project brand kit, approved Project sources, and the live
tool catalog. A five-post sample set may also consume one explicitly selected,
completed five-angle Ad batch from the same Brief and Project.

## Required references

Read [references/recipe-contract.md](references/recipe-contract.md) when creating,
revising, templating, or inspecting a recipe. Read
[references/owner-lessons.md](references/owner-lessons.md) before proposing a
composition.

## Composition boundary

- Preserve the approved Brief's offer and CTA exactly in their single required
  frames. Do not invent proof, results, testimonials, ratings, urgency, or
  scarcity.
- Use only tool IDs returned by the live Studio catalog. Never infer an ID or
  reuse a deprecated version.
- Keep every frame inside normalized canvas bounds and every motion interval
  inside the placement duration.
- Use only Project-owned uploaded media, imported Pexels assets, the packaged
  Natal identity, or owner-reviewed generated graphics. Preserve every source
  UUID and its origin/provider/prompt/digest lineage.
- Generated media is limited to explicit owner requests for non-human abstract
  or symbolic graphics. Reject synthetic people, faces, testimonials, logos,
  embedded copy, or unreviewed generated output.
- Treat TikTok support as a placement-native vertical-video extension, not as a
  claim derived from the Instagram reference articles.

## Templates and learning

Templates preserve framed composition and tool IDs with typed bindings for the
approved Brief, selected completed Creative, and Project brand kit. Applying a
template creates fresh instance UUIDs and resolves every binding server-side;
stale copy or media from another Brief or Project must never leak into it.

An AI revision is always a proposal. It receives one immutable base recipe,
one owner instruction, an optional selected frame, the approved Brief, brand
kit, Project sources, and the live catalog. Previewing is non-mutating. Explicit
Apply creates one validated immutable child recipe and render. Offer, CTA,
Brief, Project, and brand identity remain protected.

Only explicitly published renders are training examples. Feedback targets the
resolved render UUID and creates append-only feedback, weight, and proposal
entities. Promotion may update only this skill's `references/owner-lessons.md`
through owner-reviewed Plan/Execute; never learn silently.

## Boundaries

Do not switch or modify the production `ad_creative_batch` generator, publish
ads, buy traffic, add campaign/UTM/analytics behavior, or use prior Studio
examples as unapproved hidden input. Consuming an explicitly selected completed
batch for a visible five-post sample set is not permission to feed Studio state
back into that generator.
