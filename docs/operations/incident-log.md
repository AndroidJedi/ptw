# Operational incident log

Canonical record of deployment gaps and prevention rules. Do not store secrets.

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
