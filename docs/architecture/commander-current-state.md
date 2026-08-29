# Commander current state

Updated: 2026-08-29
Branch: `codex/web-only-commander`

## Current milestone

The Universal Ad Studio refactor is complete locally and is not deployed. The
Owner Console's third `Studio` destination now exposes one fixed
`universal_ad` structure rather than an arbitrary primitive-tree or
reference-calibration workflow. Its stable semantic roles are background,
optional sticker, hero title, supporting text, optional bullets, CTA, and
optional logo. The screen contains compact semantic-content, mood, typography,
spacing, CTA, optional-element, asset, Pexels, preview, and immutable-version
controls. A prominent seven-card component dock keeps the four required roles
and all three optional roles visible at a glance; optional cards are direct
keyboard-accessible switches, while detailed background, hierarchy, CTA,
sticker, and logo inspectors stay collapsed until needed. The current creative
remains the dominant sticky panel. There is no template selector/import, layer
tree, arbitrary property inspector, reference upload, pixel matching, or
calibration history.

Every bounded content edit and component/configuration toggle now requests a
debounced draft render and replaces the preview without persisting editor state.
The draft preview is bound to the current state digest, normalized by the same
strict configuration/content contract as a save, and ignored if a newer edit is
already in flight. Explicit Save setup remains the only way to advance current
workspace state. Optional Sticker and Logo switches are disabled with an upload
instruction when their fixed asset slot is unavailable, avoiding a knowingly
broken preview. Render progress, unsaved-preview success, and preview failures
are visible directly above the creative instead of only in the page-level
status line.

The loopback Studio now also exposes a local-only Test generation wizard in
explicit Tune mode. The owner supplies a project idea, desired implementation,
and optional feedback for each iteration. A non-interactive Codex run works in
a disposable mirror of the current dirty checkout and may revise only the
Universal Studio renderer/configuration surface, focused tests, styles, and
Studio UI components (including the wizard UI). Out-of-scope writes and file
deletions fail closed. Focused Python/web tests, the Owner Console production
build, and whitespace validation must pass before optimistic, atomic copy-back.
The Tune runner, launcher, authentication, production routes, Result adapter,
database, deployment, and publication boundaries are not writable by the
agent. Production does not mount Tune routes.

Successful Tune iterations now retain the exact 1080×1080 PNG rendered from the
verified isolated snapshot. The completion card shows that creative beside the
agent report through an authenticated run-scoped, SHA-256/ETag-verified,
private-no-store endpoint. Older completed runs are rendered from their retained
snapshots on first inspection, so the first investment-service experiment is
visible without rerunning it or accepting a stale in-memory Studio preview.
The review screen now keeps the creative and next-iteration feedback field
together at the top, retains the original idea and implementation across
reloads, and exposes explicit Back to Studio and new-direction actions. A
completed run reviews its exact run-scoped PNG; a safely stopped run reviews the
current Studio PNG instead. Raw runner tracebacks remain in the durable run
record but are never rendered in the owner interface. The Studio command bar
names Feedback & iterations directly, so closing the dialog does not hide the
return path.

The same review panel now has an explicit Save as reusable rule action. It
promotes the current feedback, falling back to the feedback that produced a
completed iteration when the next-feedback field is empty, into the canonical Studio Tune skill's
owner-approved rules reference, links its content digest to the originating run,
and deduplicates equivalent approvals. Every later Tune snapshot reads those
rules and must preserve observable rules with regression coverage. Ordinary
feedback still cannot rewrite agent instructions: this mutation is available
only through the authenticated loopback owner action and remains absent from
production.

The canonical `studio-tune-local` skill now makes verified local-checkout
application the default for owner Studio tuning requests. It explicitly
withholds commit, push, pull-request, remote, production, publication, and
deployment actions unless the owner names that non-local target.

Universal Studio text now aligns by actual rendered glyph ink and fits against
both ink height and nominal line spacing. The investment creative's three-line
hero begins at its configured top coordinate, no longer touches the clipped
bottom edge, and retains a measured positive gap before the supporting copy.
Resolved text nodes expose fitted size, rendered/source line counts, truncation,
and overflow so layout failures are inspectable. Focused tests lock the top
alignment, unclipped title edge, and semantic-block separation.

The new canonical `studio-ui-visual-audit` skill separates raw creative defects
from browser-preview defects and supplies a deterministic default,
high-density, and centered/minimal geometry gate. `studio-tune-local` requires
that audit for typography, positioning, spacing, component-layout, preview, and
Studio CSS changes. Its canonical desktop link is installed. This repair is
local only and was not deployed.

`ptw.studio.universal-ad-config.v1` is the reusable strict configuration.
Unknown structure fails closed, and all numeric/enum controls are bounded to
properties with meaningful visual impact. Solid, deterministic paper/grain
texture, and photo backgrounds share full/partial placement, fit, focal point,
and readability-overlay controls. The one sticker consists of an isolated
object with a smooth white die-cut contour sized from the actual fitted alpha
silhouette, reserved transparent edge room, and a subtle outside shadow. It has
bounded position, rotation, width, and object scale, with no rectangular paper
backing or blurred white glow. This render contract is the local internal
Universal Studio template version 3. Bullets, sticker, and logo can be omitted
without changing
the semantic structure or breaking the composition.

The loopback launcher now runs the complete visible Owner app rather than a UI
whose non-Studio destinations point at absent routes. Product Briefs and
Instagram post use one explicitly labeled deterministic local demonstration
journey with five distinct candidate JPEGs; provider-backed generation and
correction remain disabled. Studio is the writable local workspace. All local
routes keep the same fake-owner header boundary, bind only to `127.0.0.1`, and
do not contact production, mutate PostgreSQL, or publish.

The existing primitive system and `StudioRenderer.render_preview()` remain
internal implementation machinery for deterministic PNG rendering, fonts,
image fit, alpha, transforms, z-order, clipping, and visible measurements. The
two generic primitive fixtures remain engineering benchmarks only and are not
runtime templates. The historical production `StudioRecipeV2` JPEG path,
five active Result strategy snapshots, and byte-exact replay remain unchanged.

`UniversalStudioWorkspace` owns one current configuration, semantic content,
three fixed asset slots (`background_image`, `sticker_object`, and `logo`),
provider provenance, exact state digests, previews, and append-only immutable
versions under `STUDIO_WORKSPACE_PATH`. Background and sticker sourcing reuse
the existing bounded Pexels client. Sticker photos pass through one
deterministic edge-color soft-alpha cutout; complex sources must use an
owner-supplied transparent PNG/WebP. Approval stores the exact PNG,
configuration, content, asset provenance/digests, internal template snapshot
and digest, and render digest. Preview rendering accepts either the persisted
state digest alone or that digest plus a complete draft configuration/content
pair; the latter is rendered in memory and never mutates the workspace.

Validation and Owner Gateway expose only detail, configuration, fixed-asset,
Pexels, preview, approval, and immutable-version-render routes. All PNGs are
private, no-store, SHA-256 and ETag explicit. The loopback launcher exposes the
same Studio contract, local-only Tune routes, and the representative normal
journey described above, without Firebase; Pexels is optional unless its local
key is provided. Obsolete
reference/calibration routes, evaluator, installer, tests, and text fixtures
were removed. No deployment, reset, database mutation, publication, or
production contact was performed.

Local verification passes the complete 60-test Validation suite (three
disposable-PostgreSQL lifecycle tests skipped), five Owner Gateway tests, all
23 web unit tests, the production web build, and all 15 Playwright journeys on
desktop Chromium, 360 px Chromium, and iPhone WebKit. All seven Commander tests,
the Commander demo, primitive-engine canary, canonical PTW skill verifier,
skill-validator, deterministic three-variant visual-geometry audit,
Python compilation, four-variant visual inspection, and
`git diff --check` also pass. Built-image tests were not run because the local
Docker daemon is unavailable.

The current production state remains the Result v1/v2 milestone described
below.

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

The latest deployed milestone replaces the completed Result's raw debug
JSON presentation with a collapsed visual explanation: five initial candidate
JPEG cards, exact per-candidate parameter values, Pass 1 gates and scores, and
a three-pass ranking/pairwise/improvement/final-selection path. Candidate
previews are exposed only through authenticated run-scoped no-store routes and
retain browser-side MIME, digest, and ETag verification. Focused web unit/build
checks, Playwright on desktop, 360 px Chromium, and iPhone WebKit, the
Validation and Owner Gateway built-image suites, the disposable PostgreSQL
Result lifecycle, the clean and idempotent schema verifier, Commander
tests/demo, canonical skill verification, and `git diff --check` pass.

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

The one-click Natal repair was deployed through the owner-confirmed clean reset
as `result-v1-20260826-1710-natal-one-click` from application commit
`be3e129dc05923e6342a8c3325921ea518f33b83` and independent-platform commit
`4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`. The authorized reset irreversibly
removed one Project, one Brief, and one prior brand kit. Every Commander-owned
business table is empty, only `001_ptw_result_v1.sql` is recorded, no retired
table remains, and independent platform counts were unchanged.

Commander, Validation, Owner Gateway, platform API, and platform worker are all
healthy on the matching versioned tag with zero restarts. Firebase Hosting
serves `App-DwBfSv3E.js`; the live bytes contain the one-click Natal identity
and progress contract and exclude brand-kit setup, task entry, Text mode, and
the retired workspaces. Bridge, Pexels, dependency, skill, Telegram direct
canary, schema, 1 GB resource, hashed-bundle, Auth/App Check, unauthenticated
rejection, retired-route, service-worker, and CORS checks passed. No deployment
OOM event occurred, and the locked 24-hour resource audit is scheduled for
2026-08-27 14:17 UTC. Because the required clean-reset state contains no Result,
the live authenticated Result-image digest/ETag check is deferred to the first
real post; built-image lifecycle and 1080x1080 JPEG checks passed before release.

The initial Instagram Result UUID incident was repaired in place without a
reset as `result-v1-20260827-0900-uuid-hotfix` from application commit
`20ca7858082021076e0add35bc2511828c3676de`; the independent platform remains at
`4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`. One generated direction had mixed
`studio.*` tool IDs into a UUID-only visual `source_ids` array because that
structured-schema field accepted unrestricted strings. Candidate schemas now
bind exact server-supplied UUIDv7 enums, approved media IDs have their own
Project-asset enum, and the domain boundary repeats both checks.

The live bridge generated and domain-validated the real UUID-allowlisted
`CandidateV2` twice, with Product Brief, correction, critic, and Pexels canaries
also passing. All Commander table counts were identical across the in-place
rollout; independent-platform counts were identical across the application
cutover after the explicit canaries. Commander, Validation, and Owner Gateway
are healthy on the matching hotfix tag with zero restarts. Dependency, skill,
schema, public Auth/App Check/CORS/retired-route, and immediate 1 GB/OOM audits
passed. Failed run `01a041c0-af7c-7881-bec4-bf4ebc2d23cf` remains immutable,
and the empty operation guard permits its normal Owner Console retry as a new
child run.

The follow-up incomplete-visual-role incident was repaired in place without a
reset as `result-v1-20260827-0930-role-hotfix` from application commit
`ff05f65ae86ffd7a96699ba4de9d438e940113eb`; the independent platform remains at
`4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`. Instagram candidate schemas now
require exactly the nine adapter roles, the ordinary prompt enumerates that
same ordered set, and complete `CandidateV2` validation runs inside the fresh
two-attempt provider boundary instead of after a schema-only success.

Both pre-cutover and post-cutover live bridge canaries generated and
domain-validated exact-nine-role Candidates, with fresh Product Brief,
correction, critic, and Pexels canaries also passing. Commander counts were
preserved and platform counts were unchanged by the application cutover.
Commander, Validation, and Owner Gateway are healthy on the matching role
hotfix tag with zero restarts. Schema, dependency, skill, public bundle,
Auth/CORS, and immediate 1 GB/OOM audits passed. Failed run
`01a041d9-3a09-7fd4-af84-b9a863a57303` remains immutable, and the empty
operation guard permits its normal Owner Console retry as a new child run.

The follow-up Result critic preview-mapping incident was repaired in place
without a reset as `result-v1-20260827-1025-critic-hotfix` from application
commit `1dbc3029988b4bb06d28dbc53689a8d6ac832e3b`; the independent platform
remains at `4f9225febfcb828faae459ef3c0a4cdf7a30a5dd`. The application now accepts
the exact persisted preview mapping including `mime_type`, validates the JPEG
and digest before transport, emits strict list-shaped element scores, and runs
complete critic-domain validation inside the fresh two-attempt boundary. The
release canary exercises this real contract rather than a marker response.

Both pre-cutover and post-cutover live bridge rounds passed the real multimodal
critic schema, exact mapped JPEG, pixel inspection, and domain validator, with
fresh Product Brief, correction, candidate, and Pexels canaries also passing.
Commander counts were preserved and platform counts were unchanged by the
application cutover. Commander, Validation, and Owner Gateway are healthy on
the matching critic hotfix tag with zero restarts. Dependency, skill, schema,
public bundle, Auth/CORS, and immediate 1 GB/OOM audits passed. Failed run
`01a041f1-a430-7662-b27f-2339197e794b` and its five rendered candidates remain
immutable, and the empty operation guard permits its normal Owner Console retry
as a new child run.

The visual Result decision trace was deployed in place without a reset as
`result-v1-20260827-1140-decision-trace` from application commit
`5cfa759b00742329636a425a42cafc029bd8ddb9`; the independent platform remains
at `4f9225febfcb828faae459ef3c0a4cdf7a30a5dd` and its images were not changed.
The live Owner Console serves entry bundle `index-D5UxwWt3.js` and lazy app
bundle `App-pDzkFjZl.js`; the latter contains the five-direction, exact-
parameter, and three-pass decision markers. The new candidate asset route
rejects unauthenticated access and a real persisted candidate JPEG passed its
internal run scope, MIME, no-store, SHA-256, and ETag checks.

Fresh Product Brief, correction, UUID-allowlisted candidate, real mapped
multimodal critic, and Pexels canaries passed before and after cutover. A first
attempt safely restored the prior matching application tag when its
preservation window incorrectly included expected platform canary bookkeeping;
Commander counts remained unchanged. The corrected cutover compared counts
only across application replacement and restart, preserving one Project, one
Brief, four runs, nineteen candidates, three critic passes, and one Result;
independent-platform counts were also unchanged across that cutover. All three
application services are healthy on the matching tag with zero restart counts,
emergency stop is off, dependency/skill/schema/public Auth/App Check/CORS/
bundle/Telegram audits pass, no deployment OOM evidence exists, and the locked
24-hour resource audit is scheduled for 2026-08-28 08:38:53 UTC.

The active Studio alignment fix is deployed as immutable version 3. Candidate
contexts now include the complete digest-locked Studio snapshot; visible Instagram copy binds to
`headline` and `primary_text`; and the anonymous critic payload includes the
resolved frame contract alongside each JPEG. Validation rejects localized
static template text and requires the dark Natal logo's topmost containing
layer to be a light surface. Persisted v2 snapshots retain their original
bindings and replay path. The final-gate error now directs the owner to an
immutable retry from the approved Brief instead of unavailable task/asset
controls. The in-place Linux/amd64 release
`result-v3-20260827-1645-final-gates` preserved every table count across
replacement and explicit restart, passed the five-template English/Ukrainian
canary, live bridge/Pexels, schema/dependency/public-console/authenticated-image,
restart, immediate 1 GB, replay, and OOM audits, and left all three services
healthy with zero restart counts.

Immutable child run `01a04385-395a-7897-a3e2-0852ed3e83ae` completed from the
failed parent with seven candidates, three critic passes, and Result Creative
`01a04395-6373-7ad7-b081-1f81d2656520`. Its selected `direct_offer@3` scored 90
with no complexity penalty. Protected headline, primary text, offer, and CTA
bindings match; deterministic replay reproduces the exact JPEG; and all five
initial candidates have distinct structural signatures with minimum pairwise
decoded-pixel RMS 91.86. The operation guard is clear, no new OOM evidence
exists, and the locked follow-up audit is scheduled for 2026-08-28 13:58:26
UTC.

The agent-controlled Studio template v2 milestone is deployed in place. Five
Git-owned
`ptw.studio.template.v1` component trees now replace the shared hardcoded
Instagram skeleton: photo tension, split contrast, structured mechanism proof,
editorial human story, and typography-first direct offer. The five active
strategy documents are version 2 and digest-lock their matching Studio
definition at startup. The internal catalog exposes strict predefined media,
logo, headline, body, offer, CTA, badge, and shape tools without restoring any
Studio UI or public route.

Every slider now resolves through declared deterministic component rules and a
quantized ordered patch. Each new recipe embeds its immutable template snapshot,
protected bindings, exact/normalized sliders, component UUID map,
catalog/renderer identities, and parent recipe/base digest; child recipes add a
direct `derived_from` edge. Render manifests include the complete resolved
recipe and production digests. Historical v1 pixels remain byte-identical.

The Linux/amd64 release `result-v2-20260827-1450-studio-templates`, built from
application commit `ddd5b844082916df51c2c1a6a640bce4591d520d`, passes 32
built-image Validation tests, seven Commander tests and demo, five
Owner Gateway tests, 17 Owner web tests/build, the three-test disposable
PostgreSQL lifecycle (including nine persisted Instagram recipes and four
direct parent edges), the idempotent clean-schema journey, canonical skill
verification, and diff hygiene. Its standalone non-persisting canary renders
five English and five Ukrainian recipes, replays identical canonical recipes
and decoded pixels, verifies complete manifests, and reports all ten pairwise
visual differences above the materiality threshold.

The preservation-gated production cutover completed without a reset. Exact
all-table snapshots were identical across application replacement and explicit
restart recovery; the retained core state is one Project, one Brief, four runs,
nineteen candidates/recipes/renders, three critic passes, and one Result. The
independent platform remains at
`4f9225febfcb828faae459ef3c0a4cdf7a30a5dd` on its prior images. Pre- and
post-cutover Studio, live four-mode bridge/critic, and Pexels canaries passed,
as did schema, dependency, canonical-skill, Telegram direct, authenticated
JPEG MIME/no-store/digest/ETag, public Auth/App Check/CORS/retired-route, and
immediate 1 GB audits. Commander, Validation, and Owner Gateway are healthy on
the matching v2 tag with zero restart counts after the recovery test;
emergency stop is off, no deployment OOM evidence exists, 2 GiB swap remains
available, and the locked 24-hour audit is scheduled for
2026-08-28 12:35:40 UTC.
