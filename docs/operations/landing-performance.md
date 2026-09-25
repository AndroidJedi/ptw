# Landing performance and recovery

New image writes prepare responsive `webp-v1` copies using registered slot roles:
app screens use widths 480/720/960, other artwork 960/1440, without upscaling.
Quality is 90. Native/palette alpha and raw/prepared PNGs are preserved. Bundled
phone hardware uses lossless WebP; review portraits use bounded 160px copies.
`scripts/prepare_landing_bundled_images.py` records source/output digests. Existing
template identities, approved records and application selections stay unchanged.

Snapshots optionally expose `asset_variants`. Public derivative URLs bind slug,
approved version, slot, original digest, profile and derivative digest. Validation
and Gateway preserve publication access checks and immutable caching. Private
routes require owner authentication and use no-store. Encoding occurs before
publication, never in a read. Original PNG routes remain fallbacks. Both shared
renderers reserve image geometry, prioritize heroes, defer supporting art and show
loading placeholders. Native WebKit tests cover cached errors and PNG fallback.

Landing Studio posts Agent/Generate/Enhance requests to `.../pages/{id}/operations`;
GET on that collection returns the latest operation, GET `/{operation_id}` returns
status, and POST `/{operation_id}/retry` continues unfinished work. The request UUID
binds frozen settings, instructions and reference hashes. Migration 018 adds
`landing_operations`, append-only `landing_operation_events` and typed graph
membership. Screenshots stay temporary. Queue, interpretation, provider queue,
generation, preparation and persistence timings are recorded without estimates.

Two independent images can generate concurrently. The companion advertises its
bounded media capacity, has one general worker plus one media-only worker, uses
separate database connections, and isolates CLI homes. Astra, reasoning and image
output policy remain unchanged. Page mutations reject active operations. Provider
generation and display preparation happen outside page locks; each image commits
with a state check. Persistence sends only changed files. Reads never rewrite a
restored workspace. Restart marks active operations interrupted; retries reconcile
committed source provenance, preserve completed slots, and reuse provider keys for
uncertain outcomes. Known terminal provider failures receive a fresh attempt.
The companion marks abandoned running jobs failed on startup; completed jobs are
retained. Before retrying, Landing reads the recorded provider request status so a
known worker restart can receive a fresh attempt without an extra failed retry.
Initial template creation also prepares images outside its database workspace lock,
so status reads show completed slots while the next image is generating. Creation
uses the same blocking dialog and checks server state before a generation retry.

The native dialog covers the viewport from request preparation through result
application and decoded selected images. It blocks underlying focus, controls and
scrolling, announces actual steps/image counts and elapsed time, supports reduced
motion and English/Ukrainian, and restores focus. Failure stays in the same dialog
with Retry unfinished work / Return to editor and sanitized technical context.
Browser refresh resumes the saved UUID. Reauthorization, corrected input or original
screenshot reattachment is explicit. Historical images load only for an open
inspector; selected images appear independently.

Verification commands:

```sh
.venv/bin/python -m unittest tests.validation_pipeline.test_landing_performance -v
.venv/bin/python scripts/verify_landing_performance.py
scripts/verify_ptw_migration_runner.sh
npm --prefix apps/commander-web run test:e2e
npm --prefix apps/landing-web run test:e2e
```

The PostgreSQL canary creates disposable Projects for Project Landing v5 and
App Showcase v1/v2, exercises authenticated Agent/image operations, durable restore,
public derivatives and a replacement draft while preserving its approved source.
The companion patch is `patches/platform/landing-performance-v1.patch`; apply it
with `git apply --unidiff-zero` on base
`35b8fa0eb6b0e9e56a6448f05db14b18d01414a3` in the independent checkout.
Deploy the paired candidate only through `publish_ptw_in_place_serial.sh` and its
migration-aware preserving workflow. The previous runtime tolerates the additive
tables. Never use a reset or bulk reapplication for this release.

The owner explicitly authorized refreshing only `hotel-assistant`. Local review
retains its copy/settings/artwork, measures 5,584,916 original bytes versus 466,312
bytes for the largest WebP copies (91.65% reduction), and checks all 11 sections at
1440px, 768px, 360px and iPhone WebKit. CLS stays below 0.001 on measured Chromium
views. The real two-image capacity canary completed in 58.254 seconds with a
423,047,168-byte worker peak under its 805,306,368-byte cap, minimum host available
memory 252,256,256 bytes, and zero new OOM events. Production acceptance must still
record exact revision/Hosting versions, the refreshed immutable version and live
measurements in the current-state checkpoint.
