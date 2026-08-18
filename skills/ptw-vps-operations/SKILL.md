---
name: ptw-vps-operations
description: Safely inspect, deploy, verify, and troubleshoot the PTW production VPS, Docker Compose services, Caddy routing, Firebase owner UI, Commander, and Idea Laval. Use for PTW production/VPS requests, deployments, service health, logs, migrations, web-console availability, or restart and incident work.
---

# PTW VPS operations

Use the dedicated SSH identity without storing or echoing its passphrase:

```sh
ssh -i ~/.ssh/ptw_commander -o IdentitiesOnly=yes root@165.245.212.184
```

Never put a passphrase, token, environment value, or private key in this skill,
Git, logs, or command output.

## Keep desktop and CLI skills identical

Treat `/root/ptw/skills` on production and the repository `skills/` directory
locally as canonical. Desktop Codex skill paths symlink to these folders.
Commander and Owner Gateway mount the same folders at `$CODEX_HOME/skills`; the
Owner Gateway mount is writable so CLI-driven fixes can update the canonical
skill in the same Git change. Run `scripts/install_ptw_skill_sync.sh` once per
checkout; its post-merge hook links newly added skills and repairs production
group-write permissions after every pull. Verify after recreating either service.

## Start every operation

1. Inspect `/root/ptw/AGENTS.md` if present, then read
   `/root/ptw/docs/README.md`, current-state checkpoint, and the task route.
2. Run `git -C /root/ptw status --short --branch` before writes. Preserve all
   existing changes and synchronize without overwriting uncommitted work.
3. Treat `/root/ptw` and `/opt/ptw/platform` as unrelated histories. Never merge
   them or reuse unrelated deployment credentials.
4. Confirm disk, container, network, and environment-file presence without
   printing environment contents.

## Production layout

- Repository: `/root/ptw`
- Independent platform: `/opt/ptw/platform`
- Shared Docker network: `ptw-agent-platform_backend`
- Commander Compose: `/root/ptw/docker-compose.commander.yml`
- Idea Compose: `/root/ptw/docker-compose.idea-generation.yml`
- Commander environment: `/root/ptw/.env.commander`
- Owner/Idea environment: `/root/ptw/.env.owner-gateway`
- Platform environment: `/opt/ptw/platform/.env`
- Canonical owner web: `https://provethemwrong-86123.firebaseapp.com`
- Legacy owner host: `https://provethemwrong-86123.web.app`
- Owner API: `https://commander.proove-them-wrong.com`

Use repository runbooks as authority.

## Safety boundaries

- Keep normal instructions web-only. Telegram is notifications plus emergency
  `/help`, `/status`, and `/stop`.
- Never print, copy, rotate, or replace the existing Telegram token without
  explicit owner authorization.
- Use disposable databases for migration tests unless an exact production
  target is explicitly authorized.
- Expose only canonical Idea Laval v2. Never seed or expose C01-C10, synthetic
  owner ideas, Idea Evolution, or fixture/demo records as production owner data.
- Never run `scripts/reset_ptw.sh` without the owner's exact irreversible-reset
  request and confirmation.
- Resolve exact targets before restarts or deletion. Inspect bounded logs; never
  dump Compose configuration or container environments.

## Deployment workflow

1. Reconcile local and VPS Git state without destroying either side.
2. Build and test the changed boundary before restarting it.
3. Pass every required interpolation file explicitly. Commander and Owner
   Gateway recreation requires both `/opt/ptw/platform/.env` and
   `.env.commander`; omission previously produced a passwordless platform DSN
   and authenticated Overview HTTP 500s.
4. Use `docker compose up -d --wait` for recreated services. Confirm parsed DSN
   password presence without printing the URL, then exercise the exact
   database-backed path rather than trusting shallow health alone.
5. Keep Idea Laval in its explicit `ptw-idea-generation` Compose project.
   Commander and Idea must not share a project namespace because orphan cleanup
   from one Compose file can delete services owned by the other. Keep Idea on
   external `ptw_default` for `commander-db` DNS as well as the platform backend
   for its gateway alias. After either deployment, run the owner-incident
   skill's VPS dependency audit.
6. Apply numbered migrations explicitly, then start services in dependency
   order: Commander API, Idea API, Owner Gateway, web Hosting.
7. Validate loopback/public health, exact-owner auth, App Check, API calls,
   persistence, restart behavior, and user-facing errors.
8. For Commander changes, run the repository-mandated tests, demo, and
   `git diff --check`.

## Firebase Hosting and owner authentication

- Use `$ptw-owner-console-incident` for login, App Check, API-routing, Overview,
  database-readiness, or stale-PWA failures.
- Keep the public production App Check site key deterministic in source.
- Run `npm --prefix apps/commander-web run check`; the compiled-artifact gate
  must prove the API origin, App Check header, and site key.
- Deploy through `firebase deploy --only hosting`; never upload stale `dist`.
- Audit both entry and lazy `App-*.js` chunks, shell cache, `/healthz`, negative
  authentication, and production-origin CORS afterward.
- Preserve fail-closed gateway verification and never print browser tokens.
- Require authenticated owner-browser Overview success before full acceptance.

## DataForSEO credential onboarding

Run `scripts/configure_laval_providers.sh` only in an interactive VPS terminal;
its SSH session ends after the one-shot command succeeds or fails. A trailing
`Connection ... closed` therefore does not diagnose a network failure. Trust the
preceding provider status instead. The script validates the registered API login
and separately generated API password against the free sandbox and leaves the
root-owned environment unchanged on every rejection.

For an authenticated HTTP 403, first prove the same VPS can reach the sandbox
with dummy Basic Auth and receives the expected HTTP 401. If it can, do not
restart PTW or rotate unrelated credentials: verify the exact API login/password
from Dashboard -> API Access, inspect the account's IP whitelist and account
status, and escalate the persistent access-specific rejection to DataForSEO.
Never print the credential pair or the full response body; report only bounded
HTTP/provider status and message fields.

For a Laval Standard-queue timeout, resolve the exact run and compare
`laval_provider_tasks` counts for `completed` and `submitted`. A submitted row
with a remote task ID is already paid and must never be reposted. Use the
provider's Advanced GET only to determine readiness; retrieval is free. Once it
is ready, resume the same run so the persisted ID is fetched and its cost is
recorded exactly once. Keep the production poll window at 3600 seconds because
normal-priority outliers can exceed the earlier 900-second window.

Do not leave a production recovery as an invisible agent-only action. Normal
recovery must be available through the Ideas view's **Resume saved work**
control. If emergency diagnosis requires an authenticated internal resume,
append the real actor and bounded reason to `laval_run_actions`; never label it
as an owner action. Verify the status API exposes the original failure,
provider-task counts, recorded cost, no-repost semantics, and recovery history.
Confirm the Telegram projection contains the same run state and S00-S15
statuses, and that its outbox row is published, without printing chat IDs or
tokens. Keep deliberate stage rerun separate because it invalidates downstream
artifacts while resume preserves provider task IDs and cached work.

## Capture reusable incident knowledge

After every production incident, update the narrowest canonical repository
skill with the root-cause discriminator, safe probes, deployment guardrail, and
acceptance boundary in the same commit. Prefer a tested bundled script. Verify
desktop symlinks and CLI mounts remain the same content. Keep secrets and
ephemeral release hashes out of skills.

When production differs from canonical Git, stop before overwriting it. Preserve
and integrate the divergence deliberately.
