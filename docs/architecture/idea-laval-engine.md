# Idea Laval Engine

Status: implemented locally; production provider/deployment acceptance pending  
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

It extends Idea Evolution; it is not a separate product or source of truth.
PostgreSQL owns the run, stages, child items, artifacts, evidence, normalized
entities, approvals, overrides, costs, and lineage. JSON and Markdown exports
are derivatives generated from database state.

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
- `LAVAL_SEARCH_PROVIDER=dataforseo` uses localized Google organic SERPs with
  explicit country/language/depth. Credentials remain outside Git.
- `LAVAL_TREND_PROVIDER=fixture` supplies deterministic recorded-style results.
- `LAVAL_TREND_PROVIDER=google_trends` requires an owner-provided bridge URL for
  the restricted Google Trends alpha/API account. The bridge contract returns
  normalized dimensions plus related/rising/breakout discoveries.

No Google Custom Search dependency exists. Provider failures are persisted per
item; the stage continues when remaining evidence is sufficient and applies a
partial status/confidence penalty.

## Web and CLI operation

The mobile-first Ideas view is the normal VPS interface. It creates runs with a
configurable country/language list, starts or pauses work, polls durable state,
shows all 16 stages, filters SERP/selection output by country, separates Trend
Scores from Trend Discoveries, approves gates, reruns stages/countries, writes
audited overrides, and exports JSON or Markdown. All calls pass Firebase Auth,
App Check, exact-owner verification, and the Owner Gateway bridge.

The same services are available inside the Idea Evolution image:

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
