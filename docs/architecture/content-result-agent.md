# PTW five-template Result architecture

## Flow

```text
approved Product Brief + fixed server task + canonical Natal brand/assets
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

The strategies are `moment_tension@2`, `contrast_reframe@2`,
`mechanism_proof@2`, `human_story@2`, and `direct_offer@2`. Each is digest-bound
at startup to one matching Git-owned `ptw.studio.template.v1` component tree;
missing, extra, version-skewed, or digest-skewed active definitions stop startup.
Five integer sliders
retain exact 0–100 values and template-specific envelopes. Critic deltas are
multiples of five, change at most two dimensions, and change a chosen dimension
by at least ten.

The Instagram adapter, not the generic orchestrator, resolves each slider into
an ordered typed component patch. Only numeric interpolation, enumerated steps,
and bounded optional-component thresholds are accepted. Geometry is quantized
to 0.001 and typography to declared integer steps. The patch cannot change
component identity, tool IDs, protected copy, source assets, palette bindings,
or any path absent from the component catalog.

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

Every configured Instagram recipe carries one
`studio.layout.template_application.v1` modifier: the immutable template
snapshot, strategy/Studio/catalog/renderer versions and digests, exact and
normalized sliders, component-key-to-UUID map, protected typed bindings,
ordered before/after patch, and optional parent recipe/base digest. Improved
candidates point `parent_recipe_id` at the direct base recipe and add a
`derived_from` edge. The render manifest stores the complete resolved recipe,
source/output digests, and the same production identities. Replaying the stored
snapshot, bindings, sliders, and reserved IDs must reproduce the canonical
recipe digest and decoded pixels.

The owner normally sees only the approved source, one Instagram create action,
three progress stages, one final post, two-to-four selection observations,
download/use, retry, and feedback. The public path has no text profile, task
field, asset upload, or brand-kit setup. The collapsed owner-only explanation
lays out the five initial candidate JPEGs, their exact five parameter values,
Pass 1 gate/score results, and the persisted three-pass ranking, pairwise,
action, observation, and final-selection trail. Candidate JPEGs use
run-scoped authenticated no-store endpoints and the same client-side MIME,
SHA-256, and ETag verification as the final Result. Deeper debug remains
bounded to IDs, versions, scores, gates, actions, digests, provider request
IDs, and lineage; neither view exposes chain-of-thought, credentials, raw
base64, or unrestricted source contents.
