# ProductBriefV1 output contract

The model returns exactly this object. The server adds the UUIDv7 `brief_id`.

```text
schema_version: 1
language: uk | en
product: string
target_audience: string
main_pain: string
promise: string
key_benefits: string[3..5]
cta: string
trust_strategy: string
offer: string
```

Every string must be concise, concrete, non-empty, and written in `language`.
The output is one testable marketing hypothesis. The offer must reduce friction
and be practically honor-able; it does not redefine the proposed product.

Do not include IDs, sources, assumptions, alternatives, market analysis,
confidence, performance projections, hooks, image ideas, landing copy, or
additional properties. Server code computes the canonical SHA-256 digest and
assigns identity.
