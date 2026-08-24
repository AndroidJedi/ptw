# CreativeSetV1 output contract

The model returns exactly:

```text
schema_version: 1
creatives: exactly 5 items
```

Each item has exactly:

```text
angle: emotional | practical | curiosity | authority | problem_first
hook: string
primary_text: string
image_description: string
cta: string
desired_emotion: string
image_category: string
image_search_query: string
crop_focus: left | center | right
```

Order is emotional, practical, curiosity, authority, problem-first. CTA must
equal the approved Brief CTA. Copy must visibly retain the Brief offer.
`image_search_query` is concise English suitable for Pexels; ad copy follows
the Brief language. Server code adds `creative_id`, `brief_id`, image metadata,
and digests.
