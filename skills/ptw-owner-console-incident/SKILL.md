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
   terminal, and Firebase `/__/auth/` helper traffic must never enter a cache.
7. **Deployment state:** compare Git HEAD, VPS HEAD, build hashes, Compose
   interpolation inputs, and live assets. A healthy shallow endpoint or clean
   source tree does not prove dependencies are usable.
8. **Service bridges:** when Ideas says “Idea Laval service is unavailable,”
   authentication already passed and the gateway caught an HTTP transport
   failure. Run `scripts/audit_vps_owner_dependencies.sh` on the VPS. Check the
   Idea container, loopback health, shared-network DNS, then the token-protected
   run-list call from inside Owner Gateway. “Bridge is not configured” and an
   upstream 403 are different failures; do not rotate tokens blindly.
9. **Host pressure:** if public HTTPS and SSH both accept TCP but stall before a
   response/banner, use the provider recovery console to inspect load, available
   memory, swap, disk, and bounded container state. A cached Hosting shell can
   remain healthy while the 1 GiB VPS is temporarily unable to serve API or SSH.
   Do not recreate healthy services or rotate credentials until this boundary
   is distinguished.

For Laval stage inspection, a selected card plus “artifact not created” does
not prove PostgreSQL lacks the artifact. Confirm the `/show` response and the
`laval_stage_runs.artifact` presence separately; browser request failures must
be rendered as failures, not as an empty artifact.

For a completed Laval run whose opportunities or finalists read like templates,
do not diagnose model quality from the artifact text. Compare the run-level
`quality` object with bounded `laval_llm_invocations` counts. Zero `success`
with `fallback`/`failed` rows means the provider never produced the shown
analysis; a completed stage only proves that an artifact was persisted. A
strict-schema bridge rejection is identified by validating every nested object
has explicit properties, all properties required,
`additionalProperties=false`, and every array has `items`. Live Laval must fail
closed on either provider or semantic-validation failure, and Final Shortlist
must refuse graph publication unless all mandatory language stages are
model-backed. Preserve old artifacts as history, but require the owner UI to
show an invalid run warning, per-stage model state, a readable summary first,
and raw JSON behind disclosure. Never relabel fallback candidates as finalists.

For a Branding tab that shows `provider unavailable` and no selectable case,
inspect the two boundaries independently. Production Branding reuses the
existing ChatGPT-authenticated Codex bridge; do not require a second
`OPENAI_API_KEY`, copy its refresh tokens, or substitute fixture output. The
bridge contract must expose the exact Branding structured modes plus one
`gpt-image-2` `$imagegen` call transported through the immutable Commander asset
volume. Case selection is based on a completed live Idea case, not on its
evaluation verdict: a case with zero surviving theses must remain selectable,
show every assessed thesis and verdict, and state that Branding will use the
original idea, mechanisms, and sourced evidence. Before claiming Branding
usable, run the VPS dependency audit with `PTW_REQUIRE_BRANDING_READY=1`; it
must require provider readiness, the established bridge credential source, and
at least one selectable case.

For a Natal landing action that creates a plan but does not build, or opens
unrelated Commander tasks, verify the Landing tab is using the dedicated
landing-build API rather than a Commander plan. A production build must fail
before persistence unless the bridge advertises `natal_landing_revision`, then
move through revising, building, publishing, and published. Feedback belongs to
the exact immutable published artifact and must be append-only skill memory;
every later revision snapshots the feedback UUIDs it consumes. Verify all three
templates remain selectable after every publication and that switching or
reapplying a template creates a new revision for the same Idea evaluation.

For a Branding timeout after logos are already visible, inspect the persisted
run, stages, provider tasks, and active-operation guard before calling it stuck.
`awaiting_review` with `OWNER_REVIEW` paused is the intentional owner boundary,
not a failed worker: label it as waiting for all three logo reviews. Distinguish
the pipeline's one fresh structured-output retry from the browser's HTTP
deadline. Never automatically repeat a timed-out review, approval, or other
mutation because it may already have committed. The timeout banner must include
a working action that safely reloads the run/list projections and must say the
server state may already have changed; a message that tells the owner to retry
while rendering only a dismiss button is a release blocker. Branding emits no
general Telegram notification, so verify its web state instead of inferring a
missing or unexpected Telegram message from the run transition.

For Branding review complexity or mobile lag, count visible primary actions and
logo asset requests before changing provider/runtime state. The normal review
screen renders one logo, one text area, and one dynamic CTA; it does
not mount the annotation canvas, request the same immutable PNG twice, require
a numeric rating, or preload all three logos. Store text-only feedback as a
truthful nullable rating and append a zero-delta text-feedback WeightUpdate;
never synthesize a neutral owner rating. A non-empty comment is a correction:
the CTA must say that it regenerates, stay on the same logo, visibly show work,
and replace the current immutable Creative only when the new revision completes.
An empty field is explicit approval and advances. A comment must never silently
count as approval or expose final direction selection. Keep run switching, ten
stages, provider/cost facts, artifacts, and deliberate rerun behind disclosure.
After all three current logos have explicit approval, show direction selection
with one approval CTA, then one download CTA after assembly. Cover correction,
restart/retry, and approval at 360 px and iPhone WebKit.

For a Branding screen that appears to have changed projects or lost history,
do not infer project identity from the newest `brand_runs.created_at`. Group by
the stable `source_laval_run_id` Brand Project identity and inspect its ordered
run versions, kit versions, active approved kit, and post-kit logo revisions.
The screen must anchor the source Idea and active kit/logo even when a direct
link focuses a paused draft. Label completed v1 and paused Draft v2 as one
history. Post-generation consumers resolve the single active approved kit by
project; never ask the owner to manage its UUID. A second initial create with a
new request ID is an error; only an exact idempotent replay may return the old
run. A deliberate research rebuild requires `intent=full_rebuild`, explicit
confirmation, and a retained request ID.

For a logo correction that only changed colors or ignored requested letters,
compare the persisted owner feedback, revision plan, source digest/path,
provider task payload/result, reference trace, and compliance row. Owner
corrections override soft direction constraints such as `text-free` or `no
letters`; reject contradictory planner output before generation. Exact text
such as `PTW` must use the code-owned bundled-font lettermark renderer, not
probabilistic image typography. A `reference_edit` must digest-check the current
immutable PNG under the shared asset root, pass that exact path as
`referenced_image_paths`, and retain proof from the actual image-tool event.
A prompt containing the path is not proof. Reject unchanged or color-only
results for structural instructions, permit at most one fresh automatic retry,
and keep the old Creative and kit active on failure.

Post-kit review must render immutable Before and After assets plus the exact
feedback, strategy, proposed version, and compliance status. Generation never
approves or activates the candidate. Rejection leaves the prior kit active;
approval creates a superseding kit only after graph and local persistence can
prove `supersedes`, `derived_from`, `evaluates`, `contains`, `generated`, and
`adjusts` lineage. Asset responses stay authenticated and `private, no-store`.

For a paused Branding run whose active stage still says `running`, audit the
timestamps of the run action, stage, and provider task. A result completed after
pause is retained, but both run and stage projections must remain paused and
startup must not resume them. Explicit resume must reuse the completed provider
task with unchanged `request_count` and stage attempt; a second provider job or
charge is an incident. Reconcile only the inconsistent stage projection—never
resume the run as part of repair.

For a failed Laval run, the owner must not need SSH or an agent to recover it.
Verify the visible error report includes the exact stage/attempt, bounded error,
failure time, provider-task counts, persisted remote-ID count, recorded cost,
and an explicit **Resume saved work** action. Resume must append the authenticated
Firebase actor to `laval_run_actions` and preserve submitted provider IDs;
deliberate rerun is a different action that invalidates downstream artifacts.
On the 1 GB production profile, do not expect an automatic terminal Telegram
notification or a web-triggered status notification: outbound delivery is
retired, the web control is hidden, and cached calls return HTTP 410. Verify
instead that unpublished Telegram rows are cancelled without deletion and that
emergency `/help`, `/status`, and `/stop` remain available through the sole
platform poller.

When semantic validation rejects a model response for unknown evidence IDs,
compare the rejected IDs against the complete serialized bounded context, not
only a normalized parent's top-level `evidence_ids`. Nested complaint clusters
are deliberately supplied evidence and must belong to the validator's allowlist;
IDs absent from every supplied `evidence_ids` field still fail closed. Live
language calls receive one automatic retry in a distinct fresh ephemeral
session. Persist both invocation rows, expose a bounded row/count reason, and
treat the failed call as recovered only when the containing stage subsequently
completes with a successful response. Never erase the failed audit row or let a
recovered call make `attempted`, cost metadata, or session provenance untruthful.

For an old run whose visible blocker is Google Trends, verify the status API's
`resume_with_market_signals_available` flag and the owner-visible **Resume with
Market Signals** control. The action must go through authenticated Owner
Gateway routing, must not run automatically, and must preserve paid task IDs,
cost, evidence, and lineage. For Market Signal inspection, verify the UI shows
the stored version/formula, all six numeric components, raw counters,
`available` versus `no_data`, and evidence IDs. Never display or apply a hidden
coverage multiplier.

If the API reports `resume_with_market_signals_available=true` but the browser
still shows **waiting for Google Trends**, **Approve and continue**, a provider
wait button, or a retired Telegram-status action, treat the screen as a stale
pre-Market-Signals bundle. The corrected UI must expose exactly one continuation
action; approval and provider-wait controls are mutually exclusive with the
upgrade. Audit the live chunks, bump the shell cache, and verify the controlled
client reloads before changing run state. Telegram projections must deep-link
to the exact run so a newer default selection cannot impersonate the notified
run.

Web creation must be one visible create-and-start action. Regression coverage
must prove that one owner click first persists the run and then calls its
authenticated `run` action, defaults to automatic progression, and leaves a
recoverable, explicitly labelled not-started record if launch fails. Do not
describe `approval_mode=automatic` as proof that execution actually started.

If the owner asks to run the same PTW idea again, do not direct them to **New
Laval idea** or **Rerun**. Select the existing run and use **Resume with Market
Signals** only when its status response explicitly reports
`resume_with_market_signals_available=true`. Before the click, record safe
aggregate baselines: run ID, paused status, current stage, pipeline version,
active-run count, provider-task count, persisted remote-ID count, recorded-cost
count and total, evidence count, and lineage count. Never render remote task IDs
in UI, logs, or chat.

After the authenticated owner click, verify all of these boundaries:

1. The request is exactly `POST /api/v1/laval/runs/{run_id}/resume-market-signals`
   with Firebase ID token and App Check; it is not generic resume or rerun.
2. The same run now uses `market_signals_v2` and `live_market_signals`; ordinal
   stages 8-10 are Plan, Collection, and Gate, while completed earlier stages
   remain intact.
3. Exactly one `resume_with_market_signals` action carries the authenticated
   Firebase actor. Paid-task, remote-ID, recorded-cost, total-cost, evidence,
   and pre-existing lineage baselines did not decrease or duplicate.
4. `laval_llm_invocations` appends fresh stage rows with different local and
   provider session IDs and truthful `success/fallback/failed` outcomes. A
   standalone bridge canary is expected not to appear in this table.
5. Market Signal cards expose the exact stored formula/version, six components,
   raw counters, `available`/`no_data`, and evidence IDs. The score contains no
   `coverage` field or hidden multiplier, and finalists can complete without
   Google Trends.

The button starts work immediately after the owner confirms it. Do not click it
merely to test visibility; use read-only status inspection for that check.

Treat “Firebase ID token and App Check are required” as an incomplete request,
not a reason to relax authentication. The gateway uses one message when either
value is empty, so determine which browser header is missing. In the first
August 2026 regression, App Check was tree-shaken out because its public site
key was absent at build time. In the subsequent Overview load regression, auth
and App Check succeeded but the gateway had been recreated without the platform
PostgreSQL password and returned HTTP 500.

If iOS Safari returns from Google but the Owner Gateway receives no CORS
preflight or authenticated API request, keep diagnosis in the browser boundary.
Initialize Firebase Auth once with `initializeAuth`, explicit
`browserLocalPersistence`, and `browserPopupRedirectResolver`; do not call
`getAuth()` and then fire-and-forget `setPersistence()`, which can migrate the
session through IndexedDB during the redirect/pagehide lifecycle. Consume
`getRedirectResult()` from the mounted auth boot path independently of
`onAuthStateChanged()`, and bound both the boot wait and the ID-token/App-Check
wait so Safari displays a retryable error instead of an indefinite loading
screen. The service worker must return without handling every `/__/auth/`
request, including the top-level OAuth callback.

## Prevent recurrence

- Keep public browser configuration deterministic in source and App Check
  non-nullable in the API client.
- Keep Auth persistence deterministic before initialization, consume redirect
  results even when the Auth observer stalls, and give Firebase credential
  acquisition its own deadline before the HTTP request deadline begins.
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
- Treat a release with a disabled primary action as unavailable. Branding
  cutover must fail its readiness gate when the authenticated Codex text/image
  contract is missing, even if health, auth, Hosting, and database migrations
  pass. A working Laval bridge is not proof that its Branding modes and image
  artifact transport are exposed.
- Branding initial readiness and logo-revision readiness are separate
  compatibility levels during serial cutover. The compatibility release may
  accept a legacy five-mode bridge, but approved-logo editing must fail closed
  until the bridge advertises planner and reference-edit modes plus exact
  path/SHA-256 trace support. Restart Idea after the platform edit release so it
  re-reads capabilities before exposing the edit action.
- Exercise strict Laval schemas against the real bridge contract. A generic
  top-level object/array test does not prove nested Codex output schemas are
  accepted, and a deterministic artifact does not prove a model call occurred.
- Bump the shell cache when behavior must reach already-controlled clients, and
  make the build/live audit fail if the worker handles `/__/auth/` traffic.
- Update this skill and the current-state checkpoint with reusable evidence.
- On a 1 GB stall, use one locked serial SSH session after provider recovery.
  Inspect bounded process age/RSS, OOM history, swap, containers, and both
  PostgreSQL connection/size views before restarting anything. A sudden latency
  cliff after hours of normal service can be a stale child or accumulated
  connections, but this remains a hypothesis until those probes identify it.

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
