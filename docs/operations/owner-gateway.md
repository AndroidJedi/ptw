# Owner Gateway operations

Owner Console uses Firebase Auth, pinned owner identity, and App Check. Owner
Gateway proxies authenticated Project, Product Brief, project-scoped Studio,
and project-scoped private Landing APIs. Domain data is never stored in Firebase
or service-worker caches.

Brief approval accepts `honor_confirmed` and `template_id`; `phone_metrics`
also requires its bounded saved `creative_direction`. The creative-scoped
direction route is state-hash guarded and may replace that direction without
creating a checkpoint or learning data. It returns HTTP 202
and includes the reserved creative. Studio exposes the common template
catalog and only Project/creative-scoped operations: list/create, detail,
composition/image retry, configuration, Save, template apply, assets/Pexels,
preview, phone generate/enhance/select/history, immutable creative approval,
version retrieval, learning decision, and learning retry.

Phone generation has a 480-second gateway deadline. Every history, preview, and
version render is authenticated and private/no-store. Provider credentials and
provider asset paths never cross the boundary. Cross-Project IDs fail closed.
Bare Studio mutation routes and `/api/v1/posts` do not exist.

Landing routes are only `/api/v1/landings/projects/{project_id}/…`: source
approved Post versions, pages, page-scoped mutations, visual history, versions,
learning decisions, and failed-learning retry. They are Firebase/App-Check protected, cross-Project
IDs fail closed, and images are private/no-store. There is no public Landing
render, lead endpoint, publishing action, or unscoped `/api/v1/landings` route.

PostgreSQL owns all creative state and bytes, append-only generation/learning
runs, immutable checkpoints/versions/skill snapshots, proposals/decisions, and
graph edges. Validation may rebuild only a disposable per-creative renderer
cache after restart; queued composition, image, and learning stages resume
idempotently.

The PWA service worker caches only public shell assets. Bind loopback services
only to `127.0.0.1`. Production deployment/reset remains separate,
irreversible, and requires the exact `RESET PTW PRODUCTION` confirmation.
