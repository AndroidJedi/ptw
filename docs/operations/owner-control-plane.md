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

After deploy, verify exact-owner login, negative auth/App Check, one Plan and
one approved Execute, cancellation, root `id`/`pwd`, emergency stop/resume,
restart persistence, and that the PWA service worker never caches API, image,
WebSocket, or terminal traffic.
