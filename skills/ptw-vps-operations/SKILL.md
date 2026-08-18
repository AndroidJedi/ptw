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
5. Apply numbered migrations explicitly, then start services in dependency
   order: Commander API, Idea API, Owner Gateway, web Hosting.
6. Validate loopback/public health, exact-owner auth, App Check, API calls,
   persistence, restart behavior, and user-facing errors.
7. For Commander changes, run the repository-mandated tests, demo, and
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

## Capture reusable incident knowledge

After every production incident, update the narrowest canonical repository
skill with the root-cause discriminator, safe probes, deployment guardrail, and
acceptance boundary in the same commit. Prefer a tested bundled script. Verify
desktop symlinks and CLI mounts remain the same content. Keep secrets and
ephemeral release hashes out of skills.

When production differs from canonical Git, stop before overwriting it. Preserve
and integrate the divergence deliberately.
