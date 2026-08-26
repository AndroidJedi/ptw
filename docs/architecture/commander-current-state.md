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
- 26 focused independent-platform tests and disposable platform migration journey;
- Validation, Owner Gateway, and Commander built-image suites;
- Owner Console unit tests and production build;
- Commander demo and `git diff --check` at intermediate checkpoints.

## Next release action

Complete the final built-image/browser/regression pass, commit both unrelated
histories, build matching release archives, deploy the enforcing platform
worker and API, run capability/multimodal canaries, then invoke the irreversible
application reset with exact confirmation `RESET PTW PRODUCTION`. Production
has not yet been reset in this milestone.
