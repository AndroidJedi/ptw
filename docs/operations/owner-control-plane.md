# Owner control plane operations

Status: production cutover runbook
Updated: 2026-08-22

Commander Web is deployed to `https://provethemwrong-86123.firebaseapp.com`; the API
and WebSockets use `https://commander.proove-them-wrong.com`. Firebase stores
identity and static Hosting content only.

The `firebaseapp.com` Hosting origin is canonical so Firebase Auth helper state
remains first-party in Safari and other storage-partitioned browsers. The
parallel `web.app` URL forwards to the canonical origin before Auth is
initialized.

Browser Auth selects local-storage persistence as part of `initializeAuth`;
it neither starts with IndexedDB nor asynchronously migrates persistence during
a redirect. The mounted boot path consumes the redirect result independently of
the Auth observer, has a bounded Safari recovery path, and the service worker
never handles `/__/auth/` helper or callback traffic. ID-token and App Check
acquisition is also bounded separately from the API request deadline so a
stalled browser credential store becomes a visible retryable failure.

## Authentication boundary

Identity Platform Google Sign-In is guarded by `beforeUserCreated` and
`beforeUserSignedIn` in `europe-west3`. Only verified Google identity
`sgolovaschuk@gmail.com` is accepted. The gateway then verifies the ID token,
project/audience/issuer, verified email, Google provider, pinned UID, and the
exact App Check app ID. Wrong email, UID, provider, verification state, project,
or App Check token fails closed.

The Firebase service account is mounted from
`/opt/ptw/secrets/firebase-service-account.json`, readable only by root. It is
never served to the PWA or stored in Git.

## Job execution

Plan mode talks to [Codex App Server](https://learn.chatgpt.com/docs/app-server)
in a read-only sandbox. Its final plan is
stored with an immutable SHA-256 digest. Approval must submit the same digest;
one approval can launch only one
[`codex exec --json`](https://learn.chatgpt.com/docs/non-interactive-mode)
child. Live JSONL events,
cancellation, validation, Git/PR, and deployment evidence are shown in Jobs.
Destructive plans additionally require an exact owner confirmation. They do
not require a backup by the owner's explicit decision.

Laval, Branding, and Codex planning/execution, including Natal landing builds,
are intentionally serial on the 1 GB host.
A conflicting start returns HTTP 409 with the active operation ID. Waiting for
plan or logo approval is not active work; approval rechecks the shared guard
before execution or kit assembly.

## Emergency control

Telegram `/stop` and the web emergency button set the durable platform stop,
cancel queued/running work, and fan out stop state to idea and creative
runtimes. While active, the gateway rejects new generation, post, batch, and
execution approvals. Resume is available only from Docs / System and clears the
platform stop only after every runtime acknowledges resume.

## Root terminal

`ptw-root-broker.service` listens only on `/run/ptw-root-broker/control.sock`
and accepts peer UID 10002. One authenticated browser session is allowed, with
a 15-minute idle and 60-minute hard limit. Only session metadata is retained.
The terminal is break-glass: it bypasses Commander policy and has no extra
re-authentication by the owner's explicit risk decision.

## Deployment checks

```sh
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
python3 -m unittest discover -s tests/owner_gateway -v
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
npm --prefix firebase/functions run check
git diff --check
```

## Idea Laval VPS cutover

The Idea service reads Laval provider settings from explicitly passed VPS
environment files. The fixture
providers are safe for orchestration acceptance but do not constitute live
market evidence. For live V2 operation set
`LAVAL_SEARCH_PROVIDER=dataforseo` with its two credentials and configure an
official YouTube Data API key. Google Trends is optional. Do not put these
values in Git or the web application.

Obtain the DataForSEO API login and API password from
<https://app.dataforseo.com/api-access>; the API password is distinct from the
dashboard password. Configure it interactively without chat or shell-history
exposure:

```sh
ssh -i ~/.ssh/ptw_commander -o IdentitiesOnly=yes root@165.245.212.184
cd /root/ptw
scripts/configure_laval_providers.sh
```

The script validates the DataForSEO sandbox and an official YouTube
`videos.list` canary, writes `DATAFORSEO_VERIFIED=1` and `YOUTUBE_VERIFIED=1`,
and fixes the run maximum at USD 0.05 with only USD 0.04 reservable. It does not
configure Google Trends; missing Trends access does not block V2 completion.
When DataForSEO is already configured, use
`scripts/configure_laval_providers.sh --youtube-only`; this prompts for and
replaces only the canary-verified YouTube key and readiness marker.

Build Linux/amd64 images locally, publish them through the single locked SSH
session, then deploy Hosting after all API checks pass:

```sh
scripts/build_ptw_release_images.sh RELEASE_TAG .local/release-images
scripts/publish_ptw_release_serial.sh RELEASE_TAG .local/release-images
```

The publisher opens exactly one SSH session, acquires the maintenance lock
before Git synchronization, transfers and loads one image at a time, applies
migrations once, and uses `--no-deps --wait --no-build` for exactly one service
per start. It rejects a dirty VPS checkout or an existing lock holder. Never
run `docker build`, background jobs, `xargs -P`, GNU Parallel, parallel SSH, or
a multi-service `compose up` on production.

After 24 clean hours, open one SSH session and run
`/root/ptw/scripts/audit_ptw_1gb.sh`. It uses the same nonblocking maintenance
lock and fails on a retired worker, sub-two-second health regression, less than
250 MiB available memory, or any OOM evidence in the preceding 24 hours.

The web build has no secret dependency for App Check: the public production
reCAPTCHA Enterprise site key lives beside the Firebase browser config. The
build fails unless its output contains the Commander API origin, App Check
header, and site key, and the Hosting predeploy hook always rebuilds before
uploading.

Never omit `/opt/ptw/platform/.env` when rendering or recreating the Owner
Gateway. Compose now rejects an empty platform PostgreSQL password, and gateway
settings independently reject a passwordless `PLATFORM_DATABASE_URL`. After a
recreation, verify password presence without printing the URL and execute
`PlatformRepository.summary()` inside the container; shallow health alone does
not prove Overview's database dependency.

PTW skills live canonically under `skills/`. Desktop Codex uses symlinks and the
CLI agents mount that same tree, so incident knowledge is updated once and read
identically on the next run. Install the automatic post-merge synchronization
once per checkout, then verify it:

```sh
scripts/install_ptw_skill_sync.sh
python3 scripts/verify_ptw_skills.py
```

The Idea API binds to loopback port `8093` by default, avoiding Commander's
`8091`; normal browser traffic still travels through the authenticated Owner
Gateway over the shared backend network. The Idea API applies numbered
migrations at startup. Migration `005_retire_idea_evolution.sql` irreversibly
removes retired C01-C10 runtime rows while preserving Laval runs and the active
mission.

The Idea Compose file owns the explicit `ptw-idea-generation` project. Do not
override it to Commander's `ptw` project: operating separate Compose files in
one project makes each service appear orphaned to the other and permits orphan
cleanup to remove a live dependency. The isolated Idea service explicitly joins
external `ptw_default` for `commander-db` DNS and the platform backend for its
`ptw-idea-api` gateway alias. After deploying either boundary, run:

```sh
skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh
```

Before declaring the feature live, complete the manual and automatic runs,
five-country/rerun inspection, override, restart, graph-persistence, export,
failure-path, and emergency stop/resume checks in
[`idea-laval-engine.md`](../architecture/idea-laval-engine.md).

Branding cutover additionally requires an eligible completed live Idea,
automatic progression through eight pre-review stages, explicit approval of all
three current logos, one explicit direction approval, authenticated asset/ZIP access,
consumer compilation, graph lineage inspection, stale-kit enforcement, and an
Idea one-service restart. See [`branding-v1.md`](../architecture/branding-v1.md).
During review, a non-empty comment must queue a durable same-direction logo
revision and must not advance. Only an empty-field approval advances. Restart
recovery must reuse the same revision attempt/provider task, while a failed
revision exposes one owner retry action.
Branding reuses the existing ChatGPT-authenticated Codex bridge for strict text
and `$imagegen`; do not configure or copy a second API key. The compatibility
`scripts/configure_brand_provider.sh` command now runs the non-mutating release
audit. A completed live case remains selectable even if all assessed theses
were rejected. The release gate is:

```sh
PTW_REQUIRE_BRANDING_READY=1 \
  skills/ptw-owner-console-incident/scripts/audit_vps_owner_dependencies.sh
```

After deploy, verify exact-owner login, negative auth/App Check, one Plan and
one approved Execute, cancellation, root `id`/`pwd`, emergency stop/resume,
restart persistence, and that the PWA service worker never caches API, image,
WebSocket, or terminal traffic.

The Landing tab owns its build lifecycle rather than handing the owner to the
global Plan/Execute list. `GET /api/v1/landings/templates` serves the repository
catalog, `GET /api/v1/landings/candidates` derives briefs from completed live
Laval cases, and `POST /api/v1/landings/builds` resolves the source IDs again,
persists a PostgreSQL `landing` entity with Idea lineage, starts the deterministic
builder immediately, and publishes the successful result to the server-pinned
dedicated Firebase Hosting site. Browser-provided source IDs, brand names,
Firebase targets, credentials, and output paths are ignored. The UI polls
`GET /api/v1/landings/builds/<uuid>` and lists only Landing-domain history;
failed builds may be retried through the matching authenticated retry endpoint.
The external release contains only allowlisted public static files, never the
internal brief or build provenance JSON.
