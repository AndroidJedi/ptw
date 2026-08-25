# Owner control plane operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction API. Primary
navigation is Product Briefs, Ad Studio, Ads, Landing, Admin. A URL-backed global Project
switcher scopes Product Briefs, Ad Studio, Ads, and the dormant Landing placeholder; Admin
remains system-wide. API/domain data is never stored in Firebase or service-worker
caches.

Ad Studio uses the same owner Auth/App Check boundary for its catalog, Project
brand kits, reusable templates, source uploads and Pexels import, immutable
recipe revisions, previews/final renders, artifacts/manifests, explicit
training-example publication, feedback, five-post sample sets, private source
previews, render history, and review-before-Apply wizard proposals. Upload bytes travel as bounded
base64 JSON through the existing bridge; authoritative source and render bytes
remain in PostgreSQL. The bounded Studio wizard uses separate bridge modes and
an authenticated digest-checked generated-asset endpoint; it never calls or
changes the fixed Stage 2 provider mode.

Jobs use one sequential workflow: the owner describes one job, Codex prepares
read-only steps, and the owner explicitly runs those exact digest-bound steps.
Destructive work retains its separate confirmation. The root broker accepts
only Owner Gateway UID/GID over its Unix socket and provides one bounded
break-glass shell.

One global PostgreSQL guard serializes Product Brief, creative-batch, and Codex
Plan/Execute work. Emergency stop fans out to Commander and Validation and
rejects new heavy work.

Additive release command (preserves the production database):

```sh
scripts/build_ptw_release_images.sh RELEASE_TAG .local/release-images
scripts/publish_ptw_release_serial.sh RELEASE_TAG .local/release-images \
  PLATFORM_GIT_REVISION .local/platform-release-images \
  --confirm 'DEPLOY PTW IN PLACE'
```

The platform image directory must contain prebuilt Linux/amd64
`commander-api.tar` and `commander-worker.tar` archives tagged with the same
release plus `platform-revision.bundle` containing the exact independent
platform HEAD. This bundle is the only code-transfer boundary between the two
unrelated histories; the deploy verifies its digest and commit before a
fast-forward merge. The publisher loads the enforcing platform worker before
the Studio-capable API and requires fresh schema-bound canaries for the three
fixed validation modes, both separate Studio modes, generated-asset
authentication/digest delivery, and the non-persisting Pexels render path.
Failure stops before the additive application migration and restores the prior
platform images. Migrations `003` and `004` then run in place; the deploy rejects
missing migrations or lost Brief/batch/creative/asset rows. The destructive
reset confirmation is outside this rollout. Before starting the new application
services, the deploy captures the matching Commander, Validation, and Owner
Gateway tag. Any startup, preservation-check, or readiness failure after the
additive migration restores all three previous application images; the older
services remain compatible with the additive schema.

The publisher keeps Natal on its clean placeholder and deploys the rebuilt
Owner Console only after API cutover. Run authenticated Stage 1–2 acceptance, public Auth/App
Check/CORS/bundle audits, restart persistence, old-route 404 checks, and the
24-hour resource audit.
