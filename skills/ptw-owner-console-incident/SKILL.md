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
  new owner-completed device flow. If auth then reports `authorized`/`passed`
  while the worker still fails, compare the auth service's published copy with
  the worker mount without printing either value. A mismatched copy means the
  mount is stale, not that the owner must authorize again. Do not retry the
  Brief until the schema-bound probe succeeds.
- Exercise device authorization through a pseudo-terminal and require both the
  official device URL and one-time code before reporting `authorizing`. Current
  Codex CLI releases may not emit the code to a plain pipe; a flow that returns
  to `authorization_required` without updating auth is a failed flow.
- The auth container must be attached to both the private backend network and an
  outbound-capable edge network. Strip ANSI terminal control sequences before
  matching the one-time code; otherwise the URL can appear while the styled code
  remains absent. Publish credentials through a dedicated root-owned directory
  mounted read-only by the worker. Never bind the primary `auth.json` as one
  file: Codex can atomically replace it and leave the worker pinned to the old
  inode. Never expose the persisted credential or bridge token.
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
- When Studio composition is `failed` with a domain `ValueError` but its bridge
  job is `completed`, read only the rejected field and matching output-schema
  constraint from the provider job. Repeated failures with the same response
  and `:attempt:1` idempotency key mean a completed invalid response is being
  replayed; provider health and owner Retry cannot repair that loop. Keep the
  renderer bound authoritative, add the exact bound/enum/pattern to the strict
  generation schema, and version the Studio composition prompt/idempotency
  namespace when its contract changes. Permit at most one `:attempt:2` job only
  after a completed response is rejected by deterministic PTW validation, with
  the bounded validation error as correction context. Never create that second
  job after an HTTP, network, timeout, cancellation, or provider failure whose
  outcome is uncertain. Preserve the failed creative and all append-only runs;
  after rollout, retry that same creative once and require a valid draft plus
  distinct completed provider provenance rather than reserving a replacement.
- Treat that Studio failure as one example of a general contract-drift class,
  not a field-specific exception. Every structured Product Brief, revision,
  Universal Post, Phone Metrics, Landing composition, Studio-learning, and
  Landing-learning call must supply a deterministic domain response validator.
  A provider/schema-valid object is never sufficient by itself. Keep renderer
  and Landing bounds, enums, patterns, fixed values, content lengths, and
  privacy constraints in shared domain constants consumed by both the strict
  schema and runtime normalizer; do not copy numeric literals into independent
  contracts.
- Bind bridge idempotency automatically to a canonical fingerprint of mode,
  model, prompt version, system-prompt digest, complete input-payload digest,
  output-schema digest, and referenced-asset digests. A manual prompt-version
  suffix alone is not an acceptable cache boundary. Prove that changing any
  dependency changes the job key, while an identical request reconciles the
  same job. Keep the final printable key within the platform's 240-character
  limit without dropping collision resistance. Media generation/enhancement
  follows the same rule.
- Keep client submission concurrency aligned with actual worker concurrency so
  a queued request cannot consume most of its deadline behind another job.
  Worker execution timeout must remain bounded below the client deadline and
  covered by a configuration-boundary test; a timeout may be extended only
  within that verified margin, never made unbounded.
- Pin production structured jobs to the server-owned bounded reasoning effort
  instead of inheriting an ambient CLI default. Keep the allowed effort values
  closed and test the exact CLI argument; all results still require schema and
  domain validation before acceptance.
- A retry transition must clear stale top-level error metadata while retaining
  append-only failed run records. Never show a recovered draft as failed merely
  because an earlier error remains in its current-state envelope. HTTP bridge
  failures expose only the bounded status and never reflect the provider body.
- When Landing reservation returns `badly formed hexadecimal UUID string`, first
  validate both the Project and selected Post IDs, then inspect every
  `DatabaseLandingAuthority._edge(connection, source_id, relation, target_id, …)`
  call. A swapped `relation`/`target_id` can send the literal `derived_from` to
  `UUID()` even though every owner-supplied ID is valid. Require a database-path
  regression test for the Project `contains` edge plus Brief and Post-version
  `derived_from` edges; the loopback path alone cannot cover this failure.
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

For a failed Landing reservation, confirm transaction rollback with zero new
Landing workspace and relationship rows before retrying. After rollout, retry
the same approved Post version once and verify the returned Landing ID, all
three typed lineage edges, background generation progress, and idempotent
second reservation. Do not delete or reset an otherwise clean Project.

Run schema idempotency, provider contract/canaries, Validation and Owner Gateway
tests, Commander tests/demo, skill validation, web unit/build/Playwright,
Studio visual audit, Python compilation, and `git diff --check`. Exercise the
complete browser workflow and cross-Project rejection before declaring the
incident resolved. The release canary must domain-validate both Product Brief
modes, both Post templates, Landing composition, both learning skills, fresh
media generation, and exact-reference enhancement; every structured canary
must use a fresh request fingerprint and pass on attempt 1. Adding a structured
workflow without its validator and canary is a release-blocking contract gap.
For a normal VPS release, execute the tracked
`scripts/deploy_ptw_preserving.sh`; do not feed a control script over SSH stdin.
Its Compose one-off jobs must retain `-T`, its cleanup must roll back any
incomplete exit even if the shell reports zero, and its full-row authority
snapshot must match before release tags are persisted. Never substitute the
confirmation-gated reset publisher for this preserving path.
Before claiming Telegram works, verify authorization,
deployed help/routing, provider readiness, persistence, restart behavior, and
the user-facing failure path.
