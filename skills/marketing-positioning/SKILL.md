---
name: marketing-positioning
description: Turn a raw business idea and a selected market into an evidence-explicit PTW Marketing Positioning document for downstream Natal Landing and Ads work. Use when creating, inspecting, correcting, exporting, or approving an immutable positioning revision; planning bounded positioning research; or reviewing positioning evidence, assumptions, ad concepts, and AEO FAQs. Do not use for arbitrary branding, landing publication, ad generation, or ad publishing.
---

# Marketing Positioning

Create a focused, truthful positioning document that Landing and Ads can consume
without reconstructing strategy.

## Required references

Before generating or correcting a document, read:

- `references/output-contract.md` for the exact five-section result.
- `references/evidence-policy.md` for source UUIDs, assumptions, proof, and
  research limits.
- `references/owner-lessons.md` for lessons the owner has explicitly promoted.

## Method

1. Start with the owner idea, selected country, research language, and output
   language. Do not silently broaden the audience or market.
2. Use the Strategyzer Value Proposition Canvas to identify customer jobs,
   pains, and gains. Use April Dunford's positioning method to identify the
   alternatives customers would use, differentiated value, the audience that
   cares most, and the market category that makes the value clear.
3. Treat those methods as reasoning tools, not sources for product or market
   facts. Ground the result in the supplied owner-idea Source and durable
   research Sources.
4. Build layered messages from feature to functional benefit to emotional
   reward. The emotional layer must follow from the functional layer; avoid
   vague identity claims.
5. Write answer-first, restrained copy. Prefer concrete plain language,
   honest limitations, and contextual ad moments. These are heuristics, not
   guaranteed performance techniques.
6. Return strict structured output only. Server-owned validation decides
   whether the document passes and persists.

## Research workflow

- `marketing_positioning_research_plan` returns two to four bounded queries for
  the chosen country and language. Cover alternatives, jobs/pains/gains,
  category language, or limitations.
- Live research uses only the configured verified catalog, paid-task reuse,
  safe public HTTPS pages, and the total USD 0.05 ceiling.
- No fixture, stale cache, generic model knowledge, or synthesized substitute
  may stand in for failed live research.
- Every selected finding enters through `ResearchKnowledgeService` as a
  permanent Source before synthesis.

## Revision and approval

- A correction names one section and one owner instruction. Receive the whole
  base document, make the focused change, and return a complete coherent
  replacement document.
- The base remains active until the owner explicitly approves the replacement.
  Approval never republishes an existing Landing.
- Feedback evaluates the exact base revision. The replacement supersedes that
  base and derives from the feedback and its source set.
- Propose a short generalized lesson, but never write an owner comment directly
  into this skill. Promotion may edit only `references/owner-lessons.md`
  through bounded Plan/Execute and must run the skill verifier.

## Boundaries

- Do not invent or imply metrics, testimonials, ratings, customer results,
  limitations, competitor capabilities, prices, urgency, scarcity, or proof.
- Do not reuse the attachment's percentages, ad-volume figures, deal-closure
  claims, rating formulas, or named performance attributions.
- An uncited inference must be visibly marked as an assumption. A limitation
  must be supplied and sourced or explicitly say results are not yet verified.
- Do not generate or publish a Landing or an ad. The positioning document
  contains downstream inputs; mutations stay in their own workspaces.

## Verification

Check strict shape, allowed Source UUIDs, unsupported-claim rejection, exactly
three Landing value sections, exactly two ordered ad concepts, exactly three
Definition–Data–Context FAQs, a real honest limitation, deterministic digest,
retry durability, revision lineage, approval gating, and Markdown export.

Run:

```sh
python3 -m unittest discover -s tests/marketing_positioning -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
