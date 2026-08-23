# Owner control plane operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction API. Primary
navigation is Positioning, Landing, Ads, Admin. API/domain data is never stored
in Firebase or service-worker caches.

Plan mode is read-only and persists an immutable digest. Execute requires that
exact digest; destructive plans retain their separate confirmation. The root
broker accepts only Owner Gateway UID/GID over its Unix socket and provides one
bounded break-glass shell.

One global PostgreSQL guard serializes Positioning, Landing agents, and Codex
Plan/Execute. Emergency stop fans out to Commander and Positioning, rejects new
heavy work, and suppresses lead notification while preserving committed leads.

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
canaries before starting the irreversible application reset. A failed bridge
canary restores the prior platform images.

The publisher deploys the clean Natal placeholder and rebuilt Owner Console
only after API cutover. Run authenticated acceptance, public Auth/App
Check/CORS/bundle audits, restart persistence, old-route 404 checks, and the
24-hour resource audit.
