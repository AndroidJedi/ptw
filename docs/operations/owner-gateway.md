# Owner Gateway operations

Owner Console uses Firebase Auth, pinned owner identity, and App Check. Owner
Gateway proxies authenticated Project, Product Brief, and project-scoped Studio
APIs. Domain data is never stored in Firebase or service-worker caches.

Brief approval accepts exactly `honor_confirmed` and `template_id`, returns
HTTP 202, and includes the reserved creative. Studio exposes the common template
catalog and only Project/creative-scoped operations: list/create, detail,
composition/image retry, configuration, Save, template apply, assets/Pexels,
preview, phone generate/enhance/select/history, immutable creative approval,
version retrieval, learning decision, and learning retry.

Phone generation has a 480-second gateway deadline. Every history, preview, and
version render is authenticated and private/no-store. Provider credentials and
provider asset paths never cross the boundary. Cross-Project IDs fail closed.
Bare Studio mutation routes and `/api/v1/posts` do not exist.

PostgreSQL owns all creative state and bytes, append-only generation/learning
runs, immutable checkpoints/versions/skill snapshots, proposals/decisions, and
graph edges. Validation may rebuild only a disposable per-creative renderer
cache after restart; queued composition, image, and learning stages resume
idempotently.

The PWA service worker caches only public shell assets. Bind loopback services
only to `127.0.0.1`. Production deployment/reset remains separate,
irreversible, and requires the exact `RESET PTW PRODUCTION` confirmation.
