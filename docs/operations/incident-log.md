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
