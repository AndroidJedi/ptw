# Commander current state

Updated: 2026-08-26
Branch: `codex/web-only-commander`

## Current milestone

PTW has been rebuilt as a clean first-version Product Brief → one-click Natal
Instagram post system.
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

- deterministic `ContextBundleV1` selection from the approved Brief, fixed
  server-owned Instagram task, canonical Natal brand kit, approved Project
  sources, five template versions, selected writing references, and skill
  digests;
- exactly five isolated initial `CandidateV2` generations;
- at most four improvement generations and exactly three critic passes;
- stable server-reserved UUIDv7 candidate, critic-pass, action, element,
  recipe, render, and Result identities;
- exact element reuse plus `supersedes` and multi-source `derived_from`
  lineage;
- internal generic `marketing_copy_v1` and `instagram_static_ad_v1` adapters,
  with only Instagram exposed through Owner Gateway;
- strict static `StudioRecipeV2` validation and deterministic 1080×1080 JPEG
  rendering for the Instagram adapter;
- fail-closed hard gates, scoring, pairwise comparison, and one immutable final
  Result Creative;
- owner status/result/debug/retry/feedback APIs and a Product Brief + one-click
  Instagram post Owner Console. Validation automatically provisions the
  digest-pinned Natal logo, palette, and Inter font; public asset and brand-kit
  setup routes are absent.

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

The current Natal one-click repair passes the clean/idempotent schema verifier,
the disposable PostgreSQL lifecycle, Validation and Owner Gateway built-image
tests, a built-image 1080×1080 Natal logo/Inter render, canonical skill/corpus
verification, Owner Console unit/build checks, Playwright on desktop, 360 px
Chromium, and iPhone WebKit, Commander tests/demo, and `git diff --check`.

## Production deployment

Result v1 was deployed on 2026-08-26 as release
`result-v1-20260826-1345`. The application reset completed from commit
`02556ec4f90ba8c73802411c2dc4f5cbb8113090`; the independent Result bridge is
at `4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`.

The Product Brief scheduling and language-contract incident was repaired
in-place without a reset. Commander, Validation, and Owner Gateway then ran
release `result-v1-20260826-1415-language-hotfix` from commit
`3b5691cd4791c7b1629a1b6ab8b2056da1960215`; the independent Result bridge
remains on its separately versioned healthy release. Production table counts
were preserved. The earliest Brief from the incident completed on retry as an
English schema-v1 document; its failed first attempt and completed second
attempt have distinct exact provider lineage. The four duplicate submissions
are preserved as failed, and the singleton operation guard is empty.

The Result brand-kit prerequisite flow was deployed as
`result-v1-20260826-1450-brand-kit-hotfix` from commit
`64083f8183e6572dffe092ccec63c64d900e23ff` through the owner-confirmed clean
reset. Six Projects and six Briefs were removed as authorized; all
Commander-owned business tables were empty afterward and independent platform
counts were unchanged. The empty-logo UUID failure is fixed, required brand
setup precedes Result creation, all five services use the matching versioned
tag, Firebase Hosting serves `App-DiuEpJxy.js`, and live Auth/App Check/CORS,
provider, dependency, Telegram, schema, and resource audits passed.

Immediate owner verification found two follow-up UI defects: EN/УКР changed
only its own label, and new-Project creation was stacked above the selected
Project workspace. The repairs were deployed as
`result-v1-20260826-1505-owner-ui-hotfix` from commit
`9535a749b96bb265d2c07f5d22876fbac351b155` through a second owner-confirmed
clean reset. One Project and one Brief were removed as authorized; all
Commander-owned business rows were zero afterward and independent platform
counts were unchanged across the reset. The complete visible console now
switches between English and Ukrainian with reload persistence, and new versus
existing Project workflows render as separate modes. Unit, build, desktop,
360 px Chromium, and iPhone WebKit checks pass. Firebase Hosting serves
`App-Dinvy60U.js`; its live bytes contain the language-storage marker and both
new-Project language variants. The live gateway, unauthenticated rejection,
CORS, service-worker, provider, Pexels, dependency, skill, Telegram, schema,
and resource audits passed.

The production Commander database contains only `001_ptw_result_v1.sql`, and
no retired table family remains. The obsolete owner-control volume, Git
watcher, credential agent, Positioning, and idea containers are absent.
Structured/multimodal bridge, real Product Brief, Pexels, schema, dependency,
resource, public bundle, retired-route, CORS, and readiness canaries passed.
All three application services are healthy on the matching owner-UI hotfix
tag; the independent API and worker are healthy on the same release tag at
bridge revision `4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`, and the locked
24-hour resource follow-up timer remains active.

The one-click Natal repair is not yet deployed. Read-only production inspection
still shows application commit `9535a749b96bb265d2c07f5d22876fbac351b155`
and release `result-v1-20260826-1505-owner-ui-hotfix`, with one Project, one
Brief, one prior brand kit, and no Result runs or Results. The canonical release
path remains reset-gated; do not delete that owner state without the exact
`RESET PTW PRODUCTION` confirmation.
