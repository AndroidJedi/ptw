# Idea Laval Engine

Status: mechanism/thesis V2 implemented locally; production cutover pending
Updated: 2026-08-20

## Purpose

Idea Laval V2 separates research from validation:

```text
Owner Idea
  -> official search + website + official YouTube observations
  -> opportunities + deterministic MarketSignalScore
  -> 24 operator-balanced candidate variants
  -> 6-20 reusable mechanisms from every variant
  -> 1-3 complete product theses
  -> strict evidence-cited falsification
  -> owner selects one survivor
  -> durable manual validation workspace
  -> Observation -> Insight -> Continue / Mutate / Pivot / Reject
```

Candidate variants are intermediate material. V2 publishes surviving product
theses, not ranked variants, to Commander. No scalar probability of success is
computed or displayed.

Each run has an immutable `pipeline_version`. New runs use
`mechanism_thesis_v1`. Historical `market_signals_v2` and
`legacy-trends-v2` rows retain their topology, artifacts, rerun behavior,
exports, and graph links. A clean production reset may remove runtime data, but
the code contract remains version-aware.

## Research stages

The 22 V2 stages are:

```text
OWNER_CAPTURE, OWNER_DNA, QUERY_PLAN,
SERP_DISCOVERY, COMPETITOR_SELECTION, COMPETITOR_EVIDENCE,
YOUTUBE_DISCOVERY, YOUTUBE_OBSERVATION,
COMPETITOR_DOSSIERS, OPPORTUNITY_MATRIX,
MARKET_SIGNAL_PLAN, MARKET_SIGNAL_COLLECTION, MARKET_SIGNAL_GATE,
SYNTHESIS_PACKET,
IDEA_EXPANSION, IDEA_CLUSTERING, IDEA_EVALUATION,
MECHANISM_EXTRACTION, MECHANISM_SCORING,
THESIS_SYNTHESIS, THESIS_FALSIFICATION, THESIS_SHORTLIST
```

Every stage persists input hash, status, attempt, provider/model, metrics,
bounded error, and artifact. Remote paid task IDs are restart-safe. Rerunning
an evidence stage invalidates downstream opportunities, mechanisms, theses, and
falsification. A selected validation workspace is never rewritten; its source
thesis is flagged stale when newer research supersedes it.

Manual mode pauses at configured gates; automatic mode traverses all 22 stages.
Platform emergency stop and owner pause remain safe-boundary controls.

## YouTube observation contract

Live V2 requires a configured and canary-verified `YOUTUBE_API_KEY`. Only the
official YouTube Data API is used: `search.list`, `videos.list`, and bounded
top-level `commentThreads.list`. Region and language targeting are explicit.
Caption scraping is forbidden; official public transcript retrieval is not a
completion dependency because caption access requires authorization.

An owner may submit bounded transcript text manually. It is persisted as a
permanent `manual` Source, explicitly labelled owner-supplied and unverified,
then included in the observation context. Missing manual or official captions
never fail a run.

Behavior observations use one of: workaround, challenge format, motivation,
repeated question, complaint, transformation narrative, audience vocabulary,
creator distribution, or substitute. Every observation cites supplied video
and evidence IDs. Independent confirmation counts unique creator channels;
duplicate or viral videos from one channel add one creator confirmation.
Comment-author identity is discarded.

Video/channel remote IDs are cached. Count snapshots are append-only with an
observation timestamp. Velocity is `insufficient_history` for one snapshot and
becomes a measured count delta after the second; retrieval time is never used
as publication time. Provider calls and estimated quota units are appended to
the cost/audit ledger even when monetary cost is zero.

## Mechanisms and theses

Mechanism extraction receives all 24 variants, including lower-ranked rows,
and must return 6-20 mechanisms covering every variant. A mechanism stores
localized name/description, one typed class (`value`, `behavior`, `trust`,
`retention`, `distribution`, or `proof`), source variants, opportunities,
market signals, behavioral observations, evidence, and independent publisher
support.

Support is a code-owned vector, never one aggregate probability:

- source diversity;
- cross-variant recurrence;
- opportunity support;
- market-signal support;
- owner-DNA fit.

Each of at most three theses contains target user, problem, 3-7 mechanisms, a
5-8 step acquisition-to-return/distribution loop, value moment, zero-audience
behavior, substitutes, dangerous assumptions, and a falsifiable success
criterion.

Falsification runs in a fresh strict-schema session, retries once in another
fresh session, and has no live fallback. Objections and counterarguments must
cite exact supplied evidence and mechanism IDs. Verdicts are `survives`,
`weak`, and `rejected`. Recommendation among survivors is lexicographic: no
fatal objection, fewest unsupported high-severity assumptions, strongest
weakest-mechanism coverage, then smallest mechanism count. If none survives,
the run completes as `no_surviving_thesis` and publishes nothing.

## Commander graph and validation

Live research enters Commander through the authenticated typed research bridge:

```text
Source <- derived_from - ProductMechanism
Source <- derived_from - Hypothesis(ProductThesis)
Hypothesis - contains -> ProductMechanism
ValidationWorkspace - contains -> Experiment(MarketProbe)
ValidationWorkspace - contains -> Observation -> Insight -> Decision
```

Fixture evidence is visibly non-live and is never published to Commander.
Selecting a surviving thesis resolves all UUIDs server-side and idempotently
creates exactly one `validation_workspace` plus three editable proposed probes.
Editing creates a superseding proposal so the original plan remains append-only.

Supported manual probe types are `landing_page`, `fake_door`, `outreach`,
`mock_flow`, `creator_feedback`, `community_test`, and `concierge`. Every probe
predeclares procedure, segment, metric and threshold, sample target, duration,
optional budget, and evidence-capture instructions. PTW never publishes a page,
contacts a person, spends money, or starts external execution. Explicit owner
start only records that the owner began the probe manually.

Completion stores aggregate metrics, sample size, timeframe, bounded factual
notes, limitations, and an optional artifact URL as Source/MetricSet and
Observation. Interpretation is a separate supporting or contradicting Insight.
Secrets and personal contact data are rejected.

Decisions are append-only:

- `continue` requires an evaluated probe and enables a Plan job;
- `mutate` requires an explicit subset of current mechanisms and creates a
  superseding thesis revision;
- `pivot` requires a materially different 5-8 step loop and creates a linked
  thesis;
- `reject` closes the thesis with owner rationale.

Later decisions supersede earlier decisions. Plan context is injected from the
selected hypothesis, Sources, mechanisms, probes, observations, and insights;
Commander appends `RESEARCH_CONTEXT_CONSUMED`. The owner never copies UUIDs.

## Owner APIs and UI

The Owner Gateway exposes the bounded thesis, selection, validation, probe,
decision, and Plan routes under `/api/v1`. It also accepts optional manual
transcript Sources at
`POST /api/v1/laval/runs/{run_id}/youtube-transcripts`.

Ideas has `Дослідження` and `Валідація` subviews. Research groups technical
stages into five readable phases. Thesis cards show the complete loop,
mechanisms, support diversity, dangerous assumptions, falsification verdict,
and recommendation reason. Only survivors expose `Вибрати для валідації`.
Ukrainian is the default display language; English source fields and raw JSON
remain under progressive disclosure.

## Provider setup and acceptance

Fixture mode remains a deterministic orchestration demo. Live mode requires
verified DataForSEO and official YouTube credentials; Google Trends is optional.
Run `scripts/configure_laval_providers.sh` only as root on the VPS. It hides both
credentials, validates DataForSEO and a YouTube `videos.list` canary, and writes
readiness markers only to the root-owned environment file.
If DataForSEO is already configured, pass `--youtube-only` to validate and
replace only the YouTube key and its readiness marker.

Before production cutover, run the Commander suites, disposable PostgreSQL V2
pipeline tests, built-image tests, web Vitest/build/Playwright checks, demo
generation, skill verification, and `git diff --check`. On the 1 GB VPS, apply
the established maintenance lock and recreate one service at a time. The
irreversible clean reset remains confirmation-gated through
`scripts/reset_ptw.sh`; never infer its target or run it without owner approval.
