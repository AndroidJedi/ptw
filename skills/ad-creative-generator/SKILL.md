---
name: ad-creative-generator
description: Generate or inspect one PTW Stage 2 batch of exactly five complete Ad Creatives from one explicitly approved Product Brief. Use for creative-batch generation, retry review, real-photo direction, creative feedback, or owner lesson proposals. Do not use for Product Brief generation, raw-idea analysis, market research, AI image generation, landing pages, ad publishing, traffic purchase, campaigns, UTMs, analytics, or optimization.
---

# Ad Creative Generator

Generate a coherent five-post experiment from the approved Product Brief and
nothing else.

## Required references

Read `references/output-contract.md`, `references/real-photo-policy.md`, and
`references/owner-lessons.md` before generating a batch.

## Input boundary

- Business input is exactly one approved Product Brief, including `brief_id`.
- Never request or use its raw idea, research, market context, performance data,
  previous creatives, landing copy, campaigns, or owner history.
- Preserve the Product Brief CTA exactly in all five creatives.
- Carry the exact offer through every complete concept. Do not weaken, silently
  alter, or invent an alternative promotion.

## Generation method

Return one structured response containing exactly five complete creatives in
this fixed order:

1. `emotional`
2. `practical`
3. `curiosity`
4. `authority`
5. `problem_first`

Each is a coherent post: hook, primary text, real-photo description, CTA,
desired emotion, image category, English Pexels search query, and crop focus.
Explore the five angles intentionally; do not call the result optimized.

Use authority through clarity, a real expert, transparent process, or supplied
credentials—not fabricated testimonials, ratings, client counts, outcomes, or
proof. Avoid artificial urgency, unsupported scarcity, and guaranteed results.

Return strict structured output only. Server code assigns the five UUIDv7
`creative_id` values, selects images, renders artifacts, and persists the batch
atomically.

## Feedback and learning

- Feedback evaluates the resolved complete creative UUID, not an isolated hook,
  CTA, or image.
- Each feedback creates append-only feedback and weight entities plus an
  editable generalized lesson proposal.
- Promotion may update only `references/owner-lessons.md` through bounded owner
  Plan/Execute. Never silently mutate this skill from performance or feedback.

## Boundaries

- Do not generate AI artwork or synthetic faces.
- Do not publish ads, purchase traffic, create campaigns, add UTMs, or consume
  click/conversion analytics.
- Do not split generation into hook, CTA, copy, or image sub-generators.
- Do not add fields or change angle order.

## Verification

Check the input boundary, one structured call, five fixed distinct angles,
exact CTA and offer continuity, unique IDs, real-photo selection, deterministic
1080×1080 JPEG output, attribution, atomic failure, retries, and feedback
lineage.

Run:

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
