# Marketing Positioning evidence policy

The owner idea and every selected research finding are permanent Source
entities with UUIDs. Cite only Source UUIDs supplied in `allowed_sources`.

## Factual claims

- A category, alternative, audience fact, job, pain, gain, product capability,
  limitation, competitor fact, metric, result, or testimonial is factual.
- Cite the source that directly supports it. Nearby topical relevance is not
  support.
- If the owner idea states an intended capability, cite the owner-idea Source
  and describe it as intended when availability is not verified.
- If no source supports an inference, mark it as an assumption in its field and
  include a plain-language entry in the top-level assumptions list.

## Claims that must not be invented

Never create percentages, time savings, customer counts, ratings, quotes,
revenue, deal results, ad performance, prices, integrations, credentials,
competitive capabilities, deadlines, or scarcity. Do not convert a heuristic,
owner correction, search-result rank, or model confidence into proof.

## Honest limitation

Use a real, supplied limitation and cite it. If none exists, say “Results are
not yet verified” in English or “Результати ще не підтверджені” in Ukrainian,
with no source IDs and `assumption: true`. Do not invent a charming flaw for a
trust effect.

## Research safety and cost

- Use two to four market/language-specific queries.
- Reuse a paid provider task ID after retry; never pay for the same query twice.
- Persist provider cost exactly once and never exceed USD 0.05 for a revision.
- Fetch only public HTTPS text pages through the bounded safe-page reader.
- Failed live research or strict synthesis is a durable failure. There is no
  fixture, unsourced model-knowledge, or silent live fallback.
