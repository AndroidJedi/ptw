# Commander current state

Updated: 2026-09-02
Branch: `codex/web-only-commander`
Deployment: not authorized; local checkout only

## Current milestone

The Social posts/Result subsystem is removed. The Owner Console navigation now
contains Product Briefs and Universal Studio only. Result routes, view/review
components, candidate generation, asset pools, static-social adapters,
recipes/renders, review actions, learning snapshots/rules, exports,
notifications, provider media modes, tests, scripts, templates, corpus, and the
SKYNET experiment tree are deleted.

Production persistence now has one clean `001_ptw_brief_v1.sql` baseline for
Sources, Projects, Product Briefs, correction feedback/weights, attempts,
invocations, graph lineage, audit, and emergency control. Loopback Brief state
uses `.local/owner-briefs`; Studio remains standalone under
`.local/studio-workspace`.

The structured bridge contract is exactly `product_brief` and
`product_brief_revision`. Telegram remains `/help`, `/status`, and `/stop` only.

## Verification status

The local removal milestone is verified:

- Validation and standalone Studio: 61 tests passed.
- Owner Gateway: 4 tests passed.
- Commander: 8 tests passed in the rebuilt `ptw-commander-api:latest` image;
  the deterministic Brief lineage demo also passed.
- Owner Console: 28 unit tests, the TypeScript/Vite production build, build
  boundary verification, and 18 desktop/mobile/WebKit Playwright tests passed.
- The disposable PostgreSQL check produced the exact 14-table Brief schema and
  rejected the retired Result tables.
- Skill synchronization/validation, Python compilation, JSON validation, and
  `git diff --check` passed.
- `.local/owner-experiments` was removed after the one durable, non-provisional
  Product Brief and its source/project/approval lineage were migrated to
  `.local/owner-briefs`. The complete tracked and ignored `skynet/` tree is
  absent.

No production database, platform repository, provider, Telegram delivery,
Firebase release, or deployment was touched.

## Next work

Define the new streamlined post workflow as a separate milestone. Do not reuse
the retired Result schema, routes, or local data implicitly.
