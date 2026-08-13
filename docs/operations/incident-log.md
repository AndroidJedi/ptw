# Operational incident log

Canonical record of deployment gaps and prevention rules. Do not store secrets.

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

