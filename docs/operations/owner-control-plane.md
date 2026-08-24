# Owner control plane operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction API. Primary
navigation is Product Briefs, Ads, Landing, Admin. API/domain data is never stored
in Firebase or service-worker caches.

Plan mode is read-only and persists an immutable digest. Execute requires that
exact digest; destructive plans retain their separate confirmation. The root
broker accepts only Owner Gateway UID/GID over its Unix socket and provides one
bounded break-glass shell.

One global PostgreSQL guard serializes Product Brief, creative-batch, and Codex
Plan/Execute work. Emergency stop fans out to Commander and Validation and
rejects new heavy work.

Release command (only after explicit reset confirmation):

```sh
scripts/build_ptw_release_images.sh RELEASE_TAG .local/release-images
scripts/publish_ptw_release_serial.sh RELEASE_TAG .local/release-images \
  PLATFORM_GIT_REVISION .local/platform-release-images \
  --confirm 'RESET PTW PRODUCTION'
```

The platform image directory must contain prebuilt Linux/amd64
`commander-api.tar` and `commander-worker.tar` archives tagged with the same
release. The publisher advances the independent platform history, loads and
recreates its API and worker one at a time, and requires fresh schema-bound
canaries for `product_brief`, `product_brief_revision`, and
`ad_creative_batch` before starting the irreversible application reset. A
failed bridge or Pexels render canary stops before destruction and restores the
prior platform images.

The publisher keeps Natal on its clean placeholder and deploys the rebuilt
Owner Console only after API cutover. Run authenticated Stage 1–2 acceptance, public Auth/App
Check/CORS/bundle audits, restart persistence, old-route 404 checks, and the
24-hour resource audit.
