# Commander current state

Updated: 2026-08-25
Branch: `codex/web-only-commander`

## Last completed milestone

The Owner Console Studio Wizard now makes its long synchronous lifecycle
visible instead of presenting a silent disabled button. Scope is labelled as
the currently open post and explicitly excludes the other four posts and saved
templates. Preview and Apply show an accessible indeterminate activity panel,
elapsed time, the bounded request limit, and whether the post has changed;
submitted fields remain locked until completion. Preview success clearly says
nothing changed yet, failure preserves the instruction and offers the correct
retry, and the UI states the generated-person restriction before submission.
The PWA shell marker is bumped to
`ptw-shell-v41-studio-wizard-progress` so the follow-up cannot be hidden by the
prior cached shell. This follow-up passes 32 Owner web Vitest tests, the
production build, all 21 desktop/360 px/iPhone browser journeys, the Commander
regression/demo checks, and canonical PTW skill verification. It is deployed
as application release `studio-wizard-ui-5a6575c` and Owner Console
cache `ptw-shell-v41-studio-wizard-progress`.

The in-place production release preserved every baseline artifact count and the
owner's existing review-only proposal. Commander, Validation, and Owner Gateway
then passed deliberate restart recovery, readiness, and the 1 GB resource
audit. Both Firebase Hosting origins serve the new bundle and cache marker; the
24-hour follow-up resource audit is scheduled.

## Previous completed milestone

The five-post Ad Studio v2 milestone is implemented, deployed, and verified in
production. It
uses approved Product Brief `01a0376d-1e97-7874-a46e-392c867593dd` and completed
Ad batch `01a03794-acfa-7a2a-830b-5bf6bd54e953` to build one immutable,
idempotent `StudioSampleSet` containing exactly five ordered Instagram-square
posts: emotional, practical, curiosity, authority, and problem-first. Each item
links its source Creative, reusable `StudioTemplateV2`, root `StudioRecipeV2`,
clean 1080 x 1080 JPEG render, editable caption and alt text, source assets, and
complete lineage. The bulk ZIP contains all five JPEGs plus captions, alt text,
attribution, and a manifest. Partial sets are never returned.

The five posts use the selected batch's real Ukrainian hooks and primary text,
the approved Brief's exact offer and CTA, the canonical Natal logo and palette,
and either the required original Pexels photo or one reviewed non-human abstract
graphic. Pexels sources are re-fetched by IDs `16664910`, `19232289`, and
`7640442`; already-rendered Ad JPEGs are not reused as backgrounds. The two
packaged generated graphics contain no people, embedded text, logo, zodiac
glyph, or watermark and carry prompt, provider/model, request, digest, review,
and no-synthetic-people provenance. Mismatched photos `34183731` and `32446190`
are excluded.

Studio has separate Preview and Edit modes. Preview and every export contain
only the shareable design: no dashed guides, tool IDs, `shape` labels, handles,
or selection chrome. Edit mode exposes authenticated media and logo previews,
layers, drag/resize, crop and focal controls, logo containment, typography,
shapes, caption, alt text, and persisted render history. Responsive inspectors
work at desktop and 360 px widths, and the component-selection black-screen
regression is covered in browser tests.

`StudioRecipeV2` separates visual frames from layout, color, effect, and
strategy modifiers. Unicode text layout uses pixel measurement, wrapping,
auto-fit, line height, maximum lines, vertical alignment, and hard overflow
rejection; protected offer and CTA frames may never truncate. `StudioTemplateV2`
uses typed bindings for Creative hook/photo/caption, Brief benefits/trust/offer/
CTA, and brand logo. Applying a template resolves bindings server-side into
fresh frame UUIDs and is idempotent by request UUID.

The review-first Studio wizard creates append-only `StudioWizardProposalV1`
records for one selected component or the whole recipe. It receives the current
recipe, selected Brief, brand kit, Project source catalog, current tool catalog,
and canonical Studio skill snapshot. Preview never mutates the recipe. Apply
validates a server-derived typed diff, protects the exact offer/CTA, rejects
cross-Project sources or scope expansion, and creates one immutable child
recipe and render exactly once. Proposal history reloads after browser or
service restart. An explicitly requested generated graphic is limited to one
bounded, digest-checked, reviewed non-human PNG with complete graph lineage.

The automatic five-Ad generator remains unchanged. The independent AI bridge
still advertises exactly `product_brief`, `product_brief_revision`, and
`ad_creative_batch` as its validation modes. Studio adds the separate
`ad_studio_recipe_revision` and `ad_studio_graphic_generation` modes. Generated
bytes cross an authenticated, ETag- and digest-checked bridge asset endpoint;
the platform and Validation services share no database, filesystem, or
credentials.

Forward migrations `003_validation_projects.sql` and `004_ad_studio.sql` are
additive. The complete schema has 31 application tables, including 11 Studio
tables, without changing prior validation rows. Production rollout uses the
explicit `DEPLOY PTW IN PLACE` path: migrate, start and verify the new services,
preserve existing Briefs/batches/creatives/assets, and restore the prior
application images on startup, preservation, or readiness failure. The
irreversible reset path is not part of this release. Platform rollout puts the
enforcing worker before the Studio-capable API and restores API before worker.

## Verification

- Populated `001`/`002` through `003`/`004` migration verification and a fresh
  PostgreSQL 16 schema pass at 31 application tables; the independent platform
  fixture is unchanged.
- Validation's built-runtime suite passes 50 tests. Focused API/provider/
  renderer coverage includes five ordered angles, exact offer/CTA, truthful alt
  text, clean JPEGs, Unicode overflow, crop/focal controls, logo transparency
  and containment, deterministic ZIPs, ETags, template idempotency, wizard
  non-mutation, protected fields, cross-Project rejection, generated-source
  provenance, Apply-once behavior, and restart recovery.
- Five disposable PostgreSQL repository integration journeys and ten Owner
  Gateway authentication/proxy tests pass.
- Owner web verification passes 32 Vitest tests, its production build, and 21
  Playwright journeys on desktop Chromium, 360 px Chromium, and iPhone WebKit
  with cache `ptw-shell-v41-studio-wizard-progress`.
- The independent platform bridge passes 96 tests. Its capabilities preserve
  the three core validation modes while enforcing the two additive Studio
  modes, exactly one image-generation call, bounded square PNG output, policy
  provenance, authenticated bytes, and ETag/digest checks.
- Commander unit tests, the deterministic demo, release-script contract tests,
  shell syntax, canonical PTW skill validation, Skill Creator validation for
  the updated skills, generated-asset manifest/digest checks, and
  `git diff --check` pass.

## Production state

Production serves application release `studio-wizard-ui-5a6575c` from commit
`5a6575c1a6638bcd4568b50672f565e92d0f171f`, Owner Console cache
`ptw-shell-v41-studio-wizard-progress`, and independent platform commit
`7ec2b6e4a4dd05f9aa277850d48d021fc65b7cf4`. The serial in-place release passed
two fresh five-mode bridge canary rounds, authenticated generated-asset
digest/ETag checks, Pexels, schema, dependency, service health, restart, 1 GB
resource, frontend build, Firebase Hosting, and public-console audits on both
hosting origins.

The authoritative production sample set is
`01a038ff-66eb-7ef9-94a8-20201a7526fd`. Its deterministic share ZIP SHA-256 is
`884b9ee1fe254fc4fdc3de5e34c968970642f0ce4e21f363c9868e4638cc919f`.
It contains the five ordered 1080 x 1080 JPEGs, five captions, five alt-text
files, and the attribution/lineage manifest. Database acceptance confirms one
completed set for the selected batch, five distinct angles, 41 distinct frame
instance UUIDs, the exact protected offer and CTA on every root recipe, the
three required Pexels IDs, the canonical Natal logo, two reviewed generated
graphics with complete provenance, and no references to `34183731` or
`32446190`.

Live Wizard proposal `01a03913-eef8-7f72-b69f-cc16503d87fb` changed only the
selected emotional headline font size to 68 in preview. Preview preserved root
recipe digest `ee749d3f4961c61e7610dd3e73d936adde395d1d42221e7071b1ea114ce13144`.
Apply created child recipe `01a03915-594d-73ee-a7e2-13a1b2ae5e66` and render
`01a03915-594d-7fc5-af8a-fcf4232e539b`; repeated Apply returned those same IDs.
After a Validation service restart, the applied proposal, preview ETag/digest,
child recipe, and render history reloaded from PostgreSQL.

The owner's 2026-08-25 17:39 Kyiv Wizard submission persisted proposal
`01a0395c-829e-7ecb-a9cf-2efb013d2c57` for recipe
`01a038ff-6804-79ff-aa82-e1d0672b45ee`. It remains `previewed`, not applied,
with a 195023-byte verified preview at SHA-256
`d2d9bc31aa69176183d459aa4a96995b5a971af03b7b1dd517a20b911a65ddf7`.
The same IDs, status, bytes, digest, and all production artifact counts survived
the post-release service restarts.

The prior completed Product Brief, batch, five Ad Creatives, assets, feedback,
lessons, and graph history remain authoritative. No production reset ran.

## Next work

Normal owner work is to edit a sample, review Wizard proposals before Apply,
publish only deliberate training examples, and capture feedback through the
existing append-only lesson flow. Landing remains a dormant Stage 3
placeholder. Ad publication, campaigns, traffic purchase, UTMs, analytics,
and automatic social posting are out of scope.
