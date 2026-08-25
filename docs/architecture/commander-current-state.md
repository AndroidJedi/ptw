# Commander current state

Updated: 2026-08-25
Branch: `codex/web-only-commander`

## Last completed milestone

The five-post Ad Studio v2 milestone is implemented and verified locally. It
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
- Validation's built-runtime suite passes 48 tests. Focused API/provider/
  renderer coverage includes five ordered angles, exact offer/CTA, truthful alt
  text, clean JPEGs, Unicode overflow, crop/focal controls, logo transparency
  and containment, deterministic ZIPs, ETags, template idempotency, wizard
  non-mutation, protected fields, cross-Project rejection, generated-source
  provenance, Apply-once behavior, and restart recovery.
- Five disposable PostgreSQL repository integration journeys and ten Owner
  Gateway authentication/proxy tests pass.
- Owner web verification passes 31 Vitest tests, its production build, and 21
  Playwright journeys on desktop Chromium, 360 px Chromium, and iPhone WebKit
  with cache `ptw-shell-v40-studio-share-posts`.
- The independent platform bridge passes 95 tests. Its capabilities preserve
  the three core validation modes while enforcing the two additive Studio
  modes, exactly one image-generation call, bounded square PNG output, policy
  provenance, authenticated bytes, and ETag/digest checks.
- Commander unit tests, the deterministic demo, release-script contract tests,
  shell syntax, canonical PTW skill validation, Skill Creator validation for
  the updated skills, generated-asset manifest/digest checks, and
  `git diff --check` pass.

## Production state

This milestone is not deployed yet. Production still serves the prior
in-place application release `learned-reruns-311dae9`, the Owner Console cache
`ptw-shell-v35-simple-jobs`, and independent platform release
`phase1-5f47722-6ed6d8d`. The existing completed Product Brief, batch, five Ad
Creatives, assets, feedback, lessons, and graph history remain authoritative.
No production reset has run for this milestone.

The release gate that remains is operational rather than architectural: commit
and push both clean repositories, build pinned Linux/amd64 application and
platform images off-host, run the live five-mode bridge and Pexels canaries,
deploy in place, create the selected real sample set, visually inspect all five
authoritative JPEGs and the downloaded share ZIP, and then record the resulting
release tag and sample-set UUID here.

## Next work

Complete the release gate above. After acceptance, normal owner work is to edit
a sample, review wizard proposals before Apply, publish only deliberate
training examples, and capture feedback through the existing append-only
lesson flow. Landing remains a dormant Stage 3 placeholder. Ad publication,
campaigns, traffic purchase, UTMs, analytics, and automatic social posting are
out of scope.
