# PTW v2 incident log

This file begins with the Marketing Positioning → Landing → Ads baseline.
Historical retired-domain incidents are available only in Git history.

## Reusable release guardrails

- A reset touching `/opt/ptw/platform` data is a release-blocking defect.
- Health is insufficient: require database-backed readiness and fresh strict
  bridge canaries.
- A lead must survive any Telegram result; ambiguous delivery is not failure or
  success and cannot be auto-retried.
- A stale service worker or UI exposing a retired workspace/API blocks release.
- A preview with an active form, or a publication that calls the agent again,
  blocks release.
- A new Telegram poller/worker/webhook or non-allowlisted chat blocks release.

Append new incidents with symptom, exact cause, durable fix, verification, and
the narrowest skill update. Never record secrets or ephemeral release hashes.

## 2026-08-23: v2 cutover stopped at Compose interpolation

- Symptom: the serial release stopped after image verification and before any
  bridge replacement or database reset.
- Cause: the required exact Landing proxy CIDR was stored in the Owner Gateway
  env file, but Commander Compose interpolation loaded only the platform and
  Commander env files.
- Durable fix: every Commander lifecycle/audit command now loads the platform,
  Commander, and Owner Gateway env files in order. The incident skill requires
  a pre-stream Compose render and exact live-network CIDR resolution.
- Verification: shell parsing and Compose rendering pass with the production
  env layout; the failed attempt changed no schema or running container.

The next pre-reset gate also found that the production Compose CLI rejects
`--no-build` on `compose run`. The bridge rollback restored both prior platform
images. One-off canary/migration commands now rely on `pull_policy: never` and
preloaded versioned images, while service `up` retains `--no-build`.
