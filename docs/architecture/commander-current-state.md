# Commander current state

Updated: 2026-08-26
Branch: `codex/web-only-commander`

## Current milestone

PTW has been rebuilt as a clean first-version Product Brief → Result system.
The old five-Ad batch, Ads workspace, Studio Wizard/editor, automatic nested
validator, Landing, Admin jobs, root broker, Positioning, idea-generation, and
their tables, routes, services, skills, tests, and assets are removed.

The database now has one baseline migration,
`db/migrations/001_ptw_result_v1.sql`. It contains only shared graph/source/
feedback/control authority, Projects and Product Briefs, approved Project
assets and brand kits, static recipe/render authority, provider provenance, and
the Result lifecycle. A schema verifier applies the baseline twice and rejects
any retired table family.

Result v1 implements:

- deterministic `ContextBundleV1` selection from the approved Brief, task,
  brand kit, approved Project sources, five template versions, selected writing
  references, and skill digests;
- exactly five isolated initial `CandidateV2` generations;
- at most four improvement generations and exactly three critic passes;
- stable server-reserved UUIDv7 candidate, critic-pass, action, element,
  recipe, render, and Result identities;
- exact element reuse plus `supersedes` and multi-source `derived_from`
  lineage;
- `marketing_copy_v1` and `instagram_static_ad_v1` adapters;
- strict static `StudioRecipeV2` validation and deterministic 1080×1080 JPEG
  rendering for the Instagram adapter;
- fail-closed hard gates, scoring, pairwise comparison, and one immutable final
  Result Creative;
- owner status/result/debug/retry/feedback APIs and a Product Brief + Result
  Owner Console.

The independent platform worktree now advertises only four JSON modes and one
reviewed non-human graphic mode. It validates one-to-five digest-mapped JPEG
critic attachments, rejects image generation in JSON modes, uses fresh
ephemeral calls, deduplicates per-attempt idempotency keys, and serves generated
PNG bytes through an authenticated digest-checked endpoint. Its database is
upgraded additively and preserved.

## Verification completed locally

- clean baseline/idempotent PostgreSQL migration verifier;
- full disposable PostgreSQL Result lifecycle: five initial candidates, four
  improvements, three passes, one Result, and append-only feedback lineage;
- content corpus and PTW skill verification;
- 27 focused independent-platform tests and disposable platform migration journey;
- Validation, Owner Gateway, and Commander built-image suites;
- Owner Console unit tests, production build, and Playwright coverage on desktop,
  360 px Chromium, and iPhone WebKit;
- Commander demo and `git diff --check` at intermediate checkpoints.

## Production deployment

Result v1 was deployed on 2026-08-26 as release
`result-v1-20260826-1345`. The application reset completed from commit
`02556ec4f90ba8c73802411c2dc4f5cbb8113090`; the independent Result bridge is
at `4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`.

The Product Brief scheduling and language-contract incident was repaired
in-place without a reset. Commander, Validation, and Owner Gateway now run
release `result-v1-20260826-1415-language-hotfix` from commit
`3b5691cd4791c7b1629a1b6ab8b2056da1960215`; the independent Result bridge
remains on its separately versioned healthy release. Production table counts
were preserved. The earliest Brief from the incident completed on retry as an
English schema-v1 document; its failed first attempt and completed second
attempt have distinct exact provider lineage. The four duplicate submissions
are preserved as failed, and the singleton operation guard is empty.

The production Commander database contains only `001_ptw_result_v1.sql`, and
no retired table family remains. The obsolete owner-control volume, Git
watcher, credential agent, Positioning, and idea containers are absent.
Structured/multimodal bridge, real Product Brief, Pexels, schema, dependency,
resource, public bundle, retired-route, CORS, and readiness canaries passed.
All three application services are healthy on the matching hotfix tag with zero
restarts; the independent API and worker are healthy on their matching bridge
tag, and the locked 24-hour resource follow-up timer remains active.
