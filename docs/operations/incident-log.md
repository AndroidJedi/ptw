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

After the reset began, Owner Gateway failed closed because production lacked
the new lead-rate-limit HMAC secret. A persistent random secret was generated
once in the root-owned Owner Gateway env without disclosure. Deploy and reset
now reject a missing, short, or example-placeholder value before any schema
drop.

The first post-reset audit then falsely classified the required independent
platform bridge worker as a retired Commander worker. Retired-service checks
now use anchored full Compose container names, preserving the platform worker
while still failing on the removed application workers and Idea service.

The first public bundle audit expected an English `Admin` nav label even though
the code-owned chrome is Ukrainian. The live v2 bundle was correct. The audit
now proves Admin through its stable `Docs / System / Terminal` view marker.

The alternate official Owner Hosting hostname (`web.app`) initially failed
CORS while the primary `firebaseapp.com` origin passed. Owner Gateway now
derives and permits exactly both code-owned Firebase origins, with no wildcard.
