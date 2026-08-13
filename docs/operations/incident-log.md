# Operational incident log

Canonical record of deployment gaps and prevention rules. Do not store secrets.

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
