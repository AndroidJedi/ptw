# Operational incident log

Canonical record of deployment gaps and prevention rules. Do not store secrets.

## 2026-08-20 — Laval V2 YouTube observation mode was absent from the platform bridge contract

- Impact: the first real `mechanism_thesis_v1` run stopped safely at
  `YOUTUBE_OBSERVATION` after preserving 52 paid DataForSEO task IDs, 26
  YouTube videos, 25 independent channels, and USD 0.0372 actual cost. Both S07
  attempts received HTTP 400 before a platform job or provider session existed.
- Cause: Idea Laval defined 11 structured language modes, while the independent
  platform explicitly allowed only the seven pre-V2 modes. The missing S07 mode
  was rejected by request validation; the later mechanism extraction, thesis
  synthesis, and thesis falsification modes would have failed the same way.
  The exact S07 request was 138843 bytes, below the 1000000-byte limit.
- Correction: expose authenticated platform capabilities, allow all 11 modes,
  compare the bridge contract at Idea startup, block new live runs on any
  missing or unexpected mode, preserve bounded HTTP rejection detail, and
  attribute S07 execution to the LLM bridge instead of the YouTube evidence
  provider.
- Prevention: unit tests cover the exact 11-mode sets, all four V2 worker paths,
  malformed/unknown/oversized rejection, fail-closed live creation, invented
  S07 identifiers, recovery without repeated discovery or provider spend, and
  the owner resume proxy. The production dependency audit now fails closed on
  contract drift and release acceptance requires an out-of-run canary for the
  previously rejected mode before saved work is resumed.
- Verification: platform tests pass 26 checks; the disposable PostgreSQL Laval
  suite passes 55 checks including complete 22-stage and S07 recovery paths;
  Owner Gateway passes 20 checks; Vitest passes 17 checks; production release,
  canary, and saved-run recovery remain to be recorded.

## 2026-08-19 — Opportunity Matrix rejected evidence that its own context supplied

- Impact: live run `01a01a93-e248-7615-942a-f7e0ef1c780b` safely stopped at
  S07 after 12 successful language calls. Its USD 0.0372 paid search, 52 remote
  task IDs, and 506 evidence rows were preserved, but no opportunities or
  downstream shortlist were produced.
- Cause: the model returned ten schema-valid opportunities. Four cited nine
  evidence IDs from complaint clusters included in the exact dossier context;
  the application validator incorrectly allowed only the dossiers' smaller
  top-level `evidence_ids` arrays and rejected all nine as unknown.
- Correction: derive the evidence allowlist recursively from every
  `evidence_ids` field in the bounded supplied context, retain rejection of IDs
  absent from that context, add one fresh-session automatic retry for live
  semantic/provider failures, and report recovered versus unresolved attempts
  without erasing append-only audit history.
- Prevention: regression coverage must accept nested complaint-cluster IDs,
  reject invented IDs with bounded row/count diagnostics, prove two distinct
  sessions for one automatic retry, and keep a recovered retry verified while
  retaining the failed attempt. Production recovery must resume the same saved
  run and prove paid provider IDs, evidence counts, and cost do not duplicate.
- Verification: release `976d46a` and Hosting version `86239a8851ef08c0` are
  live. The owner-authorized resume completed the same run at 16/16 stages with
  16 successful required language calls, no fallback, and no unresolved
  failure. S07 completed on stage attempt 2; the audit retains the original
  failure, resume request, and completed retry. All 52 provider tasks and 52
  remote IDs were reused, evidence remained at 506 rows, and actual provider
  cost remained exactly USD 0.0372.

## 2026-08-19 — Completed Laval run displayed deterministic fallback as finalists

- Impact: the first completed live Market Signals run showed templated,
  irrelevant opportunity text and ranked it as a final shortlist even though
  none of its recorded language invocations succeeded. Paid search evidence
  was retained, but the resulting synthesis and published hypotheses were not
  trustworthy.
- Cause: each `laval_*` output schema constrained only its top-level
  object/array. Strict Codex output validation rejected the incomplete nested
  schema before inference, while live execution still permitted deterministic
  fallback and UI completion/finalist labels ignored invocation provenance.
  Loose SERP type inference also treated several community, grammar, synonym,
  and book pages as products.
- Correction: define complete strict nested schemas and semantic validators for
  all seven language modes; disable fallback outside fixture mode; block final
  hypothesis publication unless every mandatory live language stage is
  model-backed; exclude known non-product result classes; expose run/stage
  quality counts; render readable Ukrainian summaries with raw JSON collapsed;
  and preserve the old run as visibly invalid history.
- Prevention: acceptance must prove schema validity through the real bridge,
  exact query/operator/evaluation counts, supplied-ID integrity, failure before
  paid search when the first language stage fails, 0-success historical-run
  labelling, and the absence of finalist language on fallback artifacts.

## 2026-08-19 — Laval creation looked started while a stale legacy run looked blocked on Trends

- Impact: the owner selected automatic progression and pressed the live-run
  creation action, but the new run remained `pending` behind a second Start
  button. A separately selected legacy run still displayed “waiting for Google
  Trends,” a retired Telegram action, and a competing approval action even
  though the API already exposed the Market Signals upgrade.
- Cause: web creation and execution were two actions with ambiguous labels;
  automatic mode controlled only approval gates. The notification canary had
  projected a real historical run without a test label, and an already-open PWA
  tab retained the pre-Market-Signals UI, making the unrelated run look like the
  result of the new creation.
- Correction: make web creation create and start in one click, select automatic
  progression by default, label saved pending runs as not started, expose one
  mutually exclusive legacy continuation action, remove Trends-wait language,
  deep-link notifications to the exact run, and bump the shell cache.
- Prevention: browser coverage must assert the create-then-start request pair,
  exact-run deep links, and the absence of approval/provider-wait competition on
  eligible legacy runs. Never force a production notification canary against a
  real owner run unless the message is unmistakably labelled as a test.

## 2026-08-19 — Recurrent 1 GB VPS stall after normal daytime latency

- Impact: the Owner Console remained on “Завантаження…”, the gateway timed out,
  and SSH accepted TCP but did not deliver a banner. The same broad symptom had
  appeared the previous day after hours of normal service.
- Evidence: the earlier recovered sample had 57 MiB available, no swap, and
  load above 27. A stale Codex/Node child, stuck Laval thread, duplicate
  container, or accumulated database connections can cause the sudden cliff,
  but no single process is yet proven because this recurrence still requires a
  provider-console reboot and locked post-boot inspection. A disposable local
  full Laval run then revealed a concrete amplification path: the Idea store
  created more than ten thousand short-lived PostgreSQL backend PIDs by opening
  one connection per repository call.
- Correction: retain the 1 GB host and both PostgreSQL authorities, retire
  creative/outbound polling, add 2 GB swap only with 4 GB free disk, tune both
  databases, bound connection/browser waits, and reject overlapping Laval and
  Codex work. Idea Laval now reuses one process-level connection behind a lock,
  reducing the same 13-test PostgreSQL suite from about 63 seconds with a
  transport failure to about 11 seconds. Preserve all historical rows and
  source.
- Prevention: build Linux/amd64 images off-host and deploy through one SSH
  session holding `/run/lock/ptw-maintenance.lock`. Load one image and start one
  service at a time; never use background jobs, parallel shells, server builds,
  or multi-service Compose starts. Capture bounded PID/PPID/RSS/age, OOM, load,
  memory, disk, containers, database size/connection, swap, and 30-second
  activity evidence before calling the incident resolved.

## 2026-08-18 — Laval controls appeared inert during a transient VPS stall

- Impact: the already-rendered Ideas view accepted a stage selection but its
  artifact/export requests stalled. The real API error appeared above the
  mobile scroll position, so the inspector misleadingly said the artifact had
  not been created. SSH also stalled during banner exchange.
- Evidence: Hosting stayed healthy while public gateway and SSH requests timed
  out. On recovery without a restart, the 1 GiB VPS had about 57 MiB available,
  no swap, and recent load averages above 27. All services and stored artifacts
  were healthy afterward, so resource pressure is the observed correlate rather
  than a proven single-process root cause.
- Correction: surface API failures in a fixed in-viewport banner, distinguish
  load failure from missing artifact, persist evidence modes, and label the
  existing fixture run as a demo. Add provider-readiness and spend boundaries.
- Prevention: when both HTTPS and SSH accept TCP but stall, check host load,
  memory, and disk from the recovery console before rotating credentials or
  recreating healthy containers. Do not infer a missing database artifact from
  a failed browser fetch.

## 2026-08-17 — Telegram control surface retired in favor of owner web UI

- Impact: the growing Telegram command set was inconvenient for analysis,
  image-region feedback, documentation, live job output, and multi-step safety
  confirmation.
- Cause: notifications, emergency control, reviews, engineering execution, and
  system administration shared one text transport.
- Correction: Firebase-authenticated React PWA and Owner Gateway become the
  only normal control plane. The existing poller retains notifications plus
  `/help`, `/status`, and `/stop`; every other inbound command redirects to the
  web UI.
- Prevention: acceptance tests cover the exact three-command allowlist,
  unsupported-command non-mutation, deep links, owner-only web authentication,
  App Check, and emergency-stop persistence across restart.

## 2026-08-16 — Owner idea was queued but never entered a generation

- Impact: a long owner idea remained pending after G4 and only its first
  Telegram-sized chunk was stored. A `/run` sent during G4 returned `/status`
  without queuing G5, which looked like successful acceptance.
- Cause: owner submissions were sampled only at generation start; active-run
  commands were silently discarded by the process-local lock; and no durable
  multi-message draft joined Telegram-split text.
- Correction: active `/run [N]` atomically extends the persisted series; long
  submissions use draft/append/`/idea_done`; and owner injection creates an
  append-only replacement generation that carries the latest top candidates
  while recording the lowest candidate it replaces.
- Prevention: runtime tests cover active run extension, multi-part submission
  reconstruction, exact replacement lineage, restart persistence, and the
  user-facing acknowledgement. Deployed source must come from a pushed Git
  revision rather than image-only or dirty-checkout code.

## 2026-08-14 — Session decisions and execution state were lost after reboot

- Impact: a new Commander/Codex process could recover task acceptance but not
  the compact set of decisions, open work, deployment truth, verification
  evidence, and next action needed to resume safely. Operators had to replay
  conversational context and could confuse a merge with a verified release.
- Cause: durable task acknowledgement and graph state existed, but there was no
  versioned session-level resume record or startup integrity/freshness check.
- Correction: Commander now appends bounded PostgreSQL checkpoints with a
  server-computed checksum, restores the latest checkpoint at startup and for
  new sessions, exposes the startup canary in readiness, and provides a
  fresh-process verification command.
- Prevention: checkpoint fields remain minimal and secret-scrubbed; stale or
  corrupt state is explicit, required-checkpoint mode can block readiness, and
  Telegram acknowledgement plus live production verification retain their
  separate completion gates.

## 2026-08-14 — Workspace task acknowledgements disappeared after reboot

- Tracking issue: [GitHub issue #10](https://github.com/AndroidJedi/ptw/issues/10),
  kept open until the live post-restart delivery gate passes.
- Impact: PTW implementation tasks accepted in Codex workspace sessions could
  begin without a durable `TASK-<number>` registration and Telegram message
  containing the interpreted scope; reboot removed the volatile bridge state.
- Cause: workspace acceptance depended on the deployment runner's in-process
  path. Commander had durable Telegram outbox delivery for creative traffic but
  no repository-owned, transactional workspace acceptance boundary.
- Correction: Commander now atomically stores workspace task acceptance and a
  Telegram outbox item, exposes delivery status as a mandatory start gate, and
  records Telegram's returned message ID when the worker publishes the item.
- Prevention: after every reboot/startup, a fresh real task probe must pass via
  `commander.verify_workspace_ack`; process health or a simulated send is not
  sufficient. The incident remains operationally open until that probe is run
  against the established bot after restart.

## 2026-08-14 — Text hooks had no convenient feedback path

- Impact: `/creative hook [brief]` returned bare text. Reply-based `/feedback`
  could not resolve that message to its Creative UUID, and text-hook creatives
  had no contained component to receive a learning weight update.
- Cause: text-only delivery was added after the image feedback flow and did not
  carry forward its prompt, Telegram delivery link, or component lineage.
- Correction: text hooks now include a reply instruction and permanent Creative
  ID, record their delivered Telegram message ID, and contain a reusable hook
  component.
- Prevention: end-to-end tests reply to a returned text hook and assert both
  HumanFeedback and WeightUpdate entities; worker coverage verifies delivery
  linking for text creatives.

## 2026-08-14 — Task 48 merged but hook behavior was not deployed

- Impact: `/creative hook <brief>` still returned an image after Telegram said
  Task 48 was resolved.
- Cause: the implementation matched only the exact two-token command
  `/creative hook`; useful brief-bearing requests fell through to Story
  rendering. The runner also treated a GitHub main merge as proof that the
  unrelated production checkout had rebuilt, although no deploy pipeline ran.
- Correction: all `/creative hook [brief]` requests are text-only and select a
  matching stored research hook. Production was explicitly rebuilt and live
  behavior verified. The platform policy now marks main-only releases as
  deployment-unverified instead of claiming production completion.
- Prevention: regression coverage includes a brief-bearing hook request and
  asserts no photo outbox or PNG. Completion requires deployed behavior
  evidence, not only a merge SHA.

## 2026-08-13 — Feedback replies failed without a delivery-link row

- Impact: valid `/feedback <1-5> [comment]` replies could be surfaced by the
  forwarding poller as “creative service is temporarily unavailable”.
- Cause: reply resolution depended only on the post-send Telegram delivery
  mapping, although the generated message caption also carried the permanent
  Creative UUID.
- Correction: delivery mappings remain primary; when one is absent, Commander
  recovers the caption UUID and verifies that it identifies a stored Creative.
- Prevention: feedback reply tests cover mapped delivery and validated caption
  recovery paths.

## 2026-08-13 — `/task` executor failed before work and provided no control

- Impact: engineering jobs were accepted but failed when Codex initialized;
  the owner received neither immediate confirmation nor an interruption control.
  Creative validation failures were also flattened to “Creative service is
  temporarily unavailable,” including feedback requests.
- Cause: Codex's runtime home was mounted read-only, nested sandboxing was
  configured inside an already isolated container that disallows user
  namespaces, and Telegram queued jobs without an acknowledgement. The creative
  bridge treated every non-2xx response as provider unavailability.
- Correction: use a writable ephemeral Codex home with read-only source auth,
  rely on the constrained worker container as the execution boundary, send an
  immediate interpretation/job-ID acknowledgement, support `/cancel [job-id]`,
  and forward safe creative 4xx validation details.
- Prevention: release-test a real executor shell call, acceptance reply,
  queued/running cancellation, and user-facing downstream validation errors.

## 2026-08-13 — `/research` exposed without an executable provider

- Impact: Telegram advertised and routed creative research, but execution
  returned “provider is not configured”. Earlier `/help` also omitted it.
- Cause: routing, discovery, provider readiness, and end-to-end execution were
  treated as separate details instead of one release contract. The design also
  assumed a new API key although the VPS had an authenticated Codex runtime.
- Correction: `/research creative <topic>` uses the existing Codex agent, is
  owned by `marketing.creative.instagram`, and writes to the
  `marketing.creative` knowledge domain.
- Prevention: a Telegram capability is not available until deployed help,
  routing, authorization, provider readiness, real execution, graph persistence,
  restart behavior, and the failure message have all been verified.

## 2026-08-18 — DataForSEO onboarding hid an access-specific rejection

- Impact: the interactive provider setup ended with a generic authentication
  failure and the expected closure of its one-shot SSH session looked like a
  transport outage.
- Cause: `curl --fail-with-body` short-circuited the safe JSON-status parser, so
  an authenticated HTTP 403 was flattened even though credential-free probes
  proved VPS DNS, TLS, egress, and both DataForSEO endpoints healthy.
- Correction: setup now preserves the provider response long enough to report
  only bounded HTTP/provider status fields, safely escapes curl-config values,
  and continues to leave production unchanged on rejection.
- Prevention: distinguish one-shot SSH completion from connection failure, use
  a dummy-auth 401 as the egress discriminator, then check API Access, IP
  whitelisting, account status, and provider support without exposing secrets.

## 2026-08-18 — One Standard-queue SERP outlived the polling window

- Impact: a live five-country run showed SERP Discovery as failed after 31 of
  32 paid tasks completed; the final remote task remained safely persisted.
- Cause: the 900-second polling window treated a normal-priority queue outlier
  as a stage failure even though DataForSEO completed it later.
- Correction: free Advanced retrieval confirmed the existing task was ready,
  the same run resumed without reposting or rebilling, and the default polling
  window was raised to 3600 seconds with an owner-actionable fallback message.
  The initial recovery was performed by Codex through the authenticated
  internal owner boundary; this exposed that the generic Retry label did not
  make the actor or no-repost behavior visible.
- Prevention: audit persisted provider task state before retrying, never infer
  a need to repost from a queue timeout, and retain exactly-once cost recording.
  Append failure/resume/recovery actors to `laval_run_actions`, expose the
  task/cost recovery report and explicit Resume saved work control, and project
  the same S00-S15 state through the Commander Telegram outbox.

## 2026-08-19 — One-gigabyte pressure caused global OOM and owner-console stalls

- Impact: the Owner Console became stuck on loading and SSH sometimes accepted
  TCP without completing its banner after a day of normal latency.
- Cause: the VPS had no swap and only 80 MB available while retired creative
  and notification workers still ran. Kernel history proves repeated global
  OOM kills of API and system-update processes. Repository operations also
  created avoidable PostgreSQL connection churn, and the Commander readiness
  probe left its `SELECT 1` transaction open between checks.
- Correction: install a persistent 2 GB swap file, tune both PostgreSQL
  instances, retire the two polling workers, reuse one serialized Laval
  connection, and close every readiness transaction. Deploy prebuilt amd64
  images and services strictly one at a time under the maintenance lock.
- Prevention: the 1 GB release and audit scripts enforce serialization, memory
  thresholds, worker absence, OOM inspection, bounded deadlines, and database
  activity sampling. Inspect persistent `idle in transaction` rows by query and
  application name instead of treating a stable count as polling.
