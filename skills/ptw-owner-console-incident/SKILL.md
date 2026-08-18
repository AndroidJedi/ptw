---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth, App Check, Hosting/PWA caching, Commander gateway routing, database and service readiness, and authenticated web APIs. Use when login succeeds but a tab fails, the UI reports missing Firebase ID token or App Check, Overview returns a load or HTTP 500 failure, Ideas reports that Idea Laval is unavailable, a production page serves the app shell instead of JSON, a stale service worker is suspected, or a previously verified owner-web capability regresses.
---

# PTW Owner Console Incident

Resolve the production symptom without weakening the owner-only gateway. Prove
the deployed browser bundle, request boundary, gateway, database dependencies,
and cache behavior agree before calling the incident fixed.

## Keep skill copies identical

Treat the repository `skills/` directory as canonical. The desktop Codex skill
path must symlink to this folder, while Commander and Owner Gateway containers
mount the same folder at `$CODEX_HOME/skills`. Update this canonical skill in the
same commit whenever an incident yields reusable diagnostics or guardrails.
Run `scripts/install_ptw_skill_sync.sh` once per checkout so the installed
post-merge hook keeps new skill links and CLI write permissions synchronized.

## Start safely

1. Read the repository `AGENTS.md`, `docs/README.md`, current-state checkpoint,
   `docs/operations/owner-control-plane.md`, and the React route only.
2. Read and follow `$ptw-vps-operations` before touching production.
3. Run `git status --short --branch`, fetch the tracked branch, and preserve
   local and VPS changes. Never merge `/root/ptw` with `/opt/ptw/platform`.
4. Record the exact failing origin, tab, visible message, HTTP status, and
   whether login, reload, or service-worker activation preceded it.

## Diagnose every boundary

Run `scripts/audit_live_owner_console.py` from this skill first. It safely
checks the canonical live document, entry and lazy App chunks, required bundle
markers, service-worker cache version, gateway health, negative authentication,
and production-origin CORS. It never obtains or prints owner credentials.

Then inspect every applicable boundary:

1. **Deployed document:** resolve the exact hashed JavaScript assets from the
   canonical `firebaseapp.com` HTML.
2. **Compiled bundle:** confirm the lazy `App-*.js` chunk contains the Commander
   production origin, `X-Firebase-AppCheck`, and expected public App Check site
   key. Firebase is dynamically imported, so scanning only the entry chunk is
   insufficient. Compare with a fresh local build made without shell-only
   configuration.
3. **Browser request:** verify the failing call targets the gateway, carries
   `Authorization: Bearer …` and `X-Firebase-AppCheck`, and bypasses Hosting and
   the service worker. Never print either token.
4. **Gateway response:** distinguish 401/403 authentication failures from HTTP
   500 dependency failures. Inspect a bounded traceback before changing auth.
5. **Databases:** for Overview 500s, inspect only the parsed platform DSN shape
   and `password_present`; never print the DSN. Run `PlatformRepository.summary()`
   inside the gateway container to verify the exact failing read path.
6. **PWA:** inspect the active worker version and caches. API, image, WebSocket,
   and terminal traffic must never enter a cache.
7. **Deployment state:** compare Git HEAD, VPS HEAD, build hashes, Compose
   interpolation inputs, and live assets. A healthy shallow endpoint or clean
   source tree does not prove dependencies are usable.
8. **Service bridges:** when Ideas says “Idea Laval service is unavailable,”
   authentication already passed and the gateway caught an HTTP transport
   failure. Run `scripts/audit_vps_owner_dependencies.sh` on the VPS. Check the
   Idea container, loopback health, shared-network DNS, then the token-protected
   run-list call from inside Owner Gateway. “Bridge is not configured” and an
   upstream 403 are different failures; do not rotate tokens blindly.

Treat “Firebase ID token and App Check are required” as an incomplete request,
not a reason to relax authentication. The gateway uses one message when either
value is empty, so determine which browser header is missing. In the first
August 2026 regression, App Check was tree-shaken out because its public site
key was absent at build time. In the subsequent Overview load regression, auth
and App Check succeeded but the gateway had been recreated without the platform
PostgreSQL password and returned HTTP 500.

## Prevent recurrence

- Keep public browser configuration deterministic in source and App Check
  non-nullable in the API client.
- Make the production build fail if compiled assets omit the API origin, App
  Check header, or site key. Make Hosting predeploy rebuild and run that gate.
- Require `${POSTGRES_PASSWORD:?...}` for Compose interpolation and validate
  that `PLATFORM_DATABASE_URL` contains a password at gateway startup.
- Always pass `/opt/ptw/platform/.env` when rendering or recreating Commander
  Compose services. Use `docker compose up -d --wait` and verify the specific
  database-backed read path after recreation.
- Keep `docker-compose.idea-generation.yml` in the explicit
  `ptw-idea-generation` project. Never let Commander and Idea share one Compose
  project namespace: orphan cleanup from either file can delete the other
  service. Explicitly attach Idea to external `ptw_default` so `commander-db`
  remains resolvable after isolation. Start Idea with `--wait`, then audit the
  gateway-to-Idea run list.
- Add coverage at the failed layer. Source mocks and shallow health alone do
  not catch tree-shaken config, stale output, or missing runtime credentials.
- Bump the shell cache when behavior must reach already-controlled clients.
- Update this skill and the current-state checkpoint with reusable evidence.

## Verify and deploy

Run the repository-required checks, including:

```sh
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
python3 -m unittest discover -s tests/owner_gateway -v
python3 -m unittest discover -s tests/commander -v
python3 -m commander.demo --output-dir .local/commander-demo
git diff --check
```

Use `apps/commander-web/scripts/verify-build.mjs` before Hosting deployment and
this skill's audit script afterward:

```sh
python3 scripts/audit_live_owner_console.py
```

Resolve `scripts/` relative to this `SKILL.md`. Require a real owner-browser
reload and successful authenticated Overview response before claiming full
functional acceptance. Report root cause, guardrail, deployed evidence,
automated checks, and remaining owner-only acceptance separately.
