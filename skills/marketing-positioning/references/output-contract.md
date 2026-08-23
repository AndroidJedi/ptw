# PositioningDocumentV1 output contract

Return one object with `schema_version: 1`, `output_language`, the five sections
below, `evidence_references`, and `assumptions`. Every copy value is an evidence
statement with exactly:

```json
{"text":"...","source_ids":["uuid"],"assumption":false}
```

When `source_ids` is empty, `assumption` must be true. `evidence_references`
must exactly equal the unique source UUIDs cited anywhere in the document.

## 1. Positioning foundation

- `category`
- `competitive_alternatives` (one to six)
- `definitive_audience`
- `jobs`, `pains`, and `gains` (one to six each)
- `uvp`

Use the Value Proposition Canvas and Obviously Awesome as methods. Do not cite
the methods as evidence for facts about this idea or market.

## 2. Messaging matrix

One to eight rows. Each row contains `feature`, `functional_benefit`, and
`emotional_reward`. Keep the causal progression credible.

## 3. Landing copy

- `hero`: `eyebrow`, `headline`, `subheadline`, `cta`
- exactly three `value_sections`, each with `title` and `body`
- `honest_limitation`
- `lead_capture_strategy`

The limitation must be a real supplied limitation with source UUIDs. Otherwise
state plainly that results are not yet verified and mark it as an assumption.

## 4. Ad concepts

Return exactly two items in this order:

1. `contextual_relatable`
2. `direct_problem_solution`

Each contains `hook`, `body`, and `visual_direction`. They are concepts for the
Ads workspace, not published posts or performance promises.

## 5. AEO FAQs

Return exactly three items. Each contains `question`, `definition`, `data`, and
`context`. Definition, Data, and Context are each exactly one sentence. “Data”
means the best source-backed concrete answer available; it does not require a
number and must not manufacture one.

Server code computes quality gates and the canonical SHA-256 digest. Do not
invent gate results.
