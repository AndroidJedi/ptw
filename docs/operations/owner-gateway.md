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

Settings exposes **Commander · GOD mode**, a repository-wide coding chat. Local
development uses the existing local Codex sign-in and edits the current checkout.
The hosted control uses the same pinned Firebase owner and App Check boundary as
the rest of Settings, then Owner Gateway proxies to a private `commander-god`
service. That service receives the published read-only Codex credential, copies
only `auth.json` into its private writable state for each turn, and can write
only an isolated, shallow development clone under
`/opt/ptw/commander-workspace`. Runtime `.env` files, Docker, production data,
deployment, publishing, Git push credentials, and external messaging are outside
its mounts and policy.

Hosted Settings separately exposes owner-confirmed **DEPLOY NEW CHANGES** after
a coding turn finishes. Owner Gateway forwards the UUID-bearing request to
`commander-release`, never to the coding runner. The controller shares only the
development checkout, its private state, the deployed-revision marker, and one
repository deploy key. It commits and publishes the exact candidate; GitHub
Actions builds Linux/amd64 artifacts off the 1 GB VPS, then connects with a
restricted forced-command SSH key to the preserving receiver. The controller
has no Docker socket, VPS SSH key, production environment, or database mount.
One-tap release refuses migrations and protected workflow/deployment/Docker/
Compose paths. The UI requires a second confirmation, reconciles request UUIDs,
and recovers queued/running/success/failure status after service restarts.

Settings keeps ChatGPT Authorization visible alongside Commander. Its local
GET/refresh routes use the local Codex sign-in and an owner-initiated PTY device
flow, protected by the same local headers and loopback/origin checks. Only
status and the official device URL/code reach the browser. Local sign-in status
uses `test_status: null`; it does not claim a working provider test. The separate
production authorization bridge remains unchanged. English/Ukrainian selection
now lives in Settings and persists across navigation and reload.

The local app mounts opt-in `/api/v1/settings/commander` routes with loopback and
local owner/App Check guards. Production Validation still mounts no coding
routes. Owner Gateway registers the same public contract behind pinned owner
authentication and forwards it with a service secret to
`/internal/v1/settings/commander`; responses are private/no-store. Each runner
holds an exclusive lease, serializes coding work, stores private conversation
metadata in its dedicated state volume, and never stores raw CLI logs.
A message UUID reconciles uncertain POST results. Stop and timeout terminate
the worker process group; a liveness pipe also terminates it if the API dies.
Restart retains interrupted turns without re-executing them. Applied edits
are never rolled back by Stop.

Each GOD message may include up to four owner images. Owner Gateway forwards
the authenticated bounded payload and exposes its temporary preview only after
verifying the hosted service's PNG digest. Commander normalizes and strips image
metadata, keeps the pixels outside Git and SQLite, supplies them only to the
current Codex turn, and deletes them for every terminal outcome or restart.
History retains only safe filename, size, and digest metadata.

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
