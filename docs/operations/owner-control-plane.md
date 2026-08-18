# Owner control plane operations

Status: production cutover runbook
Updated: 2026-08-17

Commander Web is deployed to `https://provethemwrong-86123.web.app`; the API
and WebSockets use `https://commander.proove-them-wrong.com`. Firebase stores
identity and static Hosting content only.

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

The Idea service reads Laval provider settings from the same explicitly passed
VPS environment files as the existing Idea Evolution runtime. The fixture
providers are safe for orchestration acceptance but do not constitute live
market evidence. For live operation set `LAVAL_SEARCH_PROVIDER=dataforseo` with
its two credentials and set `LAVAL_TREND_PROVIDER=google_trends` with the
owner-controlled Trends bridge URL/token. Do not put these values in Git or the
web application.

Build and restart the three server-side boundaries, then build Hosting:

```sh
cd /root/ptw
docker compose --env-file .env.commander -f docker-compose.commander.yml \
  up -d --build commander-api owner-gateway
docker compose --env-file /opt/ptw/platform/.env --env-file .env.owner-gateway \
  -f docker-compose.idea-generation.yml up -d --build idea-generation-api
npm --prefix apps/commander-web run build
firebase deploy --only hosting
```

The Idea API binds to loopback port `8093` by default, avoiding Commander's
`8091`; normal browser traffic still travels through the authenticated Owner
Gateway over the shared backend network. The Idea API applies migration
`004_idea_laval_engine.sql` at startup.

Before declaring the feature live, complete the manual and automatic runs,
five-country/rerun inspection, override, restart, graph-persistence, export,
failure-path, and emergency stop/resume checks in
[`idea-laval-engine.md`](../architecture/idea-laval-engine.md).

After deploy, verify exact-owner login, negative auth/App Check, one Plan and
one approved Execute, cancellation, root `id`/`pwd`, emergency stop/resume,
restart persistence, and that the PWA service worker never caches API, image,
WebSocket, or terminal traffic.
