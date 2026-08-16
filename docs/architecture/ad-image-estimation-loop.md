# Ten-context ad image estimation loop

Status: implemented Commander workflow
Owner: marketing ad contexts A01-A10
Runtime authority: PostgreSQL entities, edges, and ad workflow projections

## Purpose

Turn one immutable Idea Evolution idea into ten image-post hypotheses, collect
the owner's predicted link CTR and qualitative feedback before analytics exist,
and let only the context that produced each post conclude from that feedback.
The implementation reuses Commander's entity graph, transactional outbox,
append-only feedback/weight history, artifact storage, and bounded recovery.

## Exact sequence

1. Idea Evolution validates `/ads from <idea-id>` and sends its immutable idea
   snapshot to `POST /internal/ad-batches` with the Telegram update ID as the
   idempotency key.
2. The batch snapshots active revisions A01-A10 and moves from `queued` to
   `generating`.
3. Each context makes one creative-spec call and one high-quality image call.
   No Telegram photo is queued until all ten final files and graph records exist.
4. Review state becomes `awaiting_owner`, and only image 1 is placed in the
   existing Telegram outbox.
5. The owner replies `/estimate <predicted-CTR%> <1-5> [feedback]`. Telegram's
   delivery map resolves the reply to the permanent Creative UUID.
6. HumanFeedback and append-only WeightUpdates commit before the producing
   context receives the selected idea, snapshotted context, final image, and
   owner feedback.
7. One `ad_context_conclusion` Insight commits for that Creative. The same
   transaction advances and queues the next photo. Position 10 instead commits
   completion and queues the ranked summary.
8. An analytics import later creates an immutable Source and one MetricSet per
   Creative, calculates actual link CTR, and records its percentage-point
   difference from the owner's estimate.

Every provider phase uses an initial attempt plus at most two recoveries.
Completed slots are not regenerated. A terminal step error preserves the batch
for `/ads continue <batch-id>` and returns a configuration/action message.
The successful batch contract is exactly ten creative-spec calls, ten image
calls, and ten owner-feedback-grounded multimodal conclusion calls.

## Contexts and lineage

The required active set is exactly:

| Code | Intention |
| --- | --- |
| A01 | Pain and urgency |
| A02 | Desired outcome |
| A03 | Contrarian reframe |
| A04 | Mechanism |
| A05 | Concrete use case |
| A06 | Status-quo comparison |
| A07 | Identity and emotion |
| A08 | Credibility and proof |
| A09 | Pattern interrupt |
| A10 | Direct-response CTA |

Context edits are versioned; a batch keeps its original revision snapshots.
The graph for each slot is:

```text
Idea Source snapshot <-derived_from- Campaign -contains-> Creative
        ^                                      |
        |                                      +contains-> CreativeComponents
        +derived_from- Hypothesis <-generated--+
                                               +generated-> Artifact

HumanFeedback -evaluates-> Creative
Conclusion Insight -derived_from-> HumanFeedback and Artifact
Conclusion Insight -evaluates-> Creative
Creative -measured_by-> MetricSet -derived_from-> Analytics Source
```

## Provider and image contract

`AdCreativeSpec` contains concept name, audience, angle, hook, supporting copy,
CTA, and a text-free visual prompt. The concept name must equal the idea title.
Pre-build copy rejects fabricated proof and numeric claims not present in the
idea snapshot.

Production image generation uses the current `gpt-image-2` alias through the
Images API with `quality=high` and a 1536×1920 source request. The renderer
validates the decoded source dimensions, composes deterministic typography, and
saves the final 1080×1350 PNG. The Artifact records requested and returned model,
prompt, quality, source/final dimensions, source digest, final digest, and paths.
Any configured model other than `gpt-image-2` fails explicitly; there is no
model fallback. See the [official GPT Image 2 model documentation](https://developers.openai.com/api/docs/models/gpt-image-2).

Creative specifications and multimodal conclusions use `gpt-5-mini` as the
approved model for this workflow. Each conclusion has feedback interpretation,
effective elements, improvements, context-intention fulfillment, and a future
revision direction.

## Analytics import

Authenticated `POST /internal/ad-batches/{batch-id}/metrics` accepts:

```json
{
  "source_system": "analytics-export",
  "import_id": "immutable-export-id",
  "captured_at": "2026-08-16T12:00:00+03:00",
  "attribution_window": "7d-click",
  "creatives": [
    {"creative_id": "uuid", "impressions": 1000, "link_clicks": 18}
  ]
}
```

`(source_system, import_id)` is idempotent. Rows must belong to the batch and
satisfy `0 <= link_clicks <= impressions`.
