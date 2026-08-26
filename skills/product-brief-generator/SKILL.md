---
name: product-brief-generator
description: Turn one raw idea into one strict PTW Product Brief validation hypothesis, or create a complete immutable correction from a base Brief and one owner instruction. Use for Stage 1 Product Brief generation, inspection, correction, retry, or approval review. Do not use for market research, SEO, YouTube, evidence reports, landing copy, ad creatives, publishing, traffic, analytics, or product implementation.
---

# Product Brief Generator

Create the smallest useful positioning hypothesis from one owner idea.

## Required references

Read `references/output-contract.md` and `references/owner-lessons.md` before
generating or correcting a Brief.

## Method

1. Treat the raw idea as the only business input.
2. Infer `uk` when Ukrainian Cyrillic letters dominate and `en` when Latin
   letters dominate; default to `en` on a tie or ambiguous input.
3. Think like a direct-response marketer and choose one promising
   differentiation: a narrower first audience, clearer promise, emotional
   angle, trust mechanism, faster perceived result, lower friction, easier
   onboarding, or stronger offer.
4. Return one hypothesis, never options, rankings, personas, research notes,
   evidence wrappers, messaging matrices, landing copy, ad concepts, or FAQs.
5. Always create one strong, low-friction validation offer. Prefer a rich but
   honor-able promise such as a free first consultation, free assessment,
   useful promo code, concrete discount, or early access. The offer is a
   marketing promotion and must not change the proposed product.
6. Keep the CTA singular and consistent with the offer.
7. Use trust mechanisms the owner can honestly provide: a real person or
   consultant photo, transparent price, no spam, no card, or real social proof
   only when supplied. Never invent testimonials, ratings, customers, results,
   credentials, urgency, deadlines, or scarcity.
8. Return strict structured output only. Server validation assigns `brief_id`,
   checks the shape and inferred language, and owns persistence.

## Corrections and approval

- A correction receives the raw idea, the complete base Brief, and one owner
  instruction. Return a complete coherent replacement, not a patch.
- The replacement keeps a new immutable `brief_id`, supersedes its base, and
  requires fresh owner approval.
- Approval means the owner confirms that the exact promise and offer can be
  honored. Do not infer approval.
- Propose a generalized lesson from owner correction, but do not edit this
  skill automatically. Promotion may update only
  `references/owner-lessons.md` through the bounded owner workflow.
- Keep each correction-feedback proposal UUID for lineage, while appending all
  pending Product Brief proposals into one editable combined lesson and one
  shared Plan/Execute command.

## Boundaries

- Do not browse, search the market, or call SEO, YouTube, paid research, social,
  competitor, keyword, trend, or analytics providers.
- Do not cite model knowledge as evidence or manufacture proof.
- Do not generate Result candidates or channel content.
- Do not add fields outside the v1 contract.

## Verification

Check strict shape, inferred language, three to five distinct benefits,
mandatory offer, singular CTA, fabricated-proof rejection, deterministic
digest, immutable replacement lineage, retries, and approval gating.

Run:

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
