# Owner Gateway operations

Owner Console uses Firebase Auth, pinned owner identity, and App Check. Owner
Gateway proxies authenticated Project, Product Brief, and Universal Studio APIs.
Domain data is never stored in Firebase or service-worker caches.

Brief operations are create/list/detail/correct/retry/approve. Studio operations
are template selection, configuration, component metadata, asset/Pexels import,
preview, phone-hero generate/enhance/select/history, immutable version approval,
and saved version/render retrieval. Phone generation has a 480-second gateway
deadline; every history and render response is authenticated and private/no-store.
Provider credentials and provider asset paths never cross this boundary. Social
posts and all content-run/review/export/notification routes are retired and must
return 404.

Production Studio uses one PostgreSQL-owned singleton workspace. Mutable cache
files are rehydrated from digest-checked database bytes after a Validation API
replacement. Generated assets and approved versions are append-only UUID graph
entities joined through `contains`, `derived_from`, and `supersedes`; API detail
responses expose those IDs. The deploy gate compares workspace/state IDs across
a forced Validation API replacement.

The new simple Post milestone is loopback-only and is not proxied here. Its
local `/api/v1/posts` routes and `.local/post-workspace` authority do not imply
production availability.

The PWA service worker caches only public shell assets. API and authenticated
render responses are never cached. Bind the loopback app only to `127.0.0.1`.
Production release remains confirmation-gated and an authorized reset must use
the exact `RESET PTW PRODUCTION` phrase.
