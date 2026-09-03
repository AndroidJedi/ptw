# Owner Gateway operations

Owner Console uses Firebase Auth, pinned owner identity, and App Check. Owner
Gateway proxies authenticated Project, Product Brief, and Universal Studio APIs.
Domain data is never stored in Firebase or service-worker caches.

Brief operations are create/list/detail/correct/retry/approve. Studio operations
are configuration, asset import, preview, immutable version approval, and saved
render retrieval. Social posts and all content-run/review/export/notification
routes are retired and must return 404.

The new simple Post milestone is loopback-only and is not proxied here. Its
local `/api/v1/posts` routes and `.local/post-workspace` authority do not imply
production availability.

The PWA service worker caches only public shell assets. API and authenticated
render responses are never cached. Bind the loopback app only to `127.0.0.1`.
Production release remains confirmation-gated; local implementation work does
not authorize deployment.
