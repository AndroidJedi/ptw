# Owner Gateway operations

Owner Console uses Firebase Auth, exact verified Google owner identity, pinned
UID, and App Check. Owner Gateway is the only normal instruction channel and
proxies only Project, Product Brief, Social Post Result, and
owner-only Universal Ad Studio APIs.
Domain data is never stored in Firebase or service-worker caches.

Navigation is Product Briefs, Social posts, and Studio. Social Posts uses one
compact Project selector; when post history exists, the selected-result toolbar
contains the post selector. Project creation and renaming stay in Product
Briefs. The selection remains URL-backed by `project` and `run`; Studio is
independent. Social creation accepts only request ID, approved
Brief ID, and optional `instagram`/`tiktok` platform. Owner Gateway maps the
platform to a fixed task/profile while Validation provisions the canonical
Natal identity. Studio configures one
fixed semantic ad structure with three fixed asset slots, Pexels sourcing,
authenticated no-store previews, and immutable rendered versions; it is not
the retired Ads workspace or an arbitrary editor. There is no public Project-asset or
brand-kit setup, Ads, Landing, Admin, Jobs, terminal, publishing, campaign,
traffic, analytics, or raw UUID-management workspace.

Local app use has the loopback-only API documented in
[`../architecture/universal-ad-studio.md`](../architecture/universal-ad-studio.md).
Briefs, approved Project assets, five-candidate Result runs, releases, and
owner-approved lessons are mutable and restart-safe in the local file authority;
an active local Result has one confirmation-gated Terminate action. The bounded
loopback endpoint marks the append-only run `terminated`, stops its exact active
Codex process group without retrying it, retains intermediate evidence, and
allows a later retry only as a child run. This route and status mutation remain
absent from Owner Gateway and the production Validation API.
Universal Studio remains a separate writable saved workspace. Provider-backed
generation uses the authenticated Codex CLI only through an empty, ephemeral,
read-only non-interactive boundary. That boundary explicitly retains `xhigh`
reasoning by default (`LOCAL_CODEX_REASONING_EFFORT` accepts bounded `low`,
`medium`, `high`, or `xhigh`) while preserving the configured model, and
records the effective effort and timeout in sanitized invocation provenance.
The local critic receives persisted 480×480 analysis derivatives bound to the
authoritative 1080×1080 PNG/JPEG digests; owner preview and export remain full
resolution. Its three `xhigh` calls attach exactly three candidates, two
candidates, then only the two group winners for final comparison. Explicit
Tune mode still uses its own
disposable writable snapshot and may copy back only verified Universal Studio
allowlisted files. All local experiment, release, lesson, and Tune routes are
absent from Owner Gateway and Validation production APIs. The local app does
not need Firebase, PostgreSQL, or production credentials. Do not bind that
development API beyond `127.0.0.1`.

`scripts/run_live_social_workspace.sh` is a separate confirmation-gated local
launcher. It uses real Firebase owner authentication and App Check for public
Project, Brief, and Social Post routes, proxies only Studio to the authenticated
loopback service, and shows a persistent live-data warning. It does not expose
PostgreSQL, bridge credentials, providers, or copied production tokens to the
browser.

Result status is durable and polled over HTTP. Instagram uses a 1080×1080 JPEG;
TikTok uses a 1080×1920 photo-post JPEG. Direct platform publishing is absent.
The completed view resolves the
displayed artifact to its final Creative UUID server-side before appending
feedback, zero-delta WeightUpdate, skill proposal, and graph edges. The owner
never copies an internal UUID into a form.

Ready appends accepted feedback and gates the export package. Improve accepts
only one 3–2000 character change comment, resolves the parent Creative
server-side, and transactionally appends rejected HumanFeedback, a zero-delta
WeightUpdate, outcome/graph lineage, and the pending child run. A later event
changes only the current review projection; prior feedback is immutable.

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
