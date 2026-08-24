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

## 2026-08-24: Validation inherited retired YouTube settings

- Symptom: the authorized validation reset completed and all new services and
  bridge canaries were healthy, but the post-reset dependency audit rejected
  the Validation container for exposing retired provider setting names.
- Cause: Validation Compose attached the complete Owner Gateway, Commander, and
  platform env files instead of injecting only its required variables. The
  cutover cleanup removed retired research and Landing prefixes but omitted the
  two legacy `YOUTUBE_` entries present in the root-owned Owner Gateway env.
- Durable fix: Validation Compose now has an explicit eight-variable runtime
  allowlist, including a dedicated in-container `LLM_BRIDGE_TOKEN` mapped from
  the existing root-owned platform credential, with no service-level
  `env_file`. Cutover cleanup also removes the retired `YOUTUBE_` prefix. The
  incident skill forbids whole-env inheritance at this boundary.
- Verification: production Compose rendered without printing values; Validation
  and Owner Gateway were recreated; runtime name inspection found no retired
  provider settings; schema, three-mode bridge, dependency, skill, Telegram,
  restart, public-boundary, and immediate 1 GB/OOM audits passed.

## 2026-08-24: validation cutover stopped at platform bundle fetch

- Symptom: the serial Phase 1 release loaded and verified all five images, then
  stopped while fetching the transferred independent-platform Git bundle.
  The bridge was not replaced and the application reset did not start.
- Cause: the binary stream protocol padded every file to a 1 MiB boundary.
  Docker accepts zero-padded tar archives, and `git bundle verify` accepted the
  bundle header, but `git fetch` correctly rejected trailing bytes as pack
  junk.
- Durable fix: non-tar stream frames now include the original byte length and
  original SHA-256. The receiver validates the framing bounds, truncates the
  padding, and only then verifies the checksum or passes the artifact to Git.
  The incident skill now requires exact-length transport and a disposable
  bundle fetch before production streaming.
- Verification: the paired publisher/deployer contract test, shell parsing,
  exact-tag archives, padded round trip, and disposable bundle fetch passed.
  The fresh serial retry then fetched the production bundle, passed all bridge
  and Pexels gates, and completed the allowlisted reset.

## 2026-08-24: rebuilt Owner Console remained old on Hosting

- Symptom: the production Firebase URL continued to show the pink Positioning
  console after the new Product Brief/Ads shell and monochrome theme were
  committed and verified locally.
- Cause: the normal publisher intentionally releases Hosting only after the
  backend bridge, Pexels canary, and irreversible schema reset. Those gates had
  not been satisfied, so no static release had occurred.
- Durable fix: after an explicit owner request, deploy Hosting alone as a
  clearly labelled partial release. Never describe the new shell as Stage 1–2
  ready while the legacy API remains active, and do not weaken the backend
  reset or Pexels gates.
- Verification: cache-busted public assets contain Product Briefs, Ads, the
  dormant Landing placeholder, Admin, monochrome chrome, and the bumped service
  worker. Desktop and iPhone login screenshots are monochrome. The full audit
  proceeds through Hosting/Auth checks and then fails at the expected legacy
  Positioning API boundary until backend cutover.

The later coordinated backend cutover removed that expected red boundary; the
same public audit now passes retired-route 404s and the new API boundary.

## 2026-08-23: first Positioning attempt timed out without notification

- Symptom: the first production Positioning remained `researching` for 15
  minutes, failed with no result, and sent no Telegram notification.
- Cause: the active workflow blocked on a DataForSEO task until its bounded
  polling timeout. Positioning terminal notifications had not been implemented;
  only Landing lead delivery used the existing bot.
- Durable fix: Positioning now synthesizes directly from the permanent owner
  idea Source. Country and market language remain context, while unsupported
  market conclusions are explicit assumptions. DataForSEO configuration and
  calls are removed from the active service. Every durable completed or failed
  generation attempt records one append-only notification attempt and makes at
  most one direct `sendMessage` through the existing allowlisted PTW bot.
- Verification: cover sole-source synthesis, absence of external-research
  settings/calls, strict assumption validation, success/failure messages,
  escaping, idempotency, emergency-stop suppression, restart recovery, and the
  retried production revision.

The first owner-input-only retry then failed immediately in the platform bridge.
A typed minimal canary passed while the document schema failed: its
`schema_version` used `const` without an explicit JSON `type`, which the current
structured-output validator rejects as `invalid_json_schema`. Positioning and
Landing output schemas now type every constant field, with regression tests and
a fresh live canary required before retry.

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
