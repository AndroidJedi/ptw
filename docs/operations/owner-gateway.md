# Owner Gateway operations

Owner Console uses Firebase Auth, pinned owner identity, and App Check. Owner
Gateway proxies authenticated Project, Product Brief, project-scoped Studio,
private Landing/publication, and PAUSED-only Meta Ads APIs. Domain data is never stored in Firebase
or service-worker caches.

Brief approval accepts `honor_confirmed` and `template_id`; `phone_metrics`
also requires its bounded saved `creative_direction`. The creative-scoped
direction route is state-hash guarded and may replace that direction without
creating a checkpoint or learning data. It returns the updated Creative without
starting image generation. Studio exposes the common template
catalog and only Project/creative-scoped operations: list/create, detail,
composition/image retry, configuration, Save, template apply, assets/Pexels,
preview, phone generate/enhance/select/history, immutable creative approval,
version retrieval, learning decision, and learning retry.

The public Gateway and private Validation Studio route tables must have exact
GET/POST method-and-path parity after their `/api/v1/studio` and
`/internal/v1/studio` prefixes are removed. The authenticated
`POST .../creative-direction` proxy forwards the exact bounded request with the
service token and Firebase owner actor. A release must fail if the parity test
finds drift or if the live unauthenticated route-registration probe returns 404
instead of the expected 401.

Phone generation has a 480-second gateway deadline. Every history, preview, and
version render is authenticated and private/no-store. Provider credentials and
provider asset paths never cross the boundary. Cross-Project IDs fail closed.
Bare Studio mutation routes and `/api/v1/posts` do not exist.

The authenticated Settings surface exposes `ChatGPT Authorization` through only
`GET /api/v1/settings/chatgpt-authorization` and
`POST /api/v1/settings/chatgpt-authorization/refresh`. The Gateway forwards a
separate root-owned bridge secret to the private `codex-auth` service and
allowlists only authorization state, a device URL, and a device code. The
service runs the official `codex login --device-auth` against the existing
root-owned `/root/.codex` store, then runs a short non-interactive Codex test
request before reporting authorized. Tokens, auth-file contents, CLI output,
and prompts never cross this boundary or enter logs. The worker refreshes its
read-only auth copy for every request, so completed device authorization needs
no SSH session or service restart.

Local development Settings additionally exposes **Commander · GOD mode**, a
repository-wide coding chat. Run `scripts/run_local_studio.sh` and open
`http://127.0.0.1:5173/?e2e=1&page=settings`. It uses the existing local Codex
sign-in and edits the current checkout. Backend edits take effect after the
local API restarts; the coding agent must finish its reply before that restart.
This milestone has no VPS execution or deployment surface.

Only `validation_pipeline.studio_local_api` mounts the opt-in
`/api/v1/settings/commander` routes: status, chat creation/detail, message POST,
and turn Stop. The public Owner Gateway and production Validation API do not
proxy or register them. Requests require local owner/App Check headers and
loopback host/client/origin checks; responses are no-store. The service holds
an exclusive local lease, serializes coding work, stores private conversation
metadata in `.local/commander-chat/chat.sqlite3`, and never stores raw CLI logs.
A message UUID reconciles uncertain POST results. Stop and timeout terminate
the worker process group; a liveness pipe also terminates it if the API dies.
Restart retains interrupted turns without re-executing them. Applied edits
are never rolled back by Stop.

Each turn injects the current canonical `skills/commander-god-mode/SKILL.md`
and records its SHA-256. Verified reusable lessons update the narrowest
relevant canonical skill, followed by `scripts/verify_ptw_skills.py`; this is
development guidance, independent of domain learning entities. Updating a skill
cannot enable VPS access or change the runner's execution boundary. Readiness
checks CLI/skill presence, not successful model authorization. Real CLI failures
remain bounded and ask the owner to inspect local Codex sign-in/runtime.

Private Landing routes are `/api/v1/landings/projects/{project_id}/…`: source
approved Post versions, pages, page-scoped mutations, visual history, versions,
learning decisions, and failed-learning retry. They are Firebase/App-Check protected, cross-Project
IDs fail closed, and editor images are private/no-store. Publication status,
availability, Publish, Republish, rollback, and Unpublish remain owner-only and
Firebase/Auth/App Check protected.

The only authentication exception is bounded `GET`/`HEAD` below
`/api/v1/public/landings/{namespace}/{slug}`. It returns a sanitized current
snapshot or one exact selected digest-addressed PNG. Unknown, malformed,
unpublished, cross-Project, old-version, unselected-asset, and write requests
fail closed. Public JSON is `no-store`; selected current PNGs are immutable.
`LANDING_WEB_ORIGINS` is an exact comma-separated allowlist and defaults to the
Natal apex plus both Firebase default domains. No public forms, lead endpoints,
analytics, cookies, Project listing, or mutation routes exist.

Ads routes are only `/api/v1/ads/connection`, versioned presets, and
`/api/v1/ads/projects/{project_id}/…` workspace/deployment/retry/sync calls.
Meta credentials remain inside the server process. The Gateway receives only
sanitized connection metadata, Meta object IDs/statuses/issues, and local
deployment records. All write-side Meta payloads are server-fixed to PAUSED and
Instagram Feed; the owner API has no activation route.

PostgreSQL owns all creative state and bytes, append-only generation/learning
runs, immutable checkpoints/versions/skill snapshots, proposals/decisions, and
graph edges. Validation may rebuild only a disposable per-creative renderer
cache after restart; queued composition, image, and learning stages resume
idempotently.

The private Owner PWA service worker caches only its shell assets. The separate
Natal public Hosting app has no authentication or service worker. Bind loopback services
only to `127.0.0.1`. Production deployment/reset remains separate,
irreversible, and requires the exact `RESET PTW PRODUCTION` confirmation. The
separate data-preserving release entrypoint requires the exact
`DEPLOY PTW IN PLACE` confirmation and cannot invoke reset.

Owner Console-only fixes use
`scripts/deploy_owner_console_web.sh --confirm "DEPLOY OWNER CONSOLE WEB"`.
That tracked gate requires clean synchronized `main`, unit/build checks, the
full Chromium/mobile/WebKit Playwright suite, skill validation, the named
`owner-console` Hosting target, and the post-deploy public boundary audit. It
does not deploy backend images, apply migrations, or touch PostgreSQL.

Every API failure exposed to the owner must state what failed, explain the
likely cause in plain language, give the next safe action, and include only
bounded technical context such as HTTP status, method, query-free endpoint, or
object ID. Apply the same contract when an HTTP 200 list/detail response contains
a persisted item with `status: failed`. Never reflect raw provider output, 5xx
response details, credentials, prompts, or private asset paths into the UI.
