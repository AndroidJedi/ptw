---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW production across Commander, Product Brief Validation, Owner Gateway, project-scoped Studio, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency boundary.
---

# PTW VPS Operations

## Memory after an authored Post preview

Run the 1 GiB resource audit after warming the owner's actual authored Post
preview as well as after provider canaries. A cached cutout ONNX session can
retain hundreds of MiB of CPU scratch buffers after inference, leaving healthy
containers below the required memory reserve. Compare Validation's anonymous
memory and swap with a fresh-process opaque-image cutout probe; host RSS alone
can hide the allocation in swap. Disable the session's CPU arena and memory
pattern retention while keeping the pinned model and rendered pixels unchanged.
Require the Linux retained-memory regression, exact PNG digest comparison, and
the warm production resource audit. Do not lower the reserve, drop caches to
pass, remove unrelated services, or regenerate approved/source assets.

## Orphan exec metadata in host runtime memory

If healthy containers miss the idle memory reserve, compare `/run` inode counts
and `shmem_inode_cache` with live Docker exec IDs. Health-probe timeouts can leave
old PID files and closed FIFOs, matching
[Moby issue 48908](https://github.com/moby/moby/issues/48908). Do not infer low
memory from application RSS alone or erase runtime directories wholesale.
Use the tracked `ptw_runtime_exec_guard.py check` to inventory only the exact PTW
container allowlist. Its clean mode requires records at least one day old,
a non-live/non-reused PID, no active Docker exec ID, no open descriptor, unchanged
file identity and real root-owned PID/FIFO types. Retire the stopped exec through
containerd without `--force` before removing its files; file-only cleanup leaves
the shim process record in memory. Successful deletion may return the old exit
code (such as 137). It never kills processes or removes directories. The hourly installed guard takes the maintenance lock and
defers when PTW work is active; retain its live-PID/open-handle/age/path/race tests.
After installation, verify eligible/removed counts, container and bridge health,
unchanged Project authority, and the normal memory/storage audits. If an earlier
file-only cleanup lost the exec IDs, clear the accumulated shim records through
controlled restarts of affected application containers, after checking bridge
jobs, Commander turns/questions/handoffs, release state and both operation locks.
Compare PostgreSQL and Commander SQLite row fingerprints afterward. Keep engine
upgrades separate from this bounded recovery. A transient health timeout alone
is not a credential failure: preserve auth, restore accepted source/skills after
rejection, and confirm actual health recovery before a fresh release attempt.

## Image-worker temporary storage

The companion worker's private `/tmp` is a Compose tmpfs, independent of the
host's free disk. The former 64 MiB mount exhausted during a Daddy image save:
a shared Codex plugin cache used about 30 MiB, an isolated job home used about
34 MiB, and the saved PNG stopped inside IDAT at a 4 KiB boundary with zero
free bytes. The CLI returned success, so PNG checks at the worker boundary are
mandatory. Use the 256 MiB worker tmpfs and the pre-generation free-space guard;
keep the worker's 768 MiB cgroup cap and at most two media jobs. Confirm
`df -B1 /tmp` inside the worker and memory.current/peak/events while jobs run.
Host `df` and absence of OOM are insufficient. Never expand the mount without
checking two-job memory headroom.

For a failed image job, compare sanitized provider-start/done events with
file bytes/digest, PNG/CRC/pixel validation, geometry and asset-commit events.
`temporary_storage_full` means a guard or full tmpfs; the other bounded codes
separate structure, checksum, decode, dimensions and absent/failed saves. Keep
one rejected file per job root-only, size-capped and short-lived; do not copy
it into Git or public assets. Preserve the failed Daddy attempt and its
idempotency key. Deploy the compatible worker, Validation and Owner UI through
the preserving release, run a real bridge canary, then use one explicit
UUID-bound Retry for the named creative. Verify the saved asset, rendered
manual-edit draft, reload, and unrelated Project fingerprints before closing
the incident. Do not wait for or claim automatic Daddy AI visual review.
Daddy composition may legitimately use the structured bridge's one validation
correction for bounded copy; its release canary must verify a rejected-first,
completed-second receipt and final valid draft, not reject all corrections.
Keep first-attempt requirements for the unrelated contract canaries.

Before enabling two Landing image jobs, run the explicit
`scripts/verify_landing_parallel_worker.py` canary with the candidate worker in
the existing bounded companion container. Require no queued/running companion
jobs, the PTW maintenance lock, unchanged model/reasoning/output geometry, no OOM
counter increase and measured worker/host memory headroom. Each concurrent CLI
job needs its own writable temporary home and an isolated copy of the mounted
credential; never share generated-image directories or print credential contents.
The second normal worker is media-only and uses its own database connection with
`SKIP LOCKED`; total capacity remains at most two. Validate that both API and
worker retain the shared Compose environment when adding capacity settings.

Landing operation records require an additive migration. Both preserving release
guards and Project deletion must reject active operations. No asset backfill runs
during migration, reads or publication. An explicitly named refresh uses
`scripts/refresh_published_landing.py` with the exact Project, current published
digest and stable request UUID after local visual checks. It copies approved
settings/artwork to one replacement draft, verifies image hashes/bytes, uses normal
Save/Approve/Publish endpoints, retains the previous version, and compares all
other Landing application fingerprints. Never infer authorization to refresh
other Projects from one example.

For an explicitly requested live feedback correction, review the named published
snapshot first. `scripts/update_published_landing_feedback.py` takes its exact
Project/digest, a stable UUID and three bounded example cards. Run without
`--publish` for review, then publish under the maintenance lock through normal
Save/Approve/Publish. Preserve old versions, any original unsaved draft and
artwork; verify unrelated Projects. Deploy the compatible renderer/validator
first. When proof is absent, cards must contain factual product points or practical guidance without fictional customer speech; verified quotes stay in the evidence block.
Public asset URLs belong to the active version. After publication moves, prior
URLs may return 404. Verify preservation against the retained approved record
and selected digests, then hash the new public image bytes against those digests.
For newly generated marketing Landings, the Project composer fills editable
feedback cards; source-site testimonials and artwork never transfer as Project
content. For a renderer-only feedback correction, keep the runtime backend out of the
release plan unless its behavior must change. If a publisher stops reporting
after canaries, inspect the deployed marker, running image tags, maintenance
lock and target checkout before any retry. Passing canaries or candidate source
alone do not prove acceptance; terminate a stale local SSH transport only after
confirming there is no active remote release or lock holder.

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. Their authenticated structured/media bridge is the only generation
integration. Never move credentials between them or mutate platform data during
a Commander reset.

For ChatGPT/Codex authorization diagnosis, auth-only recovery, and promotion
into a complete compatible release, read
[references/codex-auth-production.md](references/codex-auth-production.md).

## Start safely

Validation shares the host `/run/lock/ptw-maintenance.lock` through a read-only
file mount. Keep that nonsecret lock readable by the unprivileged runtime;
readiness must reject a missing or unreadable configured mount.
Install the tracked `scripts/ptw-maintenance-tmpfiles.conf` as root-owned
`/etc/tmpfiles.d/ptw-maintenance.conf` and run `systemd-tmpfiles --create` on it
before enabling the mount. The boot rule recreates `/run`'s ephemeral lock
before Docker starts; never replace the lock inode while a release holds it.
Runtime HTTP writes hold a shared lock through request/background completion, and scheduled
Analytics holds it through its cycle. A release holds the exclusive lock:
writes return 503 with Retry-After, Analytics skips that cycle, and reads plus
authenticated emergency stop remain available. Public beacons rejected during
maintenance are not confirmed receipts. Do not disable the exact authority
snapshot comparison or delete live analytics to make a release pass.

If a long rollout rejects its authority snapshot, retain the hash-only before/
after diff before cleanup removes it. Separate changed/removed old rows from
new Landing events, rollups, insight snapshots and their graph rows. A 15-minute
Analytics milestone capture can otherwise race real media canaries. Restore
accepted source/skills and services after rejection, preserving any dirty hosted
checkout. A cancelled canary's orphan progress heartbeat may retain inherited
maintenance descriptors; verify rollback and the exact orphan parent/command
before terminating it. Never kill an active release or unrelated worker by name.

After long structured/media release canaries, the companion worker's 5-second
PostgreSQL health probe can time out briefly even though the jobs completed and
the worker later recovers. Inspect the bounded health-check exit/timing, worker
`/tmp`, memory/OOM events and database readiness. The selective deployer may
wait at most 90 seconds for two consecutive healthy worker states with real
database probes, then must still run the complete dependency/resource audits
and final image checks. A worker that fails that bound rejects the release;
never turn a failed health state into acceptance or skip the canaries.

For ENOSPC, a growing backup/log directory, or widespread health failures with
Owner HTTP 401, read [references/storage-recovery.md](references/storage-recovery.md).
Use the canonical storage guard for retention and bounded backup writes; a
one-time prune without repairing the accumulating writer is incomplete recovery.

Recovery Git checkouts can reset group-write permissions on changed skill
files. After restoring the accepted source, explicitly run the accepted skill
sync installer and the verifier from the restored live repository before
restarting its services. The verifier derives its repository root from its own
path, so never execute its archived recovery-snapshot copy. Keep candidate Git
hooks disabled; a healthy container alone does not verify the mounted skill view.
Keep hosted checkout history complete. A depth-one refresh at an unaccepted
candidate hides its accepted ancestor after rollback and prevents safe release
retry. Unshallow a clean legacy checkout from the canonical full source; never
rewrite or replace a checkout containing unfinished owner work.

When a wrapper receives Hosting followed by a binary image stream, reserve the
unread stream on a separate descriptor and give intervening Git/Docker/database
helpers `/dev/null` as stdin. Docker `exec -i` can consume a pipe even when its
command uses `psql -c`. Only the nested stream receiver gets the reserved input.
Acceptance must include a helper that deliberately reads stdin and a downstream
receiver that checks the exact preserved header and payload.

The existing Caddy host may be named `{$COMMANDER_PUBLIC_HOST}` and its admin
endpoint is disabled. Only activate a changed PTW host fragment, preserve the
shared security-header import and unrelated routes, and use validated restart
when hot reload is unavailable. The independent platform worktree may differ
only by the exact host block generated from the accepted PTW fragment; reject
all other tracked modifications. Recovery must support the same restart path.

Keep every host-executed release helper and audit anchored to the accepted
release archive, including nested helpers and skill installation. Disable Git
hooks during privileged cutover/recovery; installing a candidate script is not
permission to execute it before acceptance. Resolve hosted synchronization from
the accepted commit SHA, not a local branch name that may lag a detached rollout.

Disposable PostgreSQL tests must wait for a successful target-database query
over TCP. `pg_isready` can succeed against the temporary initialization server
before the requested database exists; that is not migration-test readiness.

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
6. Before receiving release images, reclaim only dangling images and builder
   cache older than 24 hours while holding the maintenance lock. CI builds
   release artifacts off-host, so that cache is rebuildable. Never prune tagged
   images, containers in use, volumes, databases, credentials, or Commander
   conversation state. Verify sufficient free space before retrying an ENOSPC
   rollback; do not blind-retry the same artifact stream.
7. The CI publisher must send SSH server-alive probes throughout silent live
   provider canaries. A completed platform job does not prove that the outer
   artifact transport is still connected. Treat a post-cutover SSH broken pipe
   as a failed release, verify rollback, and retain bounded keepalive regression
   coverage; never bypass the canaries to shorten the silent interval.
   Some CI transport boundaries still terminate a channel without visible log
   output even while SSH protocol keepalives succeed. Wrap the long structured/
   media canary with a harmless 20-second progress heartbeat, preserve its exact
   exit status, and stop/reap the heartbeat afterward. Never print prompts,
   provider output, tokens, or credentials as heartbeat data.
   Candidate-side release helpers cannot protect the rollout that installs
   them because pre-acceptance execution remains pinned to accepted helpers.
   The CI publisher must also emit a fixed local 20-second heartbeat around the
   complete SSH stream and propagate the pipeline's exact status.
   When the accepted request-branch publisher itself must change, bootstrap the
   exact clean, pushed candidate through `release_ptw_fast.sh`; do not weaken the
   immutable request branch by running candidate release code before acceptance.
   Promote canonical source only after the preserving rollout is accepted, then
   reconcile the matching durable Commander record.
   A Template Creation job can complete but fail PTW's domain validator. If the
   canonical system prompt is near its 6 KiB limit, appending the validation
   error can block the second attempt before it reaches the bridge. Keep the
   prompt immutable, put a bounded correction in server-owned input context,
   reserve room in the first request's input/total budgets, and bind corrected
   input into its distinct request fingerprint. Verify a near-limit prompt with
   invalid-first/valid-second responses; a provider or transport failure must
   still create no second job. A completed bridge job alone is not acceptance.
8. A candidate merge can reset modified skill files to Git mode 0644. Before
   dependency and skill verification, run the accepted
   `install_ptw_skill_sync.sh` against the candidate repository so Linux group
   ownership/write permissions are repaired without executing candidate release
   machinery. A permissions failure is a rejected rollout, not an audit bypass.

## Production contract

- Before a migration-bearing mobile release replaces Validation, compare its
  required JSON/multimodal modes and optional reasoning-effort declarations with
  the live companion bridge capabilities. The mobile publisher currently
  streams `REUSE` for every platform artifact; a new Validation requirement
  cannot be repaired by retrying the same mobile request. Build and publish the
  compatible platform revision together with PTW through the confirmation-gated
  serial in-place path. A failed `/readyz` after application cutover must roll
  back source, images, and Hosting; Docker `/healthz` may still be green. Keep
  Firebase auth-guard changes withheld until the application release is accepted.
- Bridge structured modes are exactly `product_brief`,
  `product_brief_revision`, `studio_creative_generation`,
  `studio_manual_edit`, `creative_performance_learning`, and
  `creative_visual_analysis`. Studio manual editing accepts zero to four ordered,
  digest-bound screenshots and must pass its real multimodal canary before release.
- Media mode retains the transport name `content_non_human_graphic_generation`.
  New Studio requests require `ptw.domain-image.v1` in bridge
  `image_generation_policies`; that version permits owner-requested people,
  devices and text/UI and accepts unchanged enhancements. Inspect both the PTW
  compiler and companion worker when a requested subject disappears. Legacy
  requests retain their legacy contract. Deploy the compatible companion before
  switching Validation; the fast release path that reuses platform images cannot
  add this capability. Exercise fresh and reference canaries without semantic
  rejection. Roll back the PTW application first if the companion must roll back.
  Enhancement accepts zero or one validated square PNG reference and records its
  digest; ephemeral reference retention and integrity checks remain mandatory.
- PostgreSQL owns Projects, Sources, Briefs, corrections, approvals,
  project-scoped Studio creatives/files/assets/versions, append-only generation
  runs, immutable edit checkpoints, Analytics snapshots/rollups, frozen
  performance runs, reviewed typed skill snapshots/decisions, audit, graph
  lineage, and emergency control. Historical Save-era learning rows are inert.
- Brief approval transactionally reserves the first creative. Restart recovery
  resumes queued composition and phone-image stages idempotently.
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
  Product Brief/revision, the active Phone Metrics Post and its manual Agent,
  Landing composition, and both
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
  Save/Approve checkpoints never gate deployment and have no restart learning
  recovery. Performance learning runs are explicit Analytics work: retain their
  frozen manifests and status, but do not mutate or resume them merely because a
  service restarted. Never bypass the authority preservation comparison.
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
  checkpoint whose response outlived the browser's request deadline.
  Compare the page `state_sha256`, `landing_workspace_files.updated_at`,
  `landing_checkpoints`, versions, and Gateway request statuses before retrying.
  Save/Approve no longer invokes learning or a learning-specific retry path.
  Reconcile only an exact configuration/content match; otherwise
  preserve both the newer server state and the owner's pending browser input.
  Do not delete the completed checkpoint or reset the Project.

## Canaries and reset acceptance

Normal releases must use the tracked `scripts/release_ptw_fast.sh` entrypoint.
When public measurement behavior changes, update both the build verifier and
deployed public-shell auditor before publishing. Retired consent-storage markers
must not reject the new bundle. Browser acceptance must still verify actual
request timing, prior refusals, privacy controls and form-data exclusion.
After a manual fast-release failure, verify the accepted source, hosted checkout
and both Hosting versions as well as service images. Image rollback can leave
candidate skills mounted. Restore only clean checkouts under both locks, disable
hooks, then use accepted skill-sync and Hosting recovery helpers.
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
Before publishing off-host image archives, check filesystem headroom as well as
memory and swap. Dangling-image and builder-cache pruning does not remove old
tagged releases. If tagged images are the pressure source, enumerate the images
referenced by every running and stopped container first; only under the
maintenance lock may `docker image prune -a --force` remove the remainder.
Never prune volumes or a container-referenced accepted/rollback image. Recheck
free space against the compressed artifact plus containerd ingestion headroom.
If image ingestion still reports `no space left on device`, require the receiver
to restore accepted source, services, skills, and Hosting and prove that the
deployed marker and migration ledger did not advance. After reclaiming only
unreferenced images, rerun the same verified publish job/artifacts instead of
creating a new candidate or bypassing any gate.
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
with the exact source-revision label. Historical Studio and Landing learning
rows are audit records only. Never retry, recover, or activate them; new
learning starts explicitly from Analytics and every candidate remains inert
until an owner review decision.

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
For a Templates built-in exact-version 404, verify that the requested version
and digest match the registered catalog before treating it as missing data.
Preview-render failure can leave the gallery entry visible without a persisted
built-in record. A fix must keep that exact GET readable with
`preview_status: failed`, preserve wrong-digest 409 and unknown-ID 404, and let
the owner retry the preview. Probe the exact Gateway route and query forwarding;
do not mutate Project or template authority to repair the read.
When an accepted Post exists in the production Templates gallery but is absent
from a Project template picker, query both the authoritative Post gallery and
the Studio catalog inside the same live Validation container. Compare exact
identity/version/digest sets and confirm the service is using its injected
database-backed Post registry instead of the static built-ins. After rollout,
apply every listed choice to a disposable production-code workspace, reopen it,
restart Validation and recheck the catalogs. Keep authored definitions marked
`supports_generation: false`; initial Brief composition and arbitrary authored
Landing promotion remain separate boundaries. Do not re-import, overwrite or
delete template authority merely to repair catalog wiring.
When a release retires or renames a navigation or provider surface, run the full
Owner Playwright suite before the first cutover; a focused replacement spec is
not sufficient. Search the remaining browser specs for the retired labels and
actions, update them to assert the new boundary, and make the live Owner auditor
require the new markers while rejecting the retired provider actions. Withhold
Owner Hosting when that full browser gate fails, even if the server cutover is
healthy; correct the tests and finish through a new clean, pushed preserving
release rather than bypassing the gate.
If unchanged browser coverage fails intermittently after an accepted backend
cutover, first verify the deployed revision and service health. Withhold Owner
Hosting, investigate the failure and rerun the entire suite in that exact clean,
pushed checkout. Only after the complete gate passes may the interrupted
publisher's remaining Owner Hosting and live-audit steps finish. A source or
test correction requires a new reviewed commit and preserving release.
Live Meta can filter automated browsers even when the SDK and pixel configuration
return HTTP 200. Verify application tracking intent separately, record actual
beacons when observed and keep receipt unconfirmed when filtered; do not bypass
the automation filter or substitute mocked calls for live delivery evidence.
If a fresh post-cutover media enhancement canary alone returns `failed`, require
the tracked deployer to restore the prior image and verify its deployed marker
and health before retrying. Inspect only the bridge job's bounded status; never
expose provider output or bypass the canary. At most one fresh full preserving
retry is appropriate for an isolated transient provider failure.
Apply the same bounded recovery to an isolated structured canary timeout: confirm
the job reached a terminal timeout status, verify source, service-image, accepted
marker and Hosting rollback, and only then allow the single fresh full attempt.
Do not resubmit while the original provider outcome is uncertain, change model or
reasoning settings to pass a canary, or skip any acceptance gate. Record the failed
attempt and successful acceptance separately in the incident log.
If a later fresh Landing canary reaches the same worker deadline, stop unchanged
release retries. Keep the accepted release live, compare bounded prompt/input/
schema sizes and worker timing with the one successful run, then repair the
runtime and canary's shared Landing contract in a reviewed revision. A healthy
bridge worker or one prior successful canary does not authorize skipping the
fresh release gate.
When comparing these jobs, query only mode, status, error class, elapsed time,
model/effort and byte counts; do not print private payloads. Two exact 360-second
`TimeoutExpired` jobs beside a 40-second success with the same roughly 7 KiB
prompt, 7 KiB input and 3 KiB schema indicate intermittent execution, not a
confirmed malformed response. Keep the model/low reasoning setting. Simplify
the shared runtime composition contract, prove it with fresh local calls, and
rerun the complete fresh release canary. Before retiring historical App Showcase
choices, export and digest-verify each production Landing as a private JSON
backup; preserve legacy reads for currently published v2 pages.
When two fresh structured canaries need the same corrective domain validation,
inspect the bounded correction reason in the second bridge job, then repair the
owning prompt or contract in a new reviewed revision. Keep the first-attempt gate
and rerun the full acceptance path; repeated retries of the same artifact are not
a repair.
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
serial publisher runs the full Owner Playwright gate from its local release
checkout after VPS cutover. Before starting, verify that checkout's `.venv`
Python can import FastAPI and Pillow and run the full browser suite there;
another worktree's passing suite does not supply these fixtures. If a missing
local dependency stops the publisher after the deployed marker advances,
verify the exact live revision, migration, service health and unchanged source;
repair the local environment, rerun the entire browser gate, then finish Owner
Hosting and its live audit. Never treat that local test-launch failure as proof
of a VPS rollback, or publish Hosting before the full suite passes.

The inner deployer refuses active mutable work, backs up PostgreSQL, fingerprints
pre-existing rows before and after migration and again on failure, and verifies
all restored application image tags. The outer deployer owns the whole release:
until every dependency/resource/OOM audit passes, any error or termination must
restore and verify all application and platform images plus their persisted
tags. An additive migration may remain after rollback; existing rows must not
change and the root-only backup remains the recovery authority.
Accepted selective releases can leave Commander, Validation, and Owner Gateway
on different versioned tags. The serial/in-place preflight and rollback must
therefore capture and restore `PTW_COMMANDER_IMAGE`, `PTW_VALIDATION_IMAGE`, and
`PTW_OWNER_GATEWAY_IMAGE` independently; never require one shared legacy
`PTW_IMAGE_TAG`, and never restart an unchanged GOD service merely to normalize
tags. Retagging preserved platform archives for a new serial release is allowed
only when their exact revision bundle and image bytes are retained.

Before a Validation or platform rollout, run real domain-validating canaries for
both Product Brief modes, the active Phone Metrics Post and its manual Agent,
Landing composition, Studio learning, Landing learning, fresh image generation,
one-image enhancement, and Pexels.
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
creative composition/phone image → edit → Save with zero learning calls →
Approve creative → explicit Analytics run/review, then restart services and
verify the same IDs/digests plus empty generation recovery queues. Never claim
readiness from health checks alone.
When a serial release schedules the resource follow-up, the transient systemd
unit is `ptw-validation-24h-audit.timer`; require `active/waiting` and a concrete
next elapse time. Checking a guessed timer name is not evidence of failure.

Owner-facing error acceptance also covers failure paths: each API or persisted
background failure shows what failed, why in plain language, the next safe
action, and bounded technical context without raw provider/5xx output.

## Instagram publishing and manual validation

- Consult `docs/architecture/instagram-manual-validation.md`. Organic publishing
  and manual Post export must remain independent: unavailable direct-publish
  credentials cannot block copying tracked text or downloading an approved PNG.
- Configure organic Instagram secrets only through the existing hidden prompt.
  Keep its secret-file contract compatible with rollback images.
  `META_INSTAGRAM_MEDIA_ORIGIN` is a nonsecret Validation Compose setting.
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
- Before a schema rollout, refuse active Instagram work and preserve all prior
  business tables, including inactive Meta Ads and TikTok history. Exercise the
  exact SQL transport against disposable PostgreSQL; do not weaken preservation
  checks.
- A saved organic publish-start flag requires reconciliation, never automatic
  replay or a replacement post. Retain attempts and existing container/media IDs.
  Paid tests have no provider mutation or polling jobs: verify unique arm URLs,
  launch-kit integrity, CSV preview/confirmation, first-party event attribution,
  and the prepared → active → completed/abandoned lifecycle.
- Keep the approved-Post post-cutover canary aligned to mounted product routes.
  Under the manual Instagram boundary it must compare both `/instagram` and
  `/instagram-tests` source projections with PostgreSQL; `/ads` returning 404 is
  expected and must never remain a release-canary dependency.
