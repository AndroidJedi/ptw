---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, project-scoped Studio, Commander, Validation, PostgreSQL, Pexels, and the existing Telegram emergency boundary.
---

# PTW Owner Console Incident

Trace a public symptom through browser → Firebase Hosting/Caddy → Owner Gateway
→ Validation → PostgreSQL or the independent structured/media bridge/Pexels.
A healthy Gateway alone does not prove Brief, creative, image, or learning
readiness.

## Public boundary

- Verify hashed bundles, service-worker cache, Firebase Auth persistence, App
  Check, exact Owner CORS origins, and unauthenticated rejection.
- The app exposes only Product Briefs, Post / Допис, Landing / Лендінг,
  and Settings. Brief, Post, and Landing retain their required Project scope;
  every Studio mutation is Project/creative-scoped.
- Preview, history, and immutable-version renders are authenticated,
  digest-checked, and private/no-store. The browser receives no provider path,
  prompt credential, database secret, or raw token.
- Pexels and image assets retain source/digest provenance and validate declared
  MIME against decoded bytes before persistence.
- Telegram remains only `/help`, `/status`, and `/stop`; all other input
  returns the web-console link and cannot mutate state.

## Brief, Studio, and provider checks

- Treat `structured bridge request N failed` as a bridge job ID, not an HTTP
  status. Correlate that ID across the Product Brief attempt, provider
  invocation, platform `jobs` row, and worker log without exposing prompts or
  credentials.
- Read the authenticated live capabilities response even when API/worker image
  tags match. A reused tag can conceal stale image content; retired modes or
  missing Studio modes make the release incompatible.
- Do not accept `codex login status` as provider readiness. Check the root-owned
  auth file only by metadata and run the token-safe working Codex test. A
  credential can look logged in while model execution is revoked or times out.
- Verify raw idea → immutable Brief → correction lineage → honor confirmation
  plus template choice → HTTP 202 creative reservation/navigation.
- Provider JSON modes are exactly `product_brief`,
  `product_brief_revision`, `studio_creative_generation`, and
  `studio_edit_learning`. The only media mode is bounded non-human graphic
  generation with at most one digest-checked PNG enhancement reference.
- Composition must record Brief, template, global-skill, and Project-skill IDs
  and hashes, validate output against the live selected template, and start a
  fresh text-free phone hero for `phone_metrics`.
- Save/Approve creates learning only when accumulated owner edits changed state.
  Confirm immutable checkpoint, append-only attempts, automatic Project skill,
  sanitized global proposal, explicit owner decision, and retry without rollback.
- Restart recovery resumes queued composition/image/learning exactly once.
  PostgreSQL remains authority; per-creative renderer files are disposable cache.
- Bare Studio routes, `/api/v1/posts`, candidate/critic modes, singleton rows,
  assignment UX, and historical schema adapters must remain absent.

## Release acceptance

Run schema idempotency, provider contract/canaries, Validation and Owner Gateway
tests, Commander tests/demo, skill validation, web unit/build/Playwright,
Studio visual audit, Python compilation, and `git diff --check`. Exercise the
complete browser workflow and cross-Project rejection before declaring the
incident resolved. Before claiming Telegram works, verify authorization,
deployed help/routing, provider readiness, persistence, restart behavior, and
the user-facing failure path.
