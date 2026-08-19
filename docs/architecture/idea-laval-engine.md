# Idea Laval Engine

Status: evidence modes and five-cent live-search guard implemented
Updated: 2026-08-18

## Purpose

Idea Laval turns an Owner Idea into an inspectable chain:

```text
Owner Idea
  -> localized search plan and raw SERPs
  -> country-ranked, globally deduplicated competitors
  -> website, YouTube, review, forum, and complaint evidence
  -> competitor dossiers
  -> Opportunity Matrix
  -> Google Trends research
       -> Trend Scores
       -> Trend Discoveries
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

Every run has one durable evidence mode. `demo_fixture` is an inspectable
orchestration demo and must display `DEMO — NO LIVE RESEARCH` everywhere.
`live_search_pending_trends` uses real search evidence but pauses after the
Opportunity Matrix. Only `live_complete` may proceed through Google Trends,
synthesis, evaluation, and a final shortlist. Provider names and the spend cap
are snapshotted when the run is created.

## Stages and restart behavior

The canonical stages are `OWNER_CAPTURE`, `OWNER_DNA`, `QUERY_PLAN`,
`SERP_DISCOVERY`, `COMPETITOR_SELECTION`, `COMPETITOR_EVIDENCE`,
`COMPETITOR_DOSSIERS`, `OPPORTUNITY_MATRIX`, `TREND_QUERY_PLAN`,
`GOOGLE_TRENDS_RESEARCH`, `TREND_GATE`, `SYNTHESIS_PACKET`, `IDEA_EXPANSION`,
`IDEA_CLUSTERING`, `IDEA_EVALUATION`, and `FINAL_SHORTLIST`.

Every stage stores an input hash, status, attempt, provider/model, metrics,
bounded error, and current artifact. Country/query/competitor/trend operations
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
Every opportunity, trend signal/discovery, idea, and evaluation keeps stable
evidence/parent IDs plus explicit `laval_lineage_edges`.

With live research configured, evidence is sent through Commander's internal
bridge, which calls `ResearchKnowledgeService` with the product research agent.
Finalists become proposed product-discovery Hypotheses derived from permanent
Source UUIDs. Fixture mode deliberately does not write demo evidence into the
Commander learning graph and is labelled `fixture` in artifacts and the UI.
Fixture records are also excluded when live and fixture providers are mixed.

## Providers

Business logic depends on `SearchProvider`, `WebPageProvider`, `TrendProvider`,
the existing structured LLM provider, the PostgreSQL repository, and the
Commander research sink.

- `LAVAL_SEARCH_PROVIDER=fixture` is deterministic and makes no network calls.
- `LAVAL_SEARCH_PROVIDER=dataforseo` uses DataForSEO's Standard normal-priority
  task queue with explicit country/language/depth. Remote task IDs are persisted
  before polling so restart does not repost paid work. Polling allows up to one
  hour for queue outliers; a later Retry fetches the same paid task rather than
  posting it again. The internal reservation ceiling is USD 0.04 and the
  absolute per-run cap is USD 0.05.
- `LAVAL_TREND_PROVIDER=fixture` supplies deterministic recorded-style results.
- `LAVAL_TREND_PROVIDER=google_trends` requires an owner-provided bridge URL for
  the restricted Google Trends alpha/API account. The bridge contract returns
  normalized dimensions plus related/rising/breakout discoveries.

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
shows all 16 stages, filters SERP/selection output by country, separates Trend
Scores from Trend Discoveries, approves gates, reruns stages/countries, writes
audited overrides, and exports JSON or Markdown. Manual corrections appear only
on Competitor Selection, Opportunity Matrix, and Trend Gate. The API returns
the currently selected/enabled rows so the owner chooses a human-readable
competitor, opportunity, trend score, or trend discovery; the web UI supplies
the target UUID internally and requires a reason. The actor and reason are
appended to the audit log, and the affected downstream stages become stale for
deliberate reconstruction. All calls pass Firebase Auth, App Check, exact-owner
verification, and the Owner Gateway bridge.

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
lav show RUN_UUID TREND_GATE --view discoveries --json
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
4. raw trend, Trend Score, and Trend Discovery inspection;
5. one competitor rejection and one opportunity/trend disable;
6. process restart during SERP and trend work;
7. Source -> proposed Hypothesis graph persistence for finalists;
8. JSON/Markdown export and user-facing provider failure behavior;
9. emergency stop and web-only resume.

Fixture acceptance proves orchestration, persistence, UI, and lineage but is not
evidence that a live external provider is ready.
