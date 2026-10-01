---
name: product-brief-generator
description: Turn one raw idea into one strict PTW Product Brief validation hypothesis, or create a complete immutable correction from a base Brief and one owner instruction. Use for Stage 1 Product Brief generation, inspection, correction, retry, or approval review. Do not use for market research, SEO, YouTube, evidence reports, landing copy, ad creatives, publishing, traffic, analytics, or product implementation.
---

# Product Brief Generator

Create one useful positioning and brand hypothesis from one owner idea.

## Required references

Read `references/output-contract.md` and `references/owner-lessons.md` before
generating or correcting a Brief. For V2/V3 use the server-selected immutable policy
from `references/marketing-approaches.md`; only that approach applies.

## Method

1. Treat the raw idea as the only business-fact input. Marketing approach is
   owner-selected guidance, not evidence. Apply the supplied policy snapshot.
2. Use the server-supplied `required_language`, chosen by the owner when the
   Project is created. It is authoritative even when the raw idea is written in
   another language. The server constrains the output schema to that exact
   value; use it for the `language` field and every output string.
3. Think like a direct-response marketer and choose one promising
   differentiation: a narrower first audience, clearer promise, emotional
   angle, trust mechanism, faster perceived result, lower friction, easier
   onboarding, or stronger offer.
4. Return one hypothesis, never options, rankings, personas, research notes,
   evidence wrappers, messaging matrices, landing copy, ad concepts, or FAQs.
5. Choose one compelling, low-friction next step appropriate to this product
   and audience. The agent decides the offer format: exploring a relevant use,
   asking about availability, trying a supplied capability, booking a supplied
   service, or another natural first action. An offer need not be a promotion.
   Do not default to consultation or invent free access, discounts, durations,
   availability, guarantees or services. Preserve any explicit owner offer.
6. Keep the CTA singular and consistent with the offer.
7. Use trust mechanisms the owner can honestly provide: a real person or
   consultant photo, transparent price, no spam, no card, or real social proof
   only when supplied. Never invent testimonials, ratings, customers, results,
   credentials, urgency, deadlines, or scarcity.
8. Return strict structured output only. Server validation assigns `brief_id`,
   checks the shape and required language, and owns persistence.

## Identity-led quality check

Make `promise` a punchy headline: aim for 3–5 words, one beat, usually at most
45 characters. Put service explanations and ownership/cost tradeoffs in product,
benefits or functional_value, not a trailing "without..." headline clause.
Do not confuse brevity with an empty slogan: retain a recognizable occasion.
V3 `brand_identity` makes the brand's belief, values, identity signal, category
reframing, emotional reward, competence cue, practical anchor, voice and visual
world explicit. Use the selected policy's definitions; a use occasion alone is
insufficient. For Identity-led, connect a meaningful category reframe, one
grounded convention or tradeoff, the buyer's valued self-image and the supplied
function that earns the emotional reward. The tension may be a hypothesis for a
sparse idea, never an invented market fact, danger or competitor. Ritual is optional.
Voice should fit the audience; plain precise wording is valid. Elevated wording
is an optional technique, never a requirement for premium positioning.
`desired_identity` names a valued self-image and the values behind it;
`category_frame` names the occasion and the product's role there. Together they
brief copy and artwork agents on what the buyer wants to feel/become. Express
resourcefulness through a smart relevant choice, not flattery, IQ claims or
superiority over other people. Keep functional_value as the factual anchor.

For identity-led Briefs, make one specific occasion, aspiration or category
reframing visible in the product, audience, promise and offer as well as
positioning. Quietly compare a few distinct directions, choose the strongest
functionally grounded one, and return only that hypothesis. A sparse idea permits
a bold audience/use-occasion hypothesis; it does not permit new product features.
Reject a generic category description with an identity label attached, such as
"I choose transport for my needs." The headline should make the selected angle
recognizable without reading positioning. Avoid defaulting to competence or ease
when a concrete human occasion is available. Existing policy snapshots and owner
constraints remain authoritative; this check sharpens expression within them.

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
- Follow the supplied contract: V3 adds brand_identity, V2 only positioning;
  V1 has neither. Never upgrade a reservation on retry.
- An approach switch applies to this Brief only. Preserve feedback and weight
  lineage without promoting that selection to a global lesson.

## Verification

Check strict shape, required language, three to five distinct benefits,
mandatory offer, singular CTA, fabricated-proof rejection, deterministic
digest, immutable replacement lineage, retries, and approval gating.

Run:

```sh
python3 -m unittest discover -s tests/validation_pipeline -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
