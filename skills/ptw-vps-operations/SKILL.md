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

All production diagnostics, recovery, and deployment commands run through one
SSH session while holding `/run/lock/ptw-maintenance.lock`. If another owner
holds it, exit immediately. Never open parallel SSH channels, use background
jobs, pipelines that run production commands concurrently, `xargs -P`, GNU
Parallel, parallel image loads, or a multi-service Compose start. Read-only
provider-console work before SSH recovery is the only exception.

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

- Keep normal instructions web-only. Telegram input is limited to emergency
  `/help`, `/status`, and `/stop`; general proactive delivery is retired. The
  sole outbound exception is a direct, deduplicated Idea Laval transition
  notification for `paused`, `completed`, or `failed`. It must use `sendMessage`
  from the completing Idea process, never `getUpdates`, a new poller, or the
  retired `commander_outbox` worker.
- Never print, copy, rotate, or replace the existing Telegram token without
  explicit owner authorization.
- Use disposable databases for migration tests unless an exact production
  target is explicitly authorized.
- Expose only canonical Idea Laval v3. Never seed or expose C01-C10, synthetic
  owner ideas, Idea Evolution, or fixture/demo records as production owner data.
- Never run `scripts/reset_ptw.sh` without the owner's exact irreversible-reset
  request and confirmation.
- Before a reset drops either application schema, resolve one matching,
  non-`latest` release tag from the deployed Commander, Idea, and Owner Gateway
  containers. Export that tag for every reset migration/start and require
  `--no-build`; a reset must never build on the 1 GB VPS or silently switch to
  a default image. Pass the configured platform owner ID explicitly into its
  one-shot seed container because Compose interpolation files do not
  automatically inject variables into a service environment. Recreate Owner
  Gateway after reseeding so it cannot retain pre-reset database connections.
- Resolve exact targets before restarts or deletion. Inspect bounded logs; never
  dump Compose configuration or container environments.

## Deployment workflow

1. Reconcile local and VPS Git state without destroying either side, under the
   maintenance lock.
2. Build, test, and package Linux/amd64 images off-host. Production never runs
   Docker builds and uses only prebuilt release tags.
3. Pass every required interpolation file explicitly. Commander and Owner
   Gateway recreation requires both `/opt/ptw/platform/.env` and
   `.env.commander`; omission previously produced a passwordless platform DSN
   and authenticated Overview HTTP 500s.
4. Use `docker compose up -d --no-deps --wait --no-build <service>` for exactly
   one recreated service at a time. Confirm parsed DSN
   password presence without printing the URL, then exercise the exact
   database-backed path rather than trusting shallow health alone.
5. Keep Idea Laval in its explicit `ptw-idea-generation` Compose project.
   Commander and Idea must not share a project namespace because orphan cleanup
   from one Compose file can delete services owned by the other. Keep Idea on
   external `ptw_default` for `commander-db` DNS as well as the platform backend
   for its gateway alias. After either deployment, run the owner-incident
   skill's VPS dependency audit.
6. Load and verify one image at a time. Apply numbered migrations once, then
   start services in dependency order: Commander database if required,
   Commander migration, Commander API, Idea API, Owner Gateway, and finally web
   Hosting after API verification. Never start the retired `/root/ptw`
   `commander-worker` or `commander-ad-worker` on the 1 GB profile. The
   unrelated `/opt/ptw/platform` `commander-worker` is the required Codex/LLM
   bridge and must remain healthy.
7. Validate loopback/public health, exact-owner auth, App Check, API calls,
   persistence, restart behavior, and user-facing errors.
8. For Commander changes, run the repository-mandated tests, demo, and
   `git diff --check`.

For a Laval Telegram release, keep `OUTBOUND_NOTIFICATIONS_ENABLED=false` and
enable only `LAVAL_TELEGRAM_NOTIFICATIONS_ENABLED`. Verify one direct canary
send, its `telegram_status_send_reserved` and `telegram_status_sent` actions,
deduplication on the same transition, absence of a new poller/container, and a
bounded failed action when Telegram rejects delivery. Never resume a saved run
merely to test notification delivery.

Never force a status-formatted notification canary against an existing owner
run: it is indistinguishable from a real state transition and can be mistaken
for newly requested work. Prefer unit/transport verification plus the next
naturally occurring owner-authorized terminal transition. If the owner
explicitly authorizes a live delivery canary, label it unmistakably as a test
and do not present real-run recovery instructions. Normal status notifications
must link to their exact run in the web console.

Use `scripts/build_ptw_release_images.sh` locally and
`scripts/publish_ptw_release_serial.sh` for the release. The publisher creates
one serialized SSH input stream and the VPS runner owns the maintenance lock for
Git reconciliation, image loads, swap/tuning, migrations, starts, and checks.

## 1 GB pressure discriminator

When latency is normal for hours and then HTTPS plus the SSH banner stall,
stale Codex/Node children, a stuck Laval thread, duplicate containers, and
connection accumulation are credible discriminators. The pre-fix Idea store
opened a PostgreSQL connection per repository call and could create thousands
of short-lived backend PIDs during one Laval run; the fixed service should hold
one serialized `application_name=ptw-idea-api` connection. After a provider reboot,
capture bounded PID/PPID/RSS/age, prior-boot OOM events, load, available memory,
swap, disk, containers, PostgreSQL connection counts, and database sizes before
recreation. Never infer a single-process cause from host pressure alone.
When sampling `pg_stat_activity`, inspect persistent non-idle rows rather than
only their count. A health probe that executes `SELECT 1` without closing its
transaction appears as an anonymous `idle in transaction` backend and must be
fixed at the probe boundary; do not kill it repeatedly as an operational cure.

The production profile requires 2 GB persistent `/swapfile` only when at least
4 GB disk is free, `vm.swappiness=10`, and both PostgreSQL authorities tuned to
48 MB shared buffers, 192 MB effective cache, 1 MB work memory, 32 MB
maintenance memory, 20 connections, and one autovacuum worker. Acceptance needs
more than 250 MB idle `MemAvailable`, stable swap, no new OOM event, no retired
worker, no overlapping operation, and API responses below two seconds.
After 24 hours, run `/root/ptw/scripts/audit_ptw_1gb.sh` through one SSH session;
do not substitute concurrent ad-hoc probes.

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

For Laval structured-language failures, inspect the independent platform
bridge before blaming model quality. Its allowlist must include the active
`laval_*` mode, and every job must invoke a new `codex exec --ephemeral` with
the caller's `--output-schema`, prompt on stdin, and `--sandbox read-only`.
Reject any deployment containing `exec resume`, prompt-as-argv, or
`--dangerously-bypass-approvals-and-sandbox`. Verify the Idea database has one
append-only `laval_llm_invocations` row per attempted stage with context/schema
hashes, prompt version, model, independent session ID, and truthful result
status. A deterministic stage artifact alone does not prove Codex executed;
check the invocation audit.

For ChatGPT-authenticated Codex CLI, keep `LLM_MODEL=codex-cli-default` unless
a named model has passed a live CLI canary. The sentinel must omit `--model`;
an API model name such as `gpt-5` can be rejected by Codex subscription auth.
After a bridge release, run one schema-bound `laval_market_signal_relevance`
canary outside any Laval run and require `session_mode=fresh`,
`ephemeral=true`, `conversation_reused=false`, and a schema-valid response.
The canary creates a platform `llm_structured` job but must not create or mutate
an Idea Laval run. If a canary fails, retain the failed job as history, inspect
its sanitized issue, deploy the correction, require a successful replacement
canary, and only then mark the generated issue resolved with the real cause and
acceptance evidence. An out-of-run canary has no `laval_llm_invocations` row;
that audit begins only when a Laval stage calls `FreshStageRunner`.

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

An incomplete `legacy-trends-v2` run paused for Google Trends must expose
**Resume with Market Signals** in the owner web console. This is an explicit
owner action: never trigger it during deploy or startup. Before and after the
action compare persisted remote task IDs, provider actual cost, evidence count,
and lineage. Completed legacy Trends runs are immutable history and are never
upgraded. Google Trends readiness is optional for new `market_signals_v2` runs.

When the owner asks to “run the PTW idea again,” resolve the selected run before
acting and distinguish three different operations:

- **Resume with Market Signals** upgrades the existing eligible paused legacy
  run in place, reuses paid work, and is the correct action for a Google Trends
  blocker.
- **Rerun stage** deliberately invalidates downstream artifacts and is not a
  synonym for resume. Use it only when the owner names the stage or correction.
- **New Laval idea** creates a separate run and a new spend budget. Never choose
  this when the owner means the already-paid PTW run.

Immediately before owner resume, require zero active Laval runs and snapshot
the selected run ID, status/current stage, pipeline version, persisted remote-ID
count, exactly-once cost-record count, provider actual cost, evidence count, and
lineage count without printing remote IDs. After the click, prove the same run
changed to `market_signals_v2`/`live_market_signals`, ordinals 8-10 became the
three Market Signal stages, one authenticated `resume_with_market_signals`
action was appended, and all snapshot counts remain unchanged before claiming
safe reuse.

## Capture reusable incident knowledge

After every production incident, update the narrowest canonical repository
skill with the root-cause discriminator, safe probes, deployment guardrail, and
acceptance boundary in the same commit. Prefer a tested bundled script. Verify
desktop symlinks and CLI mounts remain the same content. Keep secrets and
ephemeral release hashes out of skills.

When production differs from canonical Git, stop before overwriting it. Preserve
and integrate the divergence deliberately.
