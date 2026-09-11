---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW production across Commander, Product Brief Validation, Owner Gateway, project-scoped Studio, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency boundary.
---

# PTW VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. Their authenticated structured/media bridge is the only generation
integration. Never move credentials between them or mutate platform data during
a Commander reset.

For ChatGPT/Codex authorization diagnosis, auth-only recovery, and promotion
into a complete compatible release, read
[references/codex-auth-production.md](references/codex-auth-production.md).

## Start safely

1. Read current state and the applicable operations route. Inspect both
   worktrees, exact image tags, containers, memory/swap, disk, database,
   bridge, Firebase, Pexels, and emergency-stop readiness without printing
   secrets.
   When a persisted object is failed inside an HTTP 200 response, correlate its
   bridge job and use the schema-bound worker probe; HTTP health and login status
   are insufficient.
2. Use one locked SSH session. For a normal non-migration release, run
   `scripts/release_ptw_fast.sh --release-tag RELEASE --confirm
   'DEPLOY PTW PRESERVING'`. Its committed component plan builds affected
   Linux/amd64 images off-host in parallel, streams only checksumed changed
   artifacts, and restarts only affected services. The receiver recomputes the
   plan from the exact previously deployed and requested PTW revisions. Unknown
   runtime paths select a full PTW rebuild. Compare every running service image
   after cutover and preserve independent Commander, Validation, Owner Gateway,
   and hosted GOD image references. When a gateway contract changes with a
   Validation or platform contract, include both components in the same plan.
3. Keep Pexels, Firebase, bridge, and Telegram credentials root-owned. Never
   print, rotate, copy, or replace them.
   Keep `codex-auth` private on the backend network but also attach it to the
   outbound-capable edge network; device authorization and its required working
   test both need egress. Share the worker credential through a dedicated
   read-only directory bind, never a primary-auth single-file bind that can stay
   pinned to a stale inode after atomic replacement.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   separately authorizes deployment and provides exactly
   `RESET PTW PRODUCTION`.
5. Treat `__pycache__`, `.pyc`, and `.pyo` below the mounted skill tree as
   generated runtime artifacts, not canonical skill content. Skill verification
   ignores them; run skill-hosted Python with `PYTHONDONTWRITEBYTECODE=1` where
   practical so a read-only audit does not create permission-noisy artifacts.

## Production contract

- Bridge JSON modes are exactly `product_brief`,
  `product_brief_revision`, `studio_creative_generation`, and
  `studio_edit_learning`.
- Media mode is exactly `content_non_human_graphic_generation`; enhancement
  accepts zero or one validated square PNG reference and records its digest.
- PostgreSQL owns Projects, Sources, Briefs, corrections, approvals,
  project-scoped Studio creatives/files/assets/versions, append-only
  generation and learning runs, immutable edit checkpoints and skill snapshots,
  proposals/decisions, audit, graph lineage, and emergency control.
- Brief approval transactionally reserves the first creative. Restart recovery
  resumes queued composition, phone-image, and learning stages idempotently.
- Bare Studio mutation routes, `/api/v1/posts`, candidate/critic modes,
  historical schema adapters, and singleton assignment flows are absent.
- A completed structured bridge job can still be unusable when its response
  violates a renderer-only bound that was absent from the output schema. If the
  same Studio `ValueError` repeats against one `:attempt:1` job, do not reset or
  keep clicking Retry. Verify the rejected field and schema constraint without
  exposing the full prompt/response, deploy the mirrored strict constraint and
  a versioned composition idempotency namespace, then allow at most one fresh
  corrective `:attempt:2` only after deterministic validation rejects a
  completed response. Transport/timeouts/provider failures must not trigger a
  new attempt automatically. Acceptance requires retrying the same failed
  creative to a valid draft, preserving its ID and append-only failed runs, and
  proving restart recovery does not enqueue duplicates.
- Apply that guard to every structured workflow, not only Phone Metrics.
  Product Brief/revision, both Post templates, Landing composition, and both
  learning skills require domain validators after provider-schema validation.
  Strict schemas and normalizers must consume the same bound/enum/pattern/
  length/privacy constants. The platform idempotency key must include the
  automatic canonical request fingerprint (mode, model, prompt, input, schema,
  and referenced-asset digests), be bounded to 240 printable characters, and
  change whenever any semantic dependency changes. Image generation and
  enhancement use the same fingerprint boundary. Reject a rollout that relies
  only on a manually bumped prompt version.
- Match Validation submission slots to the deployed bridge worker count. Keep
  the worker execution timeout explicitly bounded below the client deadline;
  verify both values in tests so queue wait cannot silently consume a second
  request's entire deadline.
- Require an explicit server-owned bounded reasoning effort for bridge workers;
  never inherit an ambient CLI setting. Verify the exact CLI override and keep
  domain-validation canaries as the quality gate.
- A workflow that repeatedly reaches the worker deadline after queue and
  reasoning controls are verified has an oversized or over-owned contract.
  Do not keep increasing timeouts or blind-retrying it. Move deterministic
  configuration/layout/routing/identity fields out of the model response,
  bound the source snapshot and recent lesson context, record only byte counts,
  and make runtime plus canary use one payload builder. Reject oversized
  contracts locally before they enter the queue; require the compact canary to
  finish on attempt 1 before promotion.
- Recovered entities must clear current top-level error fields while preserving
  append-only failure history. Never expose a provider HTTP body while
  diagnosing a status; keep only bounded status, job ID, and object ID.
- A Studio Save/Approve 400 is not non-mutating evidence. Compare the exact
  request time with immutable version/checkpoint counts and workspace-file
  digests before retrying. PostgreSQL derives `approved_version_count` from
  `universal_studio_versions`; its authority adapter must accept that service
  patch without attempting a nonexistent workspace-column update. Promotion
  requires both the loopback workflow and the database-adapter finalization
  regression. Reconcile the affected action once after rollout, require HTTP
  200 with no new version, then restart Validation and prove the version IDs,
  state/render digests, latest checkpoint, and recovery queues are unchanged.
  Both preserving deployers must reject any Studio checkpoint without a
  completed learning run before taking the authority snapshot: Validation
  restart recovery is intentionally mutating and would otherwise make a healthy
  rollout fail its own preservation comparison. Never bypass that comparison;
  let recovery finish on the current release, verify the queue is empty, and
  restart the candidate rollout from preflight.
- Telegram accepts only `/help`, `/status`, and `/stop`.
  Deployment verifies the existing bot identity with the read-only canary.
  Sending a test message requires explicit messaging authorization; deployment
  authorization alone does not enable outbound chat messages.
- A Landing create failure containing `badly formed hexadecimal UUID string`
  can originate from an internal graph-edge argument inversion rather than an
  invalid Project or Post ID. Check that the failed transaction added neither a
  `landing_workspaces` row nor relationship rows, inspect the deployed
  `DatabaseLandingAuthority._edge` call order, and preserve the Project for one
  post-fix retry. This incident does not justify a production reset.
- A repeated Landing Save 409 can be the aftermath of a successful server-side
  checkpoint whose response outlived the browser's generic request deadline.
  Compare the page `state_sha256`, `landing_workspace_files.updated_at`,
  `landing_checkpoints`, versions, and Gateway request statuses before retrying.
  Landing Save/Approve clients must share the existing bounded 480-second
  Gateway deadline because synchronous Landing learning may legitimately exceed
  15 seconds. Reconcile only an exact configuration/content match; otherwise
  preserve both the newer server state and the owner's pending browser input.
  Do not delete the completed checkpoint or reset the Project.

## Canaries and reset acceptance

Normal releases must use the tracked `scripts/release_ptw_fast.sh` entrypoint.
Never stream deployment control code into `bash -s` when a child command could
consume stdin. The tracked receiver accepts a bounded versioned stream of
checksumed image/file artifacts and explicit `REUSE` records. Every
`docker compose run` in a control path must use `-T`; the selective deployer
runs from a file, refuses active mutable operations, snapshots every
authoritative row whenever a service restarts, and restores both containers and
persisted per-component image references on any incomplete exit. The destructive
serial reset remains a separate, explicit owner-confirmed workflow. The fast
path must refuse when any repository migration is unapplied; do not use it to
bypass the backup-bearing in-place confirmation.
Exercise that migration preflight through the exact production Compose and
PostgreSQL transport before the first service is replaced. Static assertions
cannot validate `psql -c`/stdin interpolation. A preflight defect is a rejected
rollout: verify the previous component images remain live, correct it in source,
add a regression test, publish a new commit, and restart the deployment from
preflight rather than editing or bypassing the check on the server.
Treat the running service image or the root-only atomic
`.local/deployed-revision` as the deployed PTW revision; production Git HEAD can
already contain a candidate rejected by preflight. Do not advance that state
file until all checks accept the release. A preflight failure must not invoke
rollback because no cutover began. Preserve checksum and architecture checks,
and allow a retry to send `PRESENT` only when the target image already exists
with the exact source-revision label. When an incomplete Studio learning
checkpoint is blocked specifically by the old deterministic-response replay
bug, load the verified candidate Validation image first, run the tracked exact
checkpoint retry through normal domain services under the maintenance lock,
and require it to complete before restarting the release from preflight.

When a release originates in the hosted Commander checkout, treat its output as
a development handoff. Require a pushed immutable commit, a clean source tree,
the normal local and built-image verification, and explicit owner authorization
for deployment before any SSH or production mutation. Build Linux/amd64 images
outside the 1 GB VPS, transfer checksumed archives, and deploy only through the
tracked preserving or confirmation-gated in-place script. Hosted Commander must
not receive the VPS key, Docker socket, production environment files, or database
credentials. After a GOD-mode runtime change, acceptance must run a real private
chat that performs a harmless repository read, verify the isolated checkout is
clean, restart only `commander-god` under the maintenance lock, and confirm that
the completed chat and reply persist.

The hosted Commander release interface is the bounded exception to the manual
handoff. Owner Gateway must verify Firebase owner identity and App Check, then
forward the UUID-bearing one-click Deploy action to the separate
`commander-release` controller. That controller may lock, commit, and push the
isolated candidate branch, but it must have no Docker socket, production
environment, database, or VPS SSH key; `commander-god` must have none of the
controller/CI keys. The GitHub runner builds Linux/amd64 artifacts off-VPS and
may reach production only through the forced `ptw-release` receiver. Explicit
chat deployment instructions also authorize release without another confirmation;
the host persists the response and handoff before releasing the checkout lock.
All versioned PTW paths are eligible, including infrastructure and migrations.
Publish candidate source and an accepted-base request branch with only a bounded
manifest. Candidate workflow changes take effect only after acceptance. Verify
applied migration checksums against the accepted inventory; rehearse declared
transformations and previous-runtime compatibility on a disposable database,
retain a checksummed backup, and preserve undeclared business values. Keep the
previous accepted recovery tools, images, configuration and Hosting versions
until all checks pass; retain recovery files if restoration fails.
Acceptance requires the same maintenance lock, authority
snapshot, rollback, health/dependency/resource checks, deployed-revision update,
owner Hosting audit, mobile status recovery, and proof that both containers
remain free of the Docker socket.

Treat the forced receiver's final exit as authoritative even when the inner
preserving deploy reports success: verify the deployed revision before deciding
whether recovery means rollback or bookkeeping repair. Receiver functions run
with Bash nounset; declare positional locals on separate statements before any
derived local references them. Keep a contract test for that ordering so a
post-cutover cleanup or Hosting step cannot turn a successful rollout into a
false failed status.

Normal preserving deployments target 2–4 minutes for a single PTW component and
under 10 minutes when Validation/provider execution is required. Keep authority
snapshots, rollback, health/resource checks, and approved artifact verification.
Run the expensive live bridge/Pexels canaries and schema-bound Codex dependency
probe only when their owning Validation/platform components change; unchanged
provider releases use `audit_vps_owner_dependencies.sh --quick`. Stream only
changed image archives directly to the tracked receiver, retain old image
references for every reused component, and use the deployer's per-stage timing
output to identify regressions.

Migration-bearing preserving releases instead require the exact
`DEPLOY PTW IN PLACE` confirmation and
`scripts/publish_ptw_in_place_serial.sh`. Never bypass that gate with the
non-migration preserving script. Require `-T` on every Compose one-off. The
inner deployer refuses active mutable work, backs up PostgreSQL, fingerprints
pre-existing rows before and after migration and again on failure, and verifies
all restored application image tags. The outer deployer owns the whole release:
until every dependency/resource/OOM audit passes, any error or termination must
restore and verify all application and platform images plus their persisted
tags. An additive migration may remain after rollback; existing rows must not
change and the root-only backup remains the recovery authority.

Before a Validation or platform rollout, run real domain-validating canaries for
both Product Brief modes, Universal Post, Phone Metrics, Landing composition,
Studio learning, Landing learning, fresh image generation, one-image enhancement,
and Pexels.
Every structured canary must carry a fresh request fingerprint and complete on
attempt 1. It must also report valid prompt/input/schema byte budgets. The
Landing canary must use the exact runtime content-only payload, remain below its
stricter compact input/schema budgets, and prove that presentation state stays
server-owned. After an authorized clean reset
require zero Projects, Briefs, creatives, assets, versions, checkpoints,
generation/learning runs, proposals, decisions, skill snapshots, graph rows,
and every Landing workspace/file/asset/run/version/checkpoint/skill/proposal row.
Require `001_ptw_brief_v1.sql` and `002_ptw_landing_studio_v1.sql`, no retired Result/Post or legacy Landing tables/routes,
unchanged independent platform data, database-backed readiness, and the current
PWA cache.

After cutover exercise create Project/Brief → approve with template → automatic
creative composition/phone image → edit → Save learning → global decision →
Approve creative, then restart services and verify the same IDs/digests plus
empty recovery queues. Never claim readiness from health checks alone.
When a serial release schedules the resource follow-up, the transient systemd
unit is `ptw-validation-24h-audit.timer`; require `active/waiting` and a concrete
next elapse time. Checking a guessed timer name is not evidence of failure.

Owner-facing error acceptance also covers failure paths: each API or persisted
background failure shows what failed, why in plain language, the next safe
action, and bounded technical context without raw provider/5xx output.

## Instagram publishing and website Ads

- Consult `docs/architecture/meta-ads.md`. Verify publishing permissions and
  advertising permissions independently; workspace/export reads must not wait
  for remote verification. Real acceptance needs a selected approved version,
  an Instagram permalink, and a website ad verified PAUSED in Meta.
- Configure secrets only through `scripts/configure_meta_ads.sh` hidden prompts.
  Keep the production secret file's six-key contract compatible with rollback
  images. `META_INSTAGRAM_MEDIA_ORIGIN` is a nonsecret Validation Compose setting,
  not an additional production secret-file key. Loopback publishing requires an
  explicitly configured public HTTPS origin reaching the same local authority.
- When the organic configurator returns Meta HTTP 400 but a token-safe
  `GET /me/accounts?fields=id,name,tasks,instagram_business_account{id,username}`
  returns the assigned Page and linked professional account, do not keep rotating
  the token or retry a stale example Page ID. A system-user token can discover
  that binding through `/me/accounts` while Meta rejects a direct `/{page_id}`
  read. Organic configuration and runtime verification must use the discovery
  response, match the exact Page ID and Instagram username, and require
  `pages_show_list` alongside the publishing permissions. Never record the token
  or opaque paging cursors.
- Keep curl URL globbing disabled for Meta Graph queries containing nested field
  expressions such as `instagram_business_account{id,username}`. Without
  `--globoff`, curl expands the braces into multiple malformed field requests;
  the Page can still appear while the linked Instagram object disappears,
  falsely reporting that a valid assigned account is not linked.
- Keep the Validation process in GID `10001`, matching the root-owned Meta
  secret directory and mode-440 file written by the configurator. After the
  hidden prompt succeeds, verify only mount presence, numeric ownership/mode,
  process identity, and readability before checking the live connection; never
  print the file. A container restart cannot repair a UID/GID mismatch.
- Expose only the bounded opaque temporary JPEG route, never Studio files or
  metadata. Disable HTTP access logs that could retain bearer media URLs. Test
  expiry after completion and timeout through Gateway and Validation.
- Before a schema-five rollout, refuse active Instagram work and preserve all
  prior business tables, including Landing. Fingerprint the baseline column
  projection so an additive defaulted campaign objective does not look like a
  prior-row mutation. Exercise the exact SQL/psql transport against disposable
  PostgreSQL; do not weaken preservation checks or the in-place confirmation.
- A saved publish-start flag requires reconciliation, never automatic replay or
  a replacement post. Retain attempts and existing container/media IDs. Read
  externally activated ad parents without changing their status; new ads remain
  PAUSED and campaign identity includes project, objective, and categories.
