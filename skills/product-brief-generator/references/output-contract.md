# Versioned Product Brief output contract

The model returns exactly this object. The server adds the UUIDv7 `brief_id`.

```text
schema_version: 1 | 2
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

Human-facing copy must be concise, concrete and written in `language`.
V1 copy fields are non-empty; V2 desired_identity may be empty.
The output is one testable marketing hypothesis. The offer must reduce friction
and be practically honor-able; it does not redefine the proposed product.
The owner-selected Project language is persisted as `required_language`. The
server binds `language` to that exact value in the structured-output schema,
even when the raw idea is written in another language.

Do not include IDs, sources, assumptions, alternatives, market analysis,
confidence, performance projections, hooks, image ideas, landing copy, or
additional properties. Server code computes the canonical SHA-256 digest and
assigns identity.

New reservations use V2, adding exactly `positioning` with:
`marketing_approach: benefit_led | identity_led`, `desired_identity`,
`customer_tension`, `category_frame`, and `functional_value`.
The server constrains the approach to the reserved owner selection. All four
copy fields use the required language and at most 200 characters; only
`desired_identity` may be empty. The whole positioning object must fit 1024
UTF-8 bytes (shorten Ukrainian sentences accordingly). It records a testable
positioning hypothesis, never researched evidence or additional capabilities.
Historical V1 reservations and documents keep the original fields above.
