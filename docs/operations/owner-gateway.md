# Owner Gateway operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction channel and
proxies only Project, Product Brief, brand-kit/asset setup, and Result APIs.
Domain data is never stored in Firebase or service-worker caches.

Navigation is Product Briefs and Result. The Project switcher is URL-backed.
There is no Ads, Studio editor, Landing, Admin, Jobs, terminal, publishing,
campaign, traffic, analytics, or raw UUID-management workspace.

Result status is durable and polled over HTTP. The completed view resolves the
displayed artifact to its final Creative UUID server-side before appending
feedback, zero-delta WeightUpdate, skill proposal, and graph edges. The owner
never copies an internal UUID into a form.

The PWA service worker caches only public shell assets. API responses,
authenticated JPEGs, debug traces, and feedback responses are never cached.

Production release is reset-only for Result v1:

```sh
scripts/build_ptw_release_images.sh RELEASE_TAG .local/release-images
scripts/publish_ptw_release_serial.sh RELEASE_TAG .local/release-images \
  PLATFORM_GIT_REVISION .local/platform-release-images \
  --confirm 'RESET PTW PRODUCTION'
```

Platform archives come from its unrelated Git history. The release deploys the
enforcing worker before API, verifies exact capabilities and multimodal
canaries, then resets only the Commander-owned application schema. Owner
Console deploys after API readiness and empty-state checks pass.
