---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, project-scoped Studio, Commander, Validation, PostgreSQL, Pexels, and the existing Telegram emergency boundary.
---

# PTW Owner Console Incident

Trace a public symptom through browser → Firebase Hosting/Caddy → Owner Gateway
→ Validation → PostgreSQL or the independent structured/media bridge/Pexels.
A healthy Gateway alone does not prove Brief, creative, image, or learning
readiness.

When a failed structured bridge request, a missing Landing tab, or a no-op
ChatGPT Authorization button appears in production, read
[references/bridge-landing-auth-incident.md](references/bridge-landing-auth-incident.md)
before changing code or runtime state.

## Public boundary

- Verify hashed bundles, service-worker cache, Firebase Auth persistence, App
  Check, exact Owner CORS origins, and unauthenticated rejection.
- The app exposes only Brief / Бриф, Post / Допис, Landing / Лендінг,
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
- A Brief/list GET can correctly return HTTP 200 while an item inside it has
  `status: failed`. Diagnose that stored background-operation failure separately
  from transport/API status; never tell the owner that HTTP 200 proves the
  generation succeeded.
- Read the authenticated live capabilities response even when API/worker image
  tags match. A reused tag can conceal stale image content; retired modes or
  missing Studio modes make the release incompatible.
- Do not accept `codex login status` as provider readiness. Check the root-owned
  auth file only by metadata and run the token-safe working Codex test. A
  credential can look logged in while model execution is revoked or times out.
- When ordinary auth verification and health look green but a bridge job fails,
  run the token-safe schema-bound worker probe from
  `scripts/audit_vps_owner_dependencies.sh`. `unauthorized` on the same
  `codex exec --ephemeral --output-schema` boundary used by jobs requires one
  new owner-completed device flow; do not retry the Brief until authorization
  reports `authorized`/`passed` and the schema-bound probe succeeds.
- Exercise device authorization through a pseudo-terminal and require both the
  official device URL and one-time code before reporting `authorizing`. Current
  Codex CLI releases may not emit the code to a plain pipe; a flow that returns
  to `authorization_required` without updating auth is a failed flow.
- The auth container must be attached to both the private backend network and an
  outbound-capable edge network. Strip ANSI terminal control sequences before
  matching the one-time code; otherwise the URL can appear while the styled code
  remains absent. Never expose the persisted credential or bridge token.
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

Every owner-visible API failure must state: what failed, a plain-language
explanation, the next safe owner action, and bounded technical context such as
HTTP method/status, endpoint, object ID, or bridge job ID. Apply the same
contract to HTTP/network/timeout/auth/integrity failures and persisted async
`status: failed` states. Do not expose raw 5xx/provider output, prompts,
credentials, filesystem paths, or tracebacks. Preserve already-saved state and
tell the owner to refresh before retrying any request whose server outcome may
be uncertain.

Run schema idempotency, provider contract/canaries, Validation and Owner Gateway
tests, Commander tests/demo, skill validation, web unit/build/Playwright,
Studio visual audit, Python compilation, and `git diff --check`. Exercise the
complete browser workflow and cross-Project rejection before declaring the
incident resolved. Before claiming Telegram works, verify authorization,
deployed help/routing, provider readiness, persistence, restart behavior, and
the user-facing failure path.
