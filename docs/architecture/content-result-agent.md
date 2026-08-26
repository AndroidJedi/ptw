# PTW five-template Result architecture

## Flow

```text
approved Product Brief + owner task + Project brand/assets
  -> bounded ContextBundleV1
  -> five isolated versioned strategies
  -> validated CandidateV2 documents and previews
  -> three Result/Critic passes
  -> one immutable Result Creative
```

`ContentContextAssembler` selects one technique guide, one strategy, and four
to six deterministic corpus excerpts without truncation. The writing bundle is
bounded near 5,500 tokens and total system context near 8,000 tokens excluding
structured payload/tool data. Selection order and every digest are persisted.

`CandidateGenerationOrchestrator` reserves all stable IDs before side effects,
loads exactly five active template versions, and invokes them independently at
maximum JSON concurrency two. Initial failure after one fresh structured retry
fails the run. At most four improvement calls occur across critic Passes 1–2.
The global run deadline is 45 minutes.

The templates are `moment_tension@1`, `contrast_reframe@1`,
`mechanism_proof@1`, `human_story@1`, and `direct_offer@1`. Five integer sliders
retain exact 0–100 values and template-specific envelopes. Critic deltas are
multiples of five, change at most two dimensions, and change a chosen dimension
by at least ten.

`ResultCriticAgent` receives anonymized candidates, exact element IDs,
parameters, previous pass summaries, and exact mapped renders. Pass 1 explores
and synthesizes; Pass 2 challenges, detects regressions, and tunes; Pass 3
reapplies gates and compares the final two without generating anything.
Models emit typed actions and concise reason codes. Server code alone validates,
executes, renders, and persists them.

Hard gates protect task/Brief relevance, offer, CTA, language, honest claims,
Project and media ownership, coherent message, no synthetic people/faces,
layout, legibility, caption, and alt text. Eligible candidates must also meet
the versioned element and weighted candidate thresholds. If neither finalist
qualifies, the run fails closed and exposes retry guidance rather than a bad
result.

## Identity and persistence

Server-assigned UUIDv7 is primary identity. Exact reuse points to the same
element UUID; replacement creates `supersedes`; conceptual adaptation creates
a new UUID with every source in `derived_from`. Aliases such as `C2.HOOK.01`
are debug labels only.

The clean baseline persists runs, candidates, previews, elements, immutable
candidate-element associations, critic passes, typed actions, results,
outcomes, skill proposals, checkpoints, attempts, provider invocations,
recipes, renders, sources, entities, and graph edges. Only bounded run/action
status transitions update. A retry creates a child run and never overwrites its
parent.

The owner normally sees only source, result type, task, three progress stages,
one final result, two-to-four selection observations, download/use, retry, and
feedback. Debug exposes bounded IDs, versions, scores, gates, actions, digests,
provider request IDs, and lineage, never chain-of-thought, credentials, raw
base64, or unrestricted source contents.
