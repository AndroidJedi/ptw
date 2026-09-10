# PTW incident log

Updated: 2026-09-10

## 2026-09-10 — Studio learning replay blocked a guarded fast rollout

An owner Save persisted its Creative and immutable checkpoint, but learning
rejected a privacy-safe global proposal as though it contained Project-specific
content. The UI showed no error because Save itself had succeeded and the
failure remained in the queued learning state. A later release correctly
refused to restart Validation while that checkpoint lacked a completed learning
run.

The first Retry appended a second failed run but replayed the same completed
provider response. Studio learning used one checkpoint-wide idempotency key, so
deterministic PTW validation could never obtain corrected output. The retry now
keeps the same provider attempt after transport, provider, timeout, or
persistence uncertainty, while a prior `ValueError` advances the provider
attempt and includes only the bounded validation error as correction context.
Inspection of all four completed provider responses showed generalized rules
about logo visibility. The privacy filter had treated the generic asset slot
value `logo` as a private identifier. It now checks exact copy plus selected
asset provenance identifiers and still rejects IDs, digests, URLs, provider
identity, and owner visual direction without rejecting ordinary Studio terms.
The failed runs and saved Creative/checkpoint remain append-only and intact. A
tracked one-off command can recover that exact checkpoint through the normal
database and provider services before rollout.

The rejected release also exposed deployment bookkeeping defects. Its receiver
advanced Git before preflight, so later planning could mistake candidate source
for running source, and cleanup recreated old containers even though cutover had
not begun. Successful deployments now atomically record their exact revision;
legacy installs infer it from the running Validation image. Rollback is armed
only after preflight. Already loaded candidate images can be verified by amd64
architecture and source-revision label and reused without another upload.

Local verification passes all 220 Validation tests, 23 Commander tests (two
dependency-skipped locally), the Commander demo, shell and Python syntax,
canonical skill validation, release-contract checks, and whitespace checks.
The exact checkpoint completed on its fourth append-only learning run and
created one pending global proposal; the Creative remained unchanged. Release
`fast-release-20260910-64de1e8` then replaced only Validation and hosted GOD,
left all five unchanged application/provider images running, passed nine fresh
provider/media canaries, Pexels, dependency/resource, authority, immutable-Post,
and live Owner checks, and completed in 7m19s end to end. A post-restart query
confirmed the checkpoint remains completed and no mutable operation is active.
Status: resolved in production.

## 2026-09-10 — Hosted Commander turns failed at two nested runtime boundaries

The GOD-mode release passed service health, public authentication denial,
provider, dependency, resource, and Hosting checks, but its first real private
turn failed before producing a reply or editing the isolated checkout. The Codex
binary and published credential were readable. The missing contract was a
writable `CODEX_HOME`: the credential source is intentionally read-only, while
the CLI still needs private runtime files during ephemeral execution.

The runner now copies only the published `auth.json` into its persistent private
state before every turn, atomically refreshes that copy, and points `CODEX_HOME`
there. The credential source and standalone binary remain read-only, and the
isolated source checkout has no runtime `.env` files. A regression verifies the
first copy, credential refresh, private runtime path, and completed execution.

The credential repair allowed a real turn to reach the model, but its first Git
command then failed because the CLI's nested Linux workspace sandbox requires
namespace and mount operations denied by the deliberately capability-free
container. The hosted runner now uses Codex's execution mode for externally
sandboxed environments. This applies only to hosted Commander; the local runner
keeps `workspace-write` with shell network disabled. The container remains the
hosted boundary: read-only root, isolated checkout and state mounts, no Docker
socket or production data, dropped capabilities, resource limits, and a bounded
environment allowlist. Regression coverage distinguishes the two execution
modes.

Release `god-mode-sandbox-20260910-faf77f9` passed the preserving rollout and
all provider, Pexels, dependency, resource, authority, and approved-Post checks.
A real private hosted turn read `AGENTS.md`, reported the exact release HEAD and
a clean checkout, and made no edits. The same completed chat and reply remained
available after restarting only `commander-god` under the maintenance lock; the
checkout was still clean. Status: resolved in production.

## 2026-09-10 — Legacy editor Save rejected after successful read-only restore

The owner reported that Save creative edits disappeared after reloading. The
Gateway recorded three Save requests at 05:39, 05:45, and 05:47 UTC, all HTTP 409;
the latest stored save checkpoint remained from the previous day. Validation
had not restarted since the previous release. The changes were rejected before
persistence, rather than lost from a committed checkpoint on restart.

The previous compatibility repair correctly restored the original v8 files
without mutating PostgreSQL. However, the Creative service merged stored
metadata over the normalized renderer detail, replacing the editor's state
hash with its older stored hash. Checkpoint Save compared that hash directly
against the normalized hash, unlike the existing legacy-aware preview validator.
Read-only inspection of the affected Creative confirmed those hashes differ.

The local fix gives renderer fields precedence in editor responses and uses
the existing bounded state validator for Save/Approve, including clients already
holding the verified older hash. An explicit unchanged legacy Save persists the
normalized files before advancing metadata. GET remains read-only; actual stale
edits still fail closed. Tests cover edited and unchanged Saves, fresh adapter
and service/cache restoration, completed learning and checkpoint lineage, no
duplicate checkpoints, and unchanged immutable PNG bytes. The standalone
`scripts/verify_studio_save_restart.py` runs real HTTP/domain/database operations
against an automatically created and removed disposable PostgreSQL instance.

Separate latency evidence: one Creative GET returned Gateway 503, while later
internal reads took 0.066 seconds for Projects and 0.763 seconds for the Creative.
The 961 MiB VPS had 164 MiB available and 617 MiB swap used during inspection.
These observations justify resource investigation but do not prove that memory
pressure or the image-generation lock caused the original timeout.

The owner also reported seeing no error. Both Post editors placed action errors
above the template selector without moving focus or scrolling, so a failure
could remain outside the mobile viewport. The local UI now places feedback
beside Save, focuses and scrolls to errors, retains pending edits, and tells the
owner to copy them before reloading. Preview failures have a separate display
and cannot replace a Save error or negate confirmed persistence. Both templates'
Save/Approve deadlines now match the Gateway's bounded 480-second learning
deadline. Candidate shell cache v5 and the build marker identify this UI fix.

Verification: 218 local Validation tests, 21 focused Linux-image Studio tests,
18 built-image Commander tests plus demo, disposable PostgreSQL Save/restore,
canonical skill validation, and whitespace checks pass.
The companion UI passes 88 web unit tests, 78 mocked browser/UI flows, production
build verification, and the deterministic Studio visual audit. Actual delayed
409 screenshots were inspected at desktop/360px/iPhone WebKit; feedback is in
view with no horizontal overflow and the pending headline remains intact.

Release `studio-save-20260910-2d18dfc` passed the preserving rollout, provider,
Pexels, dependency, 1 GB resource, approved-Post, and live Hosting checks. Owner
cache v5 is live. A bounded unchanged Save normalized the affected legacy
workspace, retained its state and both immutable approved version/render hashes,
and completed one learning checkpoint. The same state, checkpoint, versions, and
renders survived a Validation restart; a second identical Save returned HTTP 200
without another checkpoint or version. Rejected browser edits were never stored,
were not recoverable, and were not invented.

## 2026-09-09 — Legacy Post reads failed after renderer schema uplift

The first full Instagram release preserved all prior database rows and PNGs,
but its authenticated Post-derived workspaces returned HTTP 409. The stored
Phone Metrics configuration was v8; normalization to the current editor schema
changed the computed state hash before the database adapter verified the
original snapshot. The bounded legacy hash matched the stored digest exactly.

The database restore now uses the existing legacy-aware state validator and
never persists an existing workspace during reads. Only explicit owner mutations
write the normalized state. Regression coverage checks repeated restores,
unchanged stored files/digest/approved PNG, and rejection of changed content.
Both preserving deployers now require authenticated Ads/Instagram source reads
and PNG digests to match PostgreSQL before reporting success. The new canary is
read-only and does not require Meta credentials.

The final Hosting audit also observed a transient HTTP-200 HTML SPA fallback at
a newly published hashed App URL. It passed once assets propagated; the auditor
now requires JavaScript MIME inside its existing bounded retry window, covered
by a fallback-then-JavaScript regression. Security marker checks remain required.

Verification and release: 217 Validation tests and 18 built-image Commander tests
pass. The compatibility release `instagram-restore-20260909-a4af6b2` passed both
preservation comparisons, all nine fresh generation canaries, Pexels, dependency
and resource audits, and authenticated access to the existing Project's two
approved PNGs in both Ads and Instagram. Their digests match PostgreSQL, and the
current published Landing resolves correctly. All six services are healthy;
Owner cache v4 and both Hosting sites are live. Meta credentials remain absent,
so no real Instagram publication or paid-ad creation is claimed.

## 2026-09-08 — Monolithic Landing composition repeatedly exhausted the worker deadline

**Symptom:** expanded pre-cutover canaries passed all retained structured and
media modes, but post-cutover Landing composition alone failed at the worker
deadline. It failed once at 300 seconds, again after the bounded worker timeout
was raised to 360 seconds, and again with explicit server-owned low reasoning.
Each preserving rollout rejected the candidate and restored the prior images;
the owner Creative and append-only state were unchanged.

**Cause:** the Landing model contract asked one structured call to return both
marketing content and the complete renderer configuration while also receiving
the live catalog, frozen Post configuration/assets, defaults, and skill
documents. Queue alignment, authentication, schema validation, and reasoning
were healthy. The repeated exact-deadline signature isolated excess contract
shape and model ownership, rather than a data, auth, or recoverability problem.

**Durable fix:** Landing composition v5 makes AI responsible only for strict
bounded content. The server preserves configuration, layout, theme,
presentation, components, image styles, phone layout, routing, Natal identity,
and asset policy. One canonical payload builder is shared by runtime and release
canary; it sends the approved Brief, bounded frozen Post copy, current content
defaults, and at most eight recent lessons per scope, never the live catalog,
Post configuration, or assets. Append-only learning history is retained. The
bridge now rejects any structured contract over 512 KB before submission and
records only prompt/input/schema byte counts. Landing has stricter compact
canary limits. Both incident skills now route repeated deadline failures to an
AI/server ownership split instead of longer timeouts or blind retry.

**Verification:** unit coverage proves content-only schema enforcement, AI
configuration rejection, exact preservation of current server configuration,
bounded lesson context, exclusion of catalog/config/assets, pre-submission
contract rejection, and byte-count provenance. All 169 Validation tests pass
(162 in the Git-free production image plus seven Tune tests in the same image
with ephemeral Git), together with 15 Commander/deployer, 6 Gateway, 72 web
unit, 67 browser, two build, four-migration idempotency, syntax, compilation,
and whitespace gates. The deployer tests cover active-work refusal, `-T`,
failed-path authority fingerprints, full app/platform rollback verification,
persisted-tag restoration, and refusal to bypass the backup-bearing path when a
migration is pending. The live preserving rollout at PTW revision
`153b1dc6417a4c26b36ca9af4f8aac5d00d8b591` completed without a migration or
reset. Fresh jobs 514–522 all completed on attempt 1; the compact Landing
contract was 8,444 bytes. Full-row authority was unchanged, all six services are
healthy on `contract-budget-20260908-153b1dc`, and the exact affected Creative
retained its ID, draft status, state digest, zero immutable versions, and five
append-only generation runs across a controlled Validation restart.

The first promotion attempt also exposed a release-control defect before any
service cutover: `psql -c` did not expand the migration-name variable in the
new pending-migration guard. The fail-closed preflight left production on all
six prior images with no database change. The query now uses stdin SQL, the
static regression forbids the broken `-c` form, and both incident skills require
an exact-production preflight plus a new tested commit instead of an interactive
VPS bypass. Scheduled monitoring is checked by its real transient unit,
`ptw-validation-24h-audit.timer`, which is active/waiting for the 24-hour audit.

## 2026-09-08 — Phone Metrics replayed a completed response outside renderer bounds

**Symptom:** the first approved Phone Metrics Post remained `failed` with a
`ValueError` saying that texture intensity must be between `0.04` and `0.24`.
Owner retries preserved the Post but repeated the same error.

**Cause:** the strict Studio generation schema described the field only as a
number, while the renderer enforced the narrower range. The provider therefore
completed a schema-valid response with zero intensity. Every retry reused the
same completed `:attempt:1` bridge job because the composition idempotency key
did not change, so no corrected composition was generated.

**Durable fix:** this is treated as a contract-drift class, not a one-field
exception. Provider schemas and runtime normalizers now consume the same domain
constants for Studio and Landing bounds, enums, colors, typography, fixed device
constraints, content lengths, and privacy-sensitive blank fields. Every
structured Product Brief, Studio composition, Landing composition, Studio
learning, and Landing learning call requires a deterministic domain validator.
Every local and production bridge request is keyed by a canonical fingerprint
of its mode, model, complete system prompt, input, output schema, prompt version,
and referenced asset digests; a contract change therefore cannot replay an old
completed response. Image generation and enhancement use the same fingerprint
rule. One fresh `:attempt:2` is permitted only when a completed response is
rejected by deterministic domain validation; transport, timeout, cancellation,
CLI, and provider failures do not cause an unsafe blind retry. A successful
retry clears stale current error fields while append-only failed runs remain.
Raw provider HTTP bodies are never reflected. Both incident skills encode these
system-wide diagnostics, release gates, and same-entity recovery without reset.

**Verification:** focused provider and Studio tests prove strict texture bounds,
separate corrective idempotency keys, a successful corrected response, and no
second attempt after transport/provider failure. The complete Validation,
Commander, Owner Gateway, web unit/build/browser, schema-idempotency, skill,
compilation, whitespace, demo, and Studio visual checks pass. Pre- and
post-cutover production canaries completed Phone Metrics composition on fresh
`:attempt:1` jobs and passed image generation, exact-reference enhancement,
Pexels, dependency, and resource audits. Retrying the affected Post used the
new versioned key once, accepted texture intensity `0.08`, and completed its
phone image. The original three failed runs remain append-only beside the two
new completed runs. The exact Creative ID and state digest survived a
Validation recreate, with one Creative for the Brief and no approved version
invented. No reset ran.

The generalized follow-up adds automated fingerprint dependency, bounded-key,
mandatory-validator, no-blind-retry, stale-error cleanup, secret-reflection,
strict Landing schema, and media-integrity coverage. Release acceptance now
requires fresh attempt-1 real canaries for both Product Brief modes, both Studio
templates, Landing composition, Studio learning, Landing learning, new image
generation, and exact-reference enhancement before and after cutover.
Normal rollouts now use a tracked preserving deploy path rather than an
SSH-stdin control stream: Compose one-off jobs disable TTY/stdin consumption,
active mutations block cutover, every authoritative row is fingerprinted before
and after, any incomplete exit rolls back images and persisted tags, and the
destructive reset script is never called.
The bridge client also serializes submissions to the single production worker,
and the worker execution timeout is configurable only within a tested bound
below the client deadline. This prevents queue wait from consuming a parallel
request's entire timeout while still allowing the largest Landing contract to
finish.
Production bridge jobs pin the Codex reasoning effort to the explicit bounded
`low` setting rather than inheriting an ambient CLI default. Strict schemas,
domain validators, and attempt-1 canaries remain the acceptance authority.

## 2026-09-06 — Landing reservation passed a relationship label as a UUID

**Symptom:** creating the first private Landing from a valid Project and
approved Post returned HTTP 400 with `badly formed hexadecimal UUID string`.

**Cause:** the PostgreSQL-only Landing reservation path called the graph-edge
helper with `relation` and `target_id` reversed for the approved Post lineage.
It therefore attempted to parse the literal relationship name `derived_from`
as a UUID. The local loopback path used the correct ordering, so existing local
workspace tests did not exercise the production failure.

**Durable fix:** corrected the database graph call and added a database-path
regression that asserts the Project `contains` edge and both Brief/Post
`derived_from` edges by semantic argument position. The Owner Console incident
and VPS operations skills now route this exact UUID signature to graph-edge
ordering and require rollback verification before retry, without resetting the
Project.

**Verification:** 128 Validation tests, 10 Commander tests plus demo, 4 Owner
Gateway tests, 58 web tests/build, 48 browser checks, schema idempotency, the
Studio visual audit, compilation, skill validation, and whitespace checks pass.
The versioned production rollout preserved the database. Retrying the same
approved Post returned HTTP 202, persisted the three typed lineage edges, and
completed composition plus both visuals; a duplicate reservation returned the
same Landing ID without creating another row. The draft and exact asset/state
digests survived a Validation restart with an empty recovery queue. The full
dependency audit, schema-bound worker probe, public Hosting boundary, live
Pexels canary, and 1 GB resource audit pass. No reset ran.

## 2026-09-06 — HTTP 200 masked a failed structured provider execution

**Symptom:** the project Brief list returned HTTP 200, but its persisted Brief
was failed after repeated `structured bridge request N failed` attempts. The UI
showed an internal bridge string without explaining that the successful HTTP
response represented only a successful read or how the owner could recover.

**Cause:** all containers were healthy and the auth service passed its working
test, but a benign probe using the worker's exact schema-bound Codex execution
path returned unauthorized. The worker used a single-file bind of the primary
credential; Codex atomically replaced that file after device login, leaving the
running worker pinned to its stale inode. The frontend also normalized transport
errors only partially, treated a readable failed entity separately, and omitted
the persisted Landing generation error.

**Durable fix:** centralized localized API failures into outcome, explanation,
safe next action, and bounded technical context; applied the same contract to
persisted Brief, Studio, phone-image, Landing, and Landing-learning failures;
and suppressed raw 5xx/provider details. The auth service now keeps the primary
credential root-only and publishes a separate copy through a dedicated directory
mount that remains current across atomic replacement. The production dependency
audit compares the handoff internally and runs a token-safe schema-bound worker
probe. Both incident resolver skills record the HTTP-200/failed-state and stale
single-file-mount diagnoses before any generation retry.

**Verification:** 58 web unit tests, 48 browser checks, the production web build,
10 Commander checks, Commander demo, 38 platform tests, skill validation, script
syntax, and whitespace checks pass. The public Hosting audit confirms Landing
and the actionable-error markers. Production auth reports `authorized`/`passed`;
the dedicated published credential matches the worker mount; the schema-bound
worker probe and complete dependency audit pass. One explicit retry changed the
same Brief from failed to completed: its third append-only attempt and latest
structured provider invocation are completed, with document digest, quality
gates, and completion timestamp present. No reset ran.

## 2026-09-06 — Mixed production release broke generation, Landing, and ChatGPT authorization

**Symptom:** a Brief remained readable over HTTP 200 but its persisted state was
failed with `structured bridge request N failed`; Landing was absent from the
navigation; and ChatGPT Authorization remained required while Refresh appeared
to do nothing. An earlier request to the retired Studio route also returned 404.

**Cause:** production combined stale and incompatible Commander/platform/web
releases. The bridge job number was misread as an HTTP status, the deployed
database did not contain the Landing migration, and the live bridge exposed the
wrong mode set. Device login also lacked a pseudo-terminal and outbound network;
ANSI styling hid its one-time code, login status did not prove model execution,
and the regenerated root credential was unreadable by the non-root worker.
Finally, the current Codex JSON stream did not expose nested image-tool arguments,
so the old enhancement proof rejected a valid observable flow.

**Durable fix:** deployed one versioned compatible set for Commander, Validation,
Owner Gateway, platform API/worker/auth, both schema migrations, and Firebase
Hosting. The private auth service now uses a pseudo-terminal, outbound edge
access, ANSI-safe parsing, bounded real-request retries, and a root-owned
group-readable credential handoff to the non-root worker. Enhancement acceptance
uses exact private reference validation plus a distinct output digest. The
serial publisher stops before reset whenever provider canaries fail. The
owner-confirmed irreversible reset ran only after every canary passed.

**Verification:** all six services are healthy on the same release; exact bridge
capabilities, ChatGPT/Codex working authorization, secure worker credential
readability, all structured/media/Pexels canaries, public Hosting markers, App
Check/CORS/auth boundaries, schema idempotency, local suites, Commander demo, and
skill checks pass. The reset left every Brief, Studio, Landing, and graph business
table empty while the independent platform database snapshot remained unchanged.
Both emergency stops are false, the resource audit passed, and its 24-hour
follow-up timer is active.

The retired Social posts/Result incident history is available only in Git
history. Record future Product Brief, Studio, Owner Gateway, Firebase, Commander,
or Telegram emergency incidents here with symptom, cause, durable fix,
verification, and the narrowest reusable skill update. Never record secrets or
ephemeral release hashes.
