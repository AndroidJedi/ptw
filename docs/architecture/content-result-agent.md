# PTW five-template Result architecture

## Flow

```text
approved Product Brief + server-mapped social task + canonical Natal brand/assets
  -> bounded ContextBundleV1
  -> five isolated versioned strategies
  -> validated CandidateV2 documents and previews
  -> three Result/Critic passes
  -> one immutable Result Creative
```

`ContentContextAssembler` selects one technique guide, one strategy, its exact
digest-locked Studio component snapshot, and four to six deterministic corpus
excerpts without truncation. The writing bundle is bounded near 5,500 tokens
and total system context near 8,000 tokens excluding structured payload/tool
data. Selection order and every digest are persisted.

`CandidateGenerationOrchestrator` reserves all stable IDs before side effects,
loads exactly five active template versions, and invokes them independently at
maximum JSON concurrency two. Initial failure after one fresh structured retry
fails the run. At most four improvement calls occur across critic Passes 1–2.
The global run deadline is 45 minutes.

The active strategies are `moment_tension@3`, `contrast_reframe@3`,
`mechanism_proof@3`, `human_story@3`, and `direct_offer@3`. Each is digest-bound
at startup to one matching Git-owned `ptw.studio.template.v1` component tree;
missing, extra, version-skewed, or digest-skewed active definitions stop startup.
Five integer sliders
retain exact 0–100 values and template-specific envelopes. Critic deltas are
multiples of five, change at most two dimensions, and change a chosen dimension
by at least ten.

The Instagram square and TikTok vertical-photo adapters, not the generic
orchestrator, resolve each slider into an ordered typed component patch. Only
numeric interpolation, enumerated steps,
and bounded optional-component thresholds are accepted. Geometry is quantized
to 0.001 and typography to declared integer steps. The patch cannot change
component identity, tool IDs, protected copy, source assets, palette bindings,
or any path absent from the component catalog.

`ResultCriticAgent` receives anonymized candidates, exact element IDs,
parameters, previous pass summaries, anonymous resolved frame contracts, and
exact mapped renders. Pass 1 explores
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

## Local Universal experiment profile

The loopback-only `universal_ad_experiment_v1` profile reuses the same five
strategy documents and three-pass critic contracts through a separate versioned
adapter. It captures one saved `universal_ad` export, resolves the declared
strategy slider patches server-side, and sources exactly three fresh, distinct
Pexels photographs for three differently treated image-backed directions. One
deterministic Studio texture and one solid direct-offer direction complete the
set. Adapter v8 owns a different palette, typography hierarchy, CTA treatment,
composition, and optional-role state for every strategy. The contrast direction
uses a separately sourced ultra-realistic Pexels object, deterministically
isolated as a sticker and selected to match the background's lighting, palette,
material, grain, perspective, and surface treatment. Provider/photo/license,
query, transformation, and run provenance are retained. Missing Pexels
configuration or unusable provider results fail before candidate generation;
there is no generated, procedural, bundled, or repeated image fallback. Each
candidate is generated in isolation through
`content-candidate-generator`. The adapter renders an authoritative
1080×1080 PNG plus a deterministic full-size JPEG, runs deterministic geometry
and protected-copy gates at full resolution, and persists a second deterministic
480×480 analysis JPEG for critic transport. The analysis derivative is scaled
by exactly 4/9 from the PNG, is digest-bound to both authoritative artifacts,
and has approximately five times fewer pixels. Only those exact persisted
analysis bytes enter critic calls. The local profile independently screens the
first three and remaining two initial candidates, then compares only both group
winners with both structured summaries. Exact attachment counts are `[3, 2,
2]`; screening actions and local improvement generations are disabled. Before
the critic can run, a set-level audit requires five distinct setting signatures
and background colors, image and sticker presence, multiple background modes,
four font families and CTA treatments, and minimum pairwise setting and decoded-
pixel distances. Owner-approved layout patches are scoped to the strategy that
produced them; legacy unscoped patches remain textual evidence and cannot
collapse all five strategies into one recipe.

Local authority is file-backed and append-only below
`.local/owner-experiments`; it is independent of PostgreSQL and production
Result state. Every run binds the approved Brief digest, saved Studio-state
digest, strategy/template versions, asset provenance, candidate/render digests,
critic/action trace, and exact owner-approved lesson snapshot. Ready creates an
immutable Instagram-ready download package but performs no platform call.
Improve creates a child from the selected candidate's immutable configuration
and assets plus only the owner instruction. No TikTok adapter, publishing,
analytics, market evidence, or automatic learning is enabled for this profile.
While a local run is queued or generating, the owner may terminate it through
one loopback-only action. The service sets a run-scoped cancellation event,
terminates the exact Codex process group, appends a `terminated` checkpoint and
run revision, and never converts that owner decision into a failed or completed
state. Generated candidates remain inspectable evidence; retry creates a child
run. Production lifecycle routes and states are unchanged.

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

Every configured static-social recipe carries one
`studio.layout.template_application.v1` modifier: the immutable template
snapshot, strategy/Studio/catalog/renderer versions and digests, exact and
normalized sliders, component-key-to-UUID map, protected typed bindings,
ordered before/after patch, and optional parent recipe/base digest. Improved
candidates point `parent_recipe_id` at the direct base recipe and add a
`derived_from` edge. The render manifest stores the complete resolved recipe,
source/output digests, and the same production identities. Replaying the stored
snapshot, bindings, sliders, and reserved IDs must reproduce the canonical
recipe digest and decoded pixels.

The owner normally sees a searchable Project/artifact navigator, one approved
Brief selector, Instagram/TikTok choice, three progress stages, one native post
preview, Ready/Improve, retry, and export. The public path has no text profile,
task field, asset upload, or brand-kit setup. Ready and Improve append immutable
feedback/WeightUpdate/outcome entities. Improve transactionally creates a child
run whose ContextBundle contains only the selected versioned revision
instruction and exact feedback UUID; unrelated owner history stays excluded.
The collapsed owner-only explanation
lays out the five initial candidate JPEGs, their exact five parameter values,
Pass 1 gate/score results, and the persisted three-pass ranking, pairwise,
action, observation, and final-selection trail. Candidate JPEGs use
run-scoped authenticated no-store endpoints and the same client-side MIME,
SHA-256, and ETag verification as the final Result. Deeper debug remains
bounded to IDs, versions, scores, gates, actions, digests, provider request
IDs, and lineage; neither view exposes chain-of-thought, credentials, raw
base64, or unrestricted source contents.
