# Idea Laval Engine

Status: Market Signals v2 and fresh-session audit implemented
Updated: 2026-08-19

## Purpose

Idea Laval turns an Owner Idea into an inspectable chain:

```text
Owner Idea
  -> localized search plan and raw SERPs
  -> country-ranked, globally deduplicated competitors
  -> website, YouTube, review, forum, and complaint evidence
  -> competitor dossiers
  -> Opportunity Matrix
  -> deterministic MarketSignalScore from persisted evidence
  -> bounded Synthesis Packet
  -> explicit transformation operators
  -> clustered variants
  -> deterministic + independent evaluation
  -> shortlist and finalists
```

This is the only supported Ideas subsystem. Legacy C01-C10 generations, seeded
idea rankings, generation controls, idea contexts, and idea-to-post batch
bridges are retired and must not be exposed or seeded. An empty Laval run list
means that the owner has not submitted an idea; fixtures may exercise providers
in tests but must never appear as owner-created production data.

PostgreSQL owns the run, stages, child items, artifacts, evidence, normalized
entities, approvals, overrides, costs, and lineage. JSON and Markdown exports
are derivatives generated from database state.

Every run has one durable pipeline version and evidence mode. `demo_fixture` is
an inspectable orchestration demo and must display `DEMO — NO LIVE RESEARCH`
everywhere. New live runs use `market_signals_v2` plus
`live_market_signals`; Google Trends is optional and its absence never blocks
synthesis or finalists. Historical `legacy-trends-v2`,
`live_search_pending_trends`, and `live_complete` rows remain readable and are
not rewritten. Provider names, score configuration, and spend cap are
snapshotted when the run is created.

## Stages and restart behavior

The canonical Market Signals v2 stages are `OWNER_CAPTURE`, `OWNER_DNA`, `QUERY_PLAN`,
`SERP_DISCOVERY`, `COMPETITOR_SELECTION`, `COMPETITOR_EVIDENCE`,
`COMPETITOR_DOSSIERS`, `OPPORTUNITY_MATRIX`, `MARKET_SIGNAL_PLAN`,
`MARKET_SIGNAL_COLLECTION`, `MARKET_SIGNAL_GATE`, `SYNTHESIS_PACKET`, `IDEA_EXPANSION`,
`IDEA_CLUSTERING`, `IDEA_EVALUATION`, and `FINAL_SHORTLIST`.

An eligible incomplete legacy run exposes **Resume with Market Signals** only
in the owner web console. That explicit action changes its three unstarted
ordinal 8-10 rows to the Market Signal stages and preserves paid task IDs,
recorded spend, evidence, lineage, and all earlier artifacts. It refuses
completed legacy Trends history and never starts automatically.

Every stage stores an input hash, status, attempt, provider/model, metrics,
bounded error, and current artifact. Country/query/competitor/signal operations
also have independent child states. A restart resumes `pending` or `running`
runs; a failed run remains visible until the owner resumes it. Reusing the same
input hash skips paid calls. Reruns mark every downstream stage stale before
new work begins.

Resume and rerun are deliberately different owner actions. Resume appends a
`laval_run_actions` audit row with the Firebase actor and continues from saved
stage/provider state. A submitted DataForSEO remote task is fetched by its
persisted ID and is never reposted or billed twice. Rerun invalidates the chosen
stage and its downstream artifacts for deliberate reconstruction. The status
API exposes the bounded error, attempt, failed time, provider-task counts,
recorded cost, exact resume semantics, and recent recovery history.

Manual mode pauses after competitor selection, the Opportunity Matrix, and the
final shortlist. Automatic mode skips those gates. Both modes can be paused at
safe item/stage boundaries. Platform emergency stop also pauses active Laval
runs; full resume remains web-only.

## Evidence and learning graph

`laval_evidence` retains source URI/title, retrieval time, source class,
country, claim/excerpt, confidence, provider metadata, and optional competitor.
Every opportunity, market/trend signal, idea, and evaluation keeps stable
evidence/parent IDs plus explicit `laval_lineage_edges`.

`MarketSignalScore` is code-owned and uses only persisted evidence IDs. Laval
stores the exact formula, `market-signal-v1` normalization version, weights,
six components, raw counters, per-component data status, score timestamp, and
deduplicated evidence IDs. Missing confirmed data contributes zero and is
separately displayed as `no_data`; there is no coverage multiplier. The exact
formula is:

```text
0.20 × cross_country_recurrence
+ 0.20 × query_family_recurrence
+ 0.15 × recent_content_activity
+ 0.15 × community_activity
+ 0.15 × negative_pain_recurrence
+ 0.15 × semantic_relevance
```

Only a real provider `published_at` value may contribute to the 365-day
counter; retrieval time is never substituted. Canonical duplicate URLs count
once. A fresh LLM invocation may only classify supplied
opportunity/evidence-ID pairs as relevant or not relevant. It never supplies a
numeric component or final score.

With live research configured, evidence is sent through Commander's internal
bridge, which calls `ResearchKnowledgeService` with the product research agent.
Finalists become proposed product-discovery Hypotheses derived from permanent
Source UUIDs. Fixture mode deliberately does not write demo evidence into the
Commander learning graph and is labelled `fixture` in artifacts and the UI.
Fixture records are also excluded when live and fixture providers are mixed.

## Providers

Business logic depends on `SearchProvider`, `WebPageProvider`, an optional `TrendProvider`,
the existing structured LLM provider, the PostgreSQL repository, and the
Commander research sink.

- `LAVAL_SEARCH_PROVIDER=fixture` is deterministic and makes no network calls.
- `LAVAL_SEARCH_PROVIDER=dataforseo` uses DataForSEO's Standard normal-priority
  task queue with explicit country/language/depth. Remote task IDs are persisted
  before polling so restart does not repost paid work. Polling allows up to one
  hour for queue outliers; a later Retry fetches the same paid task rather than
  posting it again. The internal reservation ceiling is USD 0.04 and the
  absolute per-run cap is USD 0.05.
- `LAVAL_TREND_PROVIDER=google_trends` remains an optional supplemental source;
  it is not required for Market Signals v2 completion.

Every Laval language stage uses a bounded context packet and a separate fresh
model invocation. The VPS bridge accepts explicit `laval_*` modes, passes the
caller's JSON Schema to `codex exec --output-schema`, supplies the prompt on
stdin, and runs `--ephemeral --sandbox read-only`. It never uses `resume` or a
dangerous sandbox bypass. `codex-cli-default` deliberately omits `--model`, so
ChatGPT-authenticated Codex selects its supported default instead of receiving
an API-only model name. `laval_llm_invocations` is append-only and records
context/schema hashes, prompt version, model, independent session IDs, and
`success`, `fallback`, or `failed`.

No Google Custom Search dependency exists. Provider failures are persisted per
item; the stage continues when remaining evidence is sufficient and applies a
partial status/confidence penalty.

DataForSEO credentials come from Dashboard -> API Access and are an API login
plus a separately generated API password. Configure them only through
`scripts/configure_laval_providers.sh` on the VPS; the script hides input,
validates against DataForSEO's free sandbox, writes the non-secret
`DATAFORSEO_VERIFIED=1` readiness marker, and updates only the root-owned
environment file. Google Trends remains a limited alpha; apply at
<https://developers.google.com/search/apis/trends>. Never use unofficial Trends
scraping as a production substitute.

## Web and CLI operation

The mobile-first Ideas view is the normal VPS interface. It creates runs with a
configurable country/language list, starts or pauses work, polls durable state,
shows all 16 stages, filters SERP/selection output by country, displays the
MarketSignalScore formula, components, raw counters, data status, and evidence
IDs, approves gates, reruns stages/countries, writes
audited overrides, and exports JSON or Markdown. New-run manual corrections
appear on Competitor Selection and Opportunity Matrix; historical legacy runs
retain their Trend Gate correction alias. The API returns the currently
selected/enabled rows so the owner chooses a human-readable competitor,
opportunity, or legacy trend row; the web UI supplies
the target UUID internally and requires a reason. The actor and reason are
appended to the audit log, and the affected downstream stages become stale for
deliberate reconstruction. All calls pass Firebase Auth, App Check, exact-owner
verification, and the Owner Gateway bridge.

Creating a run from the web is a one-click create-and-start flow. Automatic
progression through all 16 stages is the recommended default; checkpoint review
is a separate, explicit mode. A persisted historical `pending` run remains
recoverable but is labelled as not started. An eligible legacy Trends run shows
one continuation action only: it upgrades to Market Signals while preserving
paid work. Telegram status projections deep-link to that exact run rather than
opening whichever run the browser would otherwise select.

Failed runs show an in-page recovery report and a distinct **Resume saved
work** action. On the 1 GB production profile, automatic and owner-triggered
Telegram status notifications are retired. The notifier is not constructed,
the web action is hidden, and cached notification calls receive HTTP 410;
historical outbox rows remain preserved.

The same services are available through the `lav` CLI inside the Idea service:

```sh
lav idea new --text "OWNER IDEA"
lav run RUN_UUID --through COMPETITOR_SELECTION
lav status RUN_UUID --watch
lav show RUN_UUID MARKET_SIGNAL_GATE --view scores --json
lav resume-market-signals RUN_UUID
lav approve RUN_UUID COMPETITOR_SELECTION
lav rerun RUN_UUID SERP_DISCOVERY --country DE
lav competitor reject RUN_UUID --competitor UUID --reason "not a product"
lav opportunity disable RUN_UUID UUID
lav trend disable RUN_UUID UUID
lav export RUN_UUID --stage FINAL_SHORTLIST --format md
lav cost RUN_UUID --json
```

## Production acceptance

Before calling live research ready, configure providers, migrate the shared Idea
database, rebuild the Idea API/Commander API/Owner Gateway/Web images, and run:

1. exact-owner login and negative authentication checks;
2. one manual run through all three gates and one automatic run;
3. five-country top-three inspection and a Germany-only rerun;
4. raw Market Signal components, counters, data status, and evidence IDs;
5. one competitor rejection and one opportunity disable;
6. process restart during SERP and Market Signal work;
7. Source -> proposed Hypothesis graph persistence for finalists;
8. JSON/Markdown export and user-facing provider failure behavior;
9. emergency stop and web-only resume;
10. completion without Google Trends and no repeated paid task submission.

Fixture acceptance proves orchestration, persistence, UI, and lineage but is not
evidence that a live external provider is ready.
