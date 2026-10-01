# Versioned Product Brief output contract

The model returns exactly this object. The server adds the UUIDv7 `brief_id`.

```text
schema_version: 1 | 2 | 3
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
and be practically honor-able; it does not redefine the proposed product. V2
accepts a natural next step without requiring promotional keywords, a discount,
free access or a consultation. Historical V1 retains its promotion validation.
The owner-selected Project language is persisted as `required_language`. The
server binds `language` to that exact value in the structured-output schema,
even when the raw idea is written in another language.

Do not include IDs, sources, alternatives, market analysis,
confidence, performance projections, channel copy or properties outside the
supplied schema. V3 brand voice and visual direction are required strategy fields,
not finished ads. Server code computes the canonical SHA-256 digest and
assigns identity.

V2 adds exactly `positioning` with:
`marketing_approach: benefit_led | identity_led`, `desired_identity`,
`customer_tension`, `category_frame`, and `functional_value`.
The server constrains the approach to the reserved owner selection. All four
copy fields use the required language and at most 200 characters; only
`desired_identity` may be empty. The whole positioning object must fit 1024
UTF-8 bytes (shorten Ukrainian sentences accordingly). It records a testable
positioning hypothesis, never researched evidence or additional capabilities.
Historical V1 reservations and documents keep the original fields above.

New reservations and new corrections of V1/V2 use V3: retain all V2 fields and
add `brand_identity` with exactly `belief`, `identity_signal`, `values`,
`cultural_tension`, `category_reframe`, `emotional_reward`, `competence_cue`,
`proof_anchor`, `voice`, `visual_world`, `ritual`. Each is text <=260 characters;
the entire object <=3072 UTF-8 bytes. All use the required language. The V3
schema permits empty cultural_tension for historical snapshots; current
Identity-led policy asks for one grounded convention or tradeoff. Ritual may be
empty. Benefit-led may also leave identity_signal and emotional_reward empty.
Definitions live in the selected policy. Keep positioning concise; expand the
brand viewpoint in this dedicated section. Do not repeat the same line throughout.
Historical V1/V2 documents and queued/failed reservations retain their contracts.
Upgrading through a correction creates an unapproved V3 replacement using the
current policy for the inherited approach. V3 corrections inherit their snapshot
unless the owner explicitly changes approach. Retries never upgrade.
