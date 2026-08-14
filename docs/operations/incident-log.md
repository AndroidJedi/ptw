# Operational incident log

Canonical record of deployment gaps and prevention rules. Do not store secrets.

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
