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
- A local frontend that proxies the production Owner Gateway must use exactly
  one registered Firebase App Check debug token from its ignored local
  environment. Refuse to start that mode when the token is absent or malformed,
  and refuse to compile it as a production build. Never make local development
  pass by adding localhost to the production reCAPTCHA allowlist, bypassing
  Gateway App Check verification, committing the token, or printing it. Verify
  token acquisition independently in Chromium and WebKit before diagnosing the
  owner ID token or API proxy.
- When Safari reports that `frame-ancestors` is ignored in a report-only policy,
  identify the response that supplied that policy before editing PTW headers.
  The owned Owner document must send an enforcing `Content-Security-Policy`
  containing `frame-ancestors 'none'`, no report-only CSP, and `X-Frame-Options:
  DENY`. Google Identity/reCAPTCHA response policies are third-party diagnostics
  and cannot be repaired by weakening PTW's enforcing policy.
- A 401 from Google's `/recaptcha/enterprise/pat` endpoint is the expected
  Private Access Token challenge on Apple devices, not evidence that App Check
  or a PTW template request failed. Check the actual authenticated request to
  the Owner Gateway and the in-app error before changing Firebase settings or
  deploying. See [Google's Private Access Token documentation](https://docs.cloud.google.com/recaptcha/docs/private-access-tokens).
- The app exposes only Brief / Бриф, Post / Допис, Landing / Лендінг,
  Instagram tests / Instagram-тести, Analytics, Commander, and Settings. Brief,
  Post, Landing, and Instagram tests retain their required Project scope;
  every Studio mutation is Project/creative-scoped.
- Commander is a dedicated, Project-independent workspace. When its UI changes,
  update live bundle acceptance markers with the visible conversation, native
  mode controls, and steering contract; retired labels are not readiness checks.
- Preview, history, and immutable-version renders are authenticated,
  digest-checked, and private/no-store. The browser receives no provider path,
  prompt credential, database secret, or raw token.
- When a built-in Templates card appears but opening its exact version returns
  404, compare the browser's version/digest with the built-in catalog and trace
  the GET through Gateway and Validation. A failed native preview may leave the
  gallery's built-in summary unpersisted; exact reads must still resolve that
  registered identity and show `preview_status: failed`. Keep wrong-digest
  conflicts and unknown-template 404s distinct. Test the actual Gateway path
  and the Validation read while forcing the preview renderer to fail; editing
  from an instruction must not require unavailable preview bytes.
- When a locally authored template appears missing, verify which process owns
  the browser and API ports and which database the API opened. The Templates
  browser canary serves a disposable database; a `proposed` run appears under
  Drafts, while only an accepted version appears in the gallery and Project
  picker. Check the exact run, version and preview digests before recovery.
  Source deployment does not transfer local template records. For an owner-
  directed production restore, back up both authorities, import the checked
  append-only run/version/media under the maintenance lock without replacing
  existing records, then verify gallery, exact-version and digest-bound media
  through the running API. Keep the original local authority intact.
- When Recent iPhone Images has metadata but blank thumbnails, first verify the
  exact history bytes and digest through Validation, then check whether any
  history GET reached the Gateway. Zero Gateway requests while ordinary preview
  POSTs succeed points to browser credential acquisition, not missing stored
  media. Coalesce concurrent Firebase ID/App Check acquisition, retain bounded
  retry for read-only thumbnails, and keep failures non-mutating. Acceptance
  requires all three digest-checked thumbnails after a cold load and exactly one
  concurrent App Check acquisition wave.
- Pexels and image assets retain source/digest provenance and validate declared
  MIME against decoded bytes before persistence.
- Telegram remains only `/help`, `/status`, and `/stop`; all other input
  returns the web-console link and cannot mutate state.
- Paid Instagram validation is manual. PTW freezes one published Landing and
  2–6 approved Posts, assigns one tracked URL and deterministic Ad name per arm,
  and exports a launch kit for one Campaign → one Ad Set → all Ads. The audience
  exists only in Meta Ads Manager. PTW automatically records first-party Landing
  events and imports paid delivery through owner-reviewed CSV mapping.
- One Project may have only one active Instagram test. While active, changing
  the published Landing must fail closed. Completion requires explicit owner
  confirmation that both Campaign and Ad Set are stopped. A current leader by
  cost per primary CTA is informational and never an automatic winner.
- Active Owner/Validation APIs must return 404 for `/ads`, `/tiktok`, and public
  TikTok media surfaces. Historical modules and tables remain recovery material;
  use `$legacy-social-automation-recovery` only on an explicit owner request.

## Brief, Studio, and provider checks

- Treat `structured bridge request N failed` as a bridge job ID, not an HTTP
  status. Correlate that ID across the Product Brief attempt, provider
  invocation, platform `jobs` row, and worker log without exposing prompts or
  credentials.
- Before promoting a new structured schema, run that exact schema through the
  production Codex CLI `--output-schema` boundary, not only a Python validator.
  Every object at every nesting depth must set `additionalProperties: false`
  and require exactly its declared properties; open target/evidence/confidence
  objects can be rejected before model execution while ordinary auth and health
  checks remain green.
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
- Provider structured modes are exactly `product_brief`,
  `product_brief_revision`, `studio_creative_generation`,
  `studio_manual_edit`, `creative_performance_learning`, and
  `creative_visual_analysis`. Studio manual editing accepts zero to four ordered,
  digest-bound screenshots and must pass its real multimodal canary. The only
  generation media mode is bounded non-human graphic generation. Visual
  analysis and enhancement accept at most one digest-checked PNG reference.
- Composition must record Brief, template, global-skill, and Project-skill IDs
  and hashes, validate output against the live selected template, and start a
  fresh text-free phone hero for `phone_metrics`.
- Save/Approve must make zero learning calls. Confirm only the immutable changed
  checkpoint, saved state, and (for Approve) immutable version. There is no
  learning dialog, route, retry, or recovery queue at this boundary.
- Performance learning starts only from Analytics, freezes its complete eligible
  dataset, returns inactive typed candidates, and requires a reviewed Activate or
  Reject decision. A failed run must leave active skills unchanged. Global rules
  are spirit-only; Project rules are catalog-validated and Brief-subordinate.
- Restart recovery resumes queued composition/image exactly once; Save-era
  learning recovery is retired.
  PostgreSQL remains authority; per-creative renderer files are disposable cache.
- When an already-approved Brief returns HTTP 409 from `/approve`, inspect its
  ordinal-1 Studio workspace before retrying. Approval and first-Creative
  reservation are transactional: one existing workspace means the owner action
  must navigate to that Creative, not reopen a blank template/direction chooser.
  A different submitted template or Phone Metrics direction correctly conflicts
  with the immutable reservation. Confirm exactly one approval, one ordinal-1
  workspace, unchanged lineage/run counts, and no new mutation before changing
  code; preserve the server conflict guard and fix the client resolution path.
  Do not close the incident merely because that fix exists in Git. Require the
  built and live App bundle to expose the incident-specific client contract,
  bump the PWA cache generation when stale clients must be displaced, and run
  the cross-browser test that proves the action resolves the existing Creative,
  navigates directly, opens no chooser, and sends zero approval POSTs. Keep the
  exact Creative-list route assertion in the unit regression. Web-only incident
  releases use the tracked `scripts/deploy_owner_console_web.sh` gate so
  unit/build, Playwright, skill validation, Hosting deployment, and the public
  live audit cannot drift.
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
- For `Brief-supported metrics require an exact supporting Brief excerpt`,
  compare only `content.stats[*].value` with its matching `metric_basis[*]`.
  A spelled-out quantity does not support a digit-form value. Keep the runtime
  exact-substring/quantity check, make the strict schema distinguish
  `brief_supported` evidence containing an Arabic numeral from
  `ai_hypothesis` with empty evidence, and version the composition namespace.
  Do not weaken provenance to recover the creative; retry the same ID once
  after rollout and preserve both rejected bridge jobs and the failed run.
- When a browser Studio mutation returns 404, compare the exact method/path at
  all three boundaries before inspecting the provider: built/live Owner
  Console call, public Owner Gateway route, and internal Validation route. A
  public 404 paired with an internal unauthenticated 401 means the Gateway
  proxy is missing; it is not an object or provider failure. Preserve the
  Creative and add the missing authenticated proxy. Require method/path parity
  between every shared Studio Gateway and Validation route, a forwarding test
  for the exact body/service token/actor, and a live unauthenticated probe that
  returns 401 rather than 404 without mutating state.
- When the first Brief POST for an existing empty Project returns HTTP 500 and
  Validation logs `immutable Validation Project fields cannot change`, inspect
  the Project row before retrying. If it retains `owner_idea_source_id=NULL`
  and has zero Briefs, the transaction rolled back at the Project source
  attachment; this is neither a bridge outage nor partial Brief persistence.
  The Project trigger must permit exactly one `NULL -> source UUID` assignment
  while permanently rejecting a replacement, removal, or any other immutable
  field update. Repair the trigger with one additive migration, never modify
  the applied baseline migration or manually update the production Project.
  Prove both the allowed first assignment and rejected replacement in a
  disposable PostgreSQL check, then reconcile the same Project after rollout
  before its owner retries.
- Do not describe a Playwright suite that intercepts all `/api/v1/**` traffic
  as a complete end-to-end system test. Report it as browser/UI E2E. Full flow
  acceptance must additionally traverse real HTTP route handlers and domain
  services for approval, direction save/replacement/idempotency, stale-state
  and cross-Project rejection, fresh generation, exact-reference enhancement,
  history integrity, selection, Save with zero learning, approval/version,
  performance-learning review, failure/retry,
  and restart recovery. The release is blocked if the browser, Gateway,
  Validation, persistence, or provider boundary is only mocked at the point
  whose compatibility is being claimed.
- When Studio Save or Approve returns HTTP 400 but PostgreSQL version or
  checkpoint counts increase, stop retries: the mutation crossed its durable
  boundary and the response failed during metadata finalization. Correlate the
  exact request time with `universal_studio_versions`,
  `studio_edit_checkpoints`, the workspace row, and the persisted workspace
  files before changing data. In particular, keep derived fields such as
  `approved_version_count` accepted by every authority adapter while persisting
  them only where authoritative; the PostgreSQL adapter derives this count from
  immutable version rows and must ignore it as a workspace-column update.
  Require a production-adapter regression in addition to the loopback workflow.
  Approval retry comparison must use the same normalized configuration/content
  as save and preview, so semantically equivalent whitespace cannot append a
  duplicate immutable version after an uncertain response. Preserve any
  already-created versions and checkpoints as incident evidence; do not delete
  append-only authority to make counts look tidy. After deployment, reconcile
  the original action once, require HTTP 200 with no additional version, and
  prove a service restart retains the same IDs, digests, version count, and
  empty recovery queues.
  Save checkpoints no longer require or start learning. Do not block a
  preserving rollout because a historical checkpoint lacks a completed legacy
  learning run, and do not resume that work on startup. A preservation mismatch
  is never waived merely because another write is valid.
- Treat that Studio failure as one example of a general contract-drift class,
  not a field-specific exception. Every structured Product Brief, revision,
  registered Post, Landing composition, performance-learning, and
  visual-analysis call must supply a deterministic domain response validator.
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
- A synchronous Studio Agent provider timeout is not a draft-state conflict.
  Return a sanitized 504 (or 503 for other provider unavailability), never a
  409 or the raw Codex command/path. Keep its semantic component contract under
  an explicit byte cap, use the bounded workflow-specific reasoning effort,
  and retain the last two text requests per Project in browser-local storage so
  refresh/retry does not erase owner input. Never retain screenshots, editor
  state, contacts, evidence, or generated pixels in browser storage.
- Pin production structured jobs to the server-owned bounded reasoning effort
  instead of inheriting an ambient CLI default. Keep the allowed effort values
  closed and test the exact CLI argument; all results still require schema and
  domain validation before acceptance.
- Treat repeated execution-deadline failures on one schema-bound workflow as a
  contract-shape incident, not a reason to keep extending timeouts. Separate
  AI-owned semantic content from deterministic server-owned configuration,
  layout, routing, IDs, and asset policy. Send only the bounded source fields
  needed for that decision, cap the accepted lesson window without deleting
  append-only learning history, and build runtime plus canary payloads through
  the same function. Record prompt/input/schema byte counts without recording
  their contents; reject oversized contracts before submission. A compact
  workflow-specific canary must pass on attempt 1 before promotion.
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
- When the owner cannot find Landing Publish controls, inspect the lazy-loaded
  App bundle rather than only the small entry bundle and require the
  `PUBLIC NATAL PAGE` marker. Then distinguish release absence from intentional
  workflow gating: the publication panel appears only after the selected
  Landing has an immutable approved version (or the Project already has a
  publication). Read the selected Landing's version count and run its
  `approval_ready` check without mutating it. A draft with generated visuals but
  no contact endpoint needs one real owner-supplied email, phone, or direct
  `https://t.me/<bot_username>` link,
  followed by **Approve Landing**; it does not need a backend rollout, reset, or
  fabricated contact. After approval, the owner chooses the permanent lane and
  slug, confirms the complete URL, and uses **Publish approved version**.
  Public-boundary acceptance must verify both the lazy App marker and an
  unauthenticated 401 on the Project publication route so a UI/API mismatch is
  not mistaken for state gating.
- When Landing Save returns repeated `Landing changed; reload before saving`
  conflicts, correlate the request window with the page digest and Landing
  checkpoint rows before asking the owner to re-enter anything. Landing Save no
  longer invokes learning; treat the retained longer client timeout as a bounded
  compatibility allowance, not a learning contract. An early client timeout can leave a completed checkpoint on the
  server and a stale digest in the browser. On the exact stale-state 409, fetch
  the current page once: treat it as reconciled only when its complete
  configuration and content exactly equal the owner's pending document. If any
  field differs, retain the pending input and show the conflict; never overwrite
  either side automatically. Acceptance requires one completed checkpoint,
  zero duplicate versions/checkpoints, a successful equivalent-response
  reconciliation, and a divergent-state regression that preserves owner input.
  Immediately after Firebase Hosting release, cache propagation can briefly
  pair a new document with an old entry bundle (or the reverse). The live audit
  should retry document → entry → lazy App resolution as one bounded unit and
  must require the incident-specific `Landing was already saved.` marker before
  accepting the release; a single transient bundle-resolution miss is not proof
  that the deployed code is absent.
- A draft preview image is evidence for one exact configuration/content state.
  When owner copy changes, hide the prior render until the matching draft
  response arrives; a busy indicator over stale pixels must not imply the old
  in-phone title reflects the current field. Bind each preview object URL to the
  requested state and ignore late responses from superseded requests.
- Bare Studio routes, `/api/v1/posts`, candidate/critic modes, singleton rows,
  assignment UX, and historical schema adapters must remain absent.
- When Back navigation or a fast Project/creative switch appears to merge one
  Project's creative picker with another Project's editor, suspect stale
  in-flight browser responses before touching PostgreSQL. Key the Post view by
  the exact Project/creative route, invalidate earlier list/detail generations,
  clear route-scoped state while loading, and prove with an out-of-order response
  regression that the older Project cannot overwrite the current editor. Read
  the project-scoped creative list before claiming a saved Post disappeared;
  never delete or rewrite authority to repair a client-state race.
- `phone_metrics` is the only registered Post template. Unknown or retired IDs
  must fail at the registry boundary for selection, clone, variant, and
  template-replacement paths.

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
modes, the active Phone Metrics Post and its manual Agent, Landing composition,
both learning skills, fresh
media generation, and exact-reference enhancement; every structured canary
must use a fresh request fingerprint and pass on attempt 1. Adding a structured
workflow without its validator and canary is a release-blocking contract gap.
The Landing canary additionally proves that AI returns content only, that the
current server-owned configuration survives composition byte-for-byte, and
that no live catalog, Post configuration, or asset body enters the structured
prompt. Apply this ownership split to any future workflow whose schema or
context begins to grow, instead of solving one failing field in isolation.
For a normal VPS release, execute the tracked
`scripts/deploy_ptw_preserving.sh`; do not feed a control script over SSH stdin.
Its Compose one-off jobs must retain `-T`, its cleanup must roll back any
incomplete exit even if the shell reports zero, and its full-row authority
snapshot must match before release tags are persisted. Never substitute the
confirmation-gated reset publisher for this preserving path.
Run the preserving script's migration preflight against the exact production
PostgreSQL/Compose transport before any service cutover; a source-only test does
not prove `psql` variable/input behavior. If that preflight itself fails, stop
the rollout, prove the old six images and persisted tags are still live, then
fix, test, commit, and begin a new rollout from the start. Do not patch or skip
the failing check interactively on the VPS.
When the revision contains an additive migration, use only the separately
confirmation-gated `publish_ptw_in_place_serial.sh` path. Its outer cleanup must
restore and verify application plus platform images and persisted tags after
any incomplete exit, signal, canary, audit, or resource failure. Its inner
cleanup must refuse active mutable work, fingerprint pre-existing rows again on
the failed path, restore and verify all application images, preserve the
root-only backup, and never reverse the additive migration. Every Compose
one-off in either layer uses `-T` so SSH stdin cannot be consumed.
If that outer rollout fails after either source tree advances, restore the
accepted PTW and platform revisions and run accepted skill sync/verification
before restarting accepted application or platform images. Otherwise an old
Validation image can become unhealthy against candidate skills that removed an
old mounted skill. If the in-place publisher released the public Hosting shell
before the VPS step, restore the snapshotted accepted Hosting version on every
incomplete exit as part of the same rollback.
Before claiming Telegram works, verify authorization,
deployed help/routing, provider readiness, persistence, restart behavior, and
the user-facing failure path.
For the scheduled resource follow-up, inspect the actual transient unit
`ptw-validation-24h-audit.timer` with `systemctl is-active` and its next
elapse time. Do not infer a monitoring outage from a guessed unit name.

## Renderer compatibility during release

- If Save creative returns 409 after a compatible renderer restore, compare
  the public detail hash, the raw workspace detail hash, and PostgreSQL's stored
  hash before treating it as concurrent owner editing. A normalized editor
  document must expose its matching renderer hash; merging stored metadata last
  can replace it with the old snapshot hash and reject every Save. Use the same
  bounded legacy state validator for checkpoints as for preview/configuration.
  Keep GET read-only; on an explicit unchanged legacy Save, persist normalized
  files before advancing metadata so a fresh restore still verifies. Exercise
  both newly loaded and already-open clients, stale-state rejection, unchanged
  Save, zero learning rows, and immutable PNG preservation through real HTTP
  and disposable PostgreSQL with `scripts/verify_studio_save_restart.py`.
  A rejected 409 is not a successful save: compare checkpoint timestamps before
  claiming a restart lost committed edits. Never reconstruct rejected owner
  input from assumptions or replace append-only history.
- A `role="alert"` elsewhere in a long editor is not proof that the owner saw
  a rejected Save. Keep action feedback beside the Save controls, bring errors
  into the viewport and keyboard focus, retain pending input, and never show
  success after rejection. Keep preview failures separate so a late render
  response cannot replace a Save error or make a committed Save look failed.
  Save and Approve no longer invoke learning and use the normal bounded Gateway
  mutation deadline. Test a delayed 409 after scrolling away on desktop, 360px,
  and iPhone WebKit; require the actual error heading in the viewport, retained
  field values, one request, and no success notice. Tell the owner to copy
  pending edits before reloading. Bump the PWA shell cache for the release.
- A Post/Ads/Instagram workspace 409 reporting a restored state-digest mismatch
  can come from normalizing a persisted phone configuration v8 to the current
  editor schema before verifying its original snapshot. Compare the stored
  digest with both current and bounded legacy snapshot digests; never skip
  verification or rewrite the database to make it match. Restore through the
  existing state validator and persist only on an owner mutation. Acceptance
  requires repeated database-backed reads and restart with unchanged source
  files, immutable PNG bytes, IDs, and stored digest, plus rejection of tampering.
- Firebase can briefly return the SPA HTML fallback with HTTP 200 at a newly
  released hashed JavaScript URL. The live auditor must require JavaScript MIME
  for both entry and lazy App assets within its bounded propagation retry;
  HTTP 200 alone is not sufficient before checking application markers.
