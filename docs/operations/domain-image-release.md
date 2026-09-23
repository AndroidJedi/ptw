# Domain image policy v1 preserving release

Status: implementation prepared locally; production is unchanged. This release
uses the existing model and one image invocation per operation. It has no schema
migration, bulk rewrite, semantic image evaluation or automatic image retry.

## Companion artifact and compatibility

`patches/platform/domain-image-v1.patch` applies to the independent companion
repository at base `57a06e795296e180dcf8d0d8c6a258f4f37fee11`. Apply it in an
isolated companion checkout, run its tests, then commit and freeze that separate
revision. Do not merge the PTW and companion histories. The development checkout
is `.local/platform-domain-images`; the tracked patch is the portable artifact.

The companion advertises `image_generation_policies: ["ptw.domain-image.v1"]`
and accepts that optional input policy on the existing media mode. Versioned
requests use the supplied owner-first context without appended content bans;
technically valid unchanged enhancements are accepted. Requests without the
version retain their historical behavior, so old PTW can run with the new worker.
Reference bytes still use ephemeral handles and existing digest/format checks.
PTW refuses a missing capability before creating an image job. Old workers cannot
silently override the new policy. Rollback therefore restores PTW before rolling
back the companion.

## Release sequence (requires deployment authorization)

1. Freeze clean, committed PTW and companion revisions independently. Retain
   current source revisions, service-image references and Hosting recovery data.
   Run the normal release plan/dependency/resource checks and skill sync.
2. Build the affected PTW artifacts and both companion API/worker images for
   Linux/amd64. Verify artifact checksums. The fast PTW-only path reuses the
   deployed companion and is insufficient for this change.
3. Use the established preserving serial release path with the exact two
   revisions and `DEPLOY PTW IN PLACE`. That controller owns the maintenance
   lock, snapshots, cutover, canaries, Hosting and rollback. Never use the reset
   confirmation. Switch the compatible companion before new Validation requests.
4. Require structured readiness to report the new image policy and ephemeral
   reference support. Run `validation_pipeline.verify_bridge_contract` through
   the existing live-canary runner. Its fresh hotel hand/phone/QR/SPA scene and
   exact-image edit verify one provider invocation, image bytes/digest, reference
   binding and versioned provenance. Inspect the result without rejecting it for
   visual imperfections. No project/draft needs to be overwritten for a canary.
5. Check a disposable Post composition for three numeric cards, hypothesis
   labels, Save/Approve/reload/clone, owner override and hidden-card behavior.
   Exercise both Landing slots, current palette/crop, image-only mode, changed
   reference settings and failure retaining the previous image. Confirm provider
   context carries the exact request, pinned Brief and persisted state/settings
   digests. Verify an unchanged enhancement succeeds.
6. Record the accepted revisions, exact image references and canary outcomes in
   current state only after application and Hosting checks pass.

On any failed technical/readiness canary, use the existing controller rollback
for PTW source/images/Hosting and the retained companion images. Verify the
restored `/readyz`, bridge capabilities, authenticated draft/history reads and
current image digests. New metadata is additive JSON; old records remain readable.
No migration or data reset is needed for rollback.

## Local verification

Backend policy/service/provider tests cover the hotel request, origin priority,
references, settings binding, numeric hypotheses and provenance. Companion tests
cover new capability, unchanged edits and legacy compatibility. Web tests and
mocked image-flow browsers cover immediate apply, edit/failure/history behavior.
The native Studio audit verifies geometry and Ukrainian/English metric typography.
Live provider canaries are part of an authorized rollout, not evidence claimed
from mocked tests.
