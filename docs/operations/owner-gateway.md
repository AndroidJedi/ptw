# Owner Gateway operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction channel and
proxies only Project, Product Brief, one-click Instagram Result, and
owner-only Universal Ad Studio APIs.
Domain data is never stored in Firebase or service-worker caches.

Navigation is Product Briefs, Instagram post, and Studio. The Project switcher
is URL-backed and absent from Studio. Instagram creation accepts only the
approved Brief action; Owner Gateway supplies the fixed task and profile while
Validation provisions the canonical Natal identity. Studio configures one
fixed semantic ad structure with three fixed asset slots, Pexels sourcing,
authenticated no-store previews, and immutable rendered versions; it is not
the retired Ads workspace or an arbitrary editor. There is no public Project-asset or
brand-kit setup, Ads, Landing, Admin, Jobs, terminal, publishing, campaign,
traffic, analytics, or raw UUID-management workspace.

Local app use has the loopback-only API documented in
[`../architecture/universal-ad-studio.md`](../architecture/universal-ad-studio.md).
The normal Brief/Result screens use clearly marked deterministic demonstration
data and disable provider-backed generation; Universal Studio remains writable.
Its explicit Tune mode may run Codex against a disposable snapshot and copy
back only verified Universal Studio allowlisted files. These Tune routes are
absent from Owner Gateway and Validation production APIs. The local app does
not need Firebase, PostgreSQL, or production credentials. Do not bind that
development API beyond `127.0.0.1`.

Result status is durable and polled over HTTP. The completed view resolves the
displayed artifact to its final Creative UUID server-side before appending
feedback, zero-delta WeightUpdate, skill proposal, and graph edges. The owner
never copies an internal UUID into a form.

The completed view keeps one final post prominent. Its collapsed explanation
loads the five initial candidate previews through authenticated run-and-
candidate-scoped asset routes, verifies each persisted JPEG digest in the
browser, shows exact parameter values, and renders the three persisted critic
passes as a gate, score, ranking, pairwise, improvement, and final-selection
flow. Preview and trace responses are private and never cached.

The PWA service worker caches only public shell assets. API responses,
authenticated JPEG/PNG previews, debug traces, and feedback responses are
never cached.

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
