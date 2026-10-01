# Private marketing approach trial

2026-09-29. This is a generation and editorial review, not conversion evidence.
Benefit-led remains the default. No approval, publication, paid experiment or
automatic learning activation occurred in the real trial.

## Method

Six private examples use three fixed ideas: bottled-water label comparison,
career-change mentoring, and a property repair request tracker. Within each pair,
the raw idea, English language, `gpt-6-astra` model, `xhigh` structured reasoning
and the native seed Post/Landing template pair stay constant. The approach is
the changed input. Brief and Natal copy use the real local Codex provider and
canonical skills; templates are held fixed instead of generated again.

Each example retains its V2 Brief, exact policy/document digests, bindings,
image direction and native desktop/mobile PNGs. Initial previews hold neutral
fixture artwork constant to isolate copy. Separate artwork previews use the
real local image provider, the exact source positioning and the same selected
agent model (`low` image-worker reasoning). The provider does not expose its
underlying image-model version; image-model identity cannot be independently
verified. No production bridge canary or production database mutation is part
of this trial.

Open `.local/marketing-approaches-trial/index.html` for the paired Post and
desktop/mobile Landing gallery, with links to each Brief and provider receipt.

Reproduce with:

```sh
.venv/bin/python scripts/run_marketing_trial.py
.venv/bin/python scripts/run_marketing_trial.py --artwork-only
```

Completed calls are reused from the private output directory. Changed model,
idea or template inputs require a new directory under `.local`. A failed Brief
stops the trial for inspection; it is not silently replayed. Evidence lives in
`.local/marketing-approaches-trial/`; PNGs and provider receipts stay private.

## Editorial comparison

| Idea | Benefit-led Post | Identity-led Post | Assessment |
| --- | --- | --- | --- |
| Water labels | Make sense of water mineral labels. | Know what you choose. | The identity promise is supported by label comparison and plain-language explanations. The supporting line must retain the product context because the hook alone is generic. |
| Career mentoring | Find your first step toward a new career. | Take a thoughtful step toward a new career. | Both are specific to a first conversation. The identity distinction is modest; no reason to force status, rebellion or a premium category. |
| Repair tracker | Know who owns each repair request. | Be the coordinator who knows where repairs stand. | The identity is concrete and work-related. Request recording, ownership and status remain the functional explanation; no response-time guarantee is added. |

All pairs preserve their supplied offers: free early access or the free first
15-minute mentor call. Positioning, Post and Landing remain consistent with the
same capabilities. The generated directions show everyday product situations,
without invented application screens, testimonials, medical outcomes or luxury
positioning. There is no evidence here that Identity-led performs better.

## Failures, revisions and limits

- The first water Benefit-led binding contained a line break accepted by copy
  validation but rejected by the renderer. Natal now applies the renderer's
  bounded single-line check inside response validation, allowing the existing
  corrective response path to handle it. A regression covers failure/retry
  without replacing the Brief. The trial regenerated that binding against its
  existing Brief and retained the final response before rendering.
- The simple Landing template has only headline, support and CTA copy. All six
  responses used the support field for limitations. The wording is grounded,
  but this gives disclaimers too much prominence and leaves less room for useful
  explanation. Review a fuller existing Landing template before judging the
  approach's ability to develop benefits and objections. This observation did
  not create a global rule or change the owner's claim boundaries.
- Both water images depict label comparison and both mentoring images depict
  a quiet call. That consistency fits the concepts; the emotional distinction
  is subtle. The narrow mobile crop cuts part of the second bottle and much of
  the mentoring desk context; maintenance crops also lose the tap or a teammate.
  Geometry checks alone cannot detect that loss of
  meaning. A future package-specific image edit can request a tighter central
  grouping for those slots while retaining the selected template.
- Native geometry checks found no text overflow in the six fixed-art examples
  or their six generated-artwork variants.
  These fixed seed layouts are trial fixtures, not a claim that every reusable
  template has been visually validated with this copy. Generated artwork is
  illustrative; subjects are not represented as actual consultants or customers.

Implementation validation also covers English/Ukrainian contracts, populated
Ukrainian context at the full 1 KiB positioning bound, corrective-response
headroom, old V1 reservations, immutable replacements, concurrent PostgreSQL
requests, restarts, pinned source Briefs, and desktop/360px/iPhone entry flows.

## Four-move Identity-led prompt review — local

Editorial policy revision 6 asks Briefs to connect a category reframe, a
grounded convention or tradeoff, the buyer's valued self-image and a real
functional reason for the emotional reward. Fitting plain language is valid;
elevated diction is optional. No output contract or provider budget changed.

Two fresh real `gpt-6-astra` / `xhigh` Briefs and Natal Post/Landing bindings
used the same source Brief for each pair:

| Idea | Brief identity | Post and Landing continuity |
| --- | --- | --- |
| Ukrainian bottled-water label comparison | An attentive buyer understands a daily choice; side-by-side labels and plain explanations support it. The challenged habit is choosing a familiar bottle without comparing composition. | Both final Natal titles say “Знаю, чому обираю цю воду”; support names the actual label task. |
| English property-maintenance handover | A dependable lead leaves teammates a clear starting point; the request, assigned owner and recorded status support it. The tension is moving on quickly while leaving unfinished work unclear. | Both Natal titles say “Give Teammates a Clear Start”; support names the repair list and handover details. |

Direct Project Post and Landing composition was also run with each exact Brief.
The Ukrainian Post/Landing shared “Знаю, чому обираю воду”; Landing features
addressed the familiar-bottle habit, label comparison and a self-explainable
choice. The English final Post/Landing shared “Give Teammates a Clear Start”;
the Landing explained request, owner and status without promising prediction or
response times. Both used ordinary language. No fabricated testimonials or
measured outcomes were added. Post Phone Metrics numbers remain explicitly
unvalidated hypotheses and were not reused as Landing proof.

The first Natal binding crowded the Ukrainian tension into a longer Landing
title. Its revised prompt moved the tension into support and kept the short
Post hook on both surfaces. The first English direct Post had an incomplete
offer, invisible Unicode formatting and a cut-off image direction. The final
Post prompt asks for complete bounded phrases; a generated-copy validator now
rejects invisible formatting before artwork. A fresh real run returned a
complete offer and image direction. The focused failure/retry regression passes.

Receipts are under `.local/identity-four-principles-water-uk/`,
`.local/identity-four-principles-water-bindings-v3/`,
`.local/identity-four-principles-water-composers/`, and matching
`identity-four-principles-maintenance-*` private folders. Natal fixture renders
reported no geometry issues on Post desktop or Landing desktop/mobile. Direct
composer output passed its bounded domain validators. This review did not
generate new final artwork, approve drafts, publish, or measure conversion.
