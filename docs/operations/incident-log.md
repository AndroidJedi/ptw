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
- A synchronous FastAPI route must not schedule coroutine work; background
  generation starts only from a running event loop and startup must fail stale
  queued/generating work while releasing its singleton guard.
- A provider canary must use the real production prompt, schema, and domain
  validator. Product Brief language is inferred once per attempt and bound in
  both the strict output schema and prompt.

Append new incidents with symptom, exact cause, durable fix, verification, and
the narrowest skill update. Never record secrets or ephemeral release hashes.

## 2026-08-27: five Instagram strategies rendered as one visual family

- Symptom: the five generated Result directions used different media/headline
  rectangles but repeated the same dark canvas, offer row, CTA pill, logo row,
  and overall hierarchy. The strategy labels changed while the thumbnails
  remained visually interchangeable.
- Cause: `InstagramStaticAdapter._recipe()` selected five small hardcoded frame
  maps, then built every output through one shared skeleton. Four sliders had no
  renderer effect and `visual_complexity` was recorded only as inert modifier
  metadata. The regression test compared two frame rectangles rather than full
  component trees or decoded pixels.
- Durable fix: the adapter now applies exactly five Git-owned v2
  `ptw.studio.template.v1` component trees through one strict catalog and
  generic renderer. Strategy and Studio IDs, versions, and digests are locked at
  startup. All five sliders resolve through deterministic declared rules into
  quantized component patches; protected bindings and undeclared paths cannot
  change. Every recipe embeds its immutable template snapshot, reserved UUID
  map, bindings, sliders, patch, catalog/renderer identities, and parent
  lineage. Render manifests include the complete resolved recipe and production
  digests. The Owner Console incident skill now makes the non-persisting
  five-template replay/distinction canary a release gate.
- Verification: focused contract tests cover catalog strictness, five complete
  structural signatures, every valid ten-point template/slider adjustment,
  unchanged-component identity, protected binding rejection, parent metadata,
  canonical replay, and manifest completeness. The Linux/amd64 canary renders
  all five from one fixed input, verifies exact decoded-pixel replay, and checks
  all ten pairwise visual differences. Production cutover and preservation
  evidence are recorded in the current-state resume after deployment.

## 2026-08-27: Result critic rejected persisted preview mappings

- Symptom: Result run `01a041f1-a430-7662-b27f-2339197e794b` completed and
  rendered all five initial Instagram candidates, then failed before critic
  Pass 1 with `Result critic image mapping fields do not match v1`.
- Cause: `candidate_preview()` correctly returned the authenticated persisted
  JPEG metadata field `mime_type`, but the application-side bridge mapper
  required an exact reduced field set that omitted it. The generic critic
  release canary hand-built that same reduced mapping instead of exercising the
  repository shape, so it did not detect the mismatch.
- Durable fix: the bridge now accepts exactly the canonical six-field preview
  mapping, validates `image/jpeg`, dimensions, digest, bounds, and candidate
  uniqueness, then emits the separately typed transport mapping. Critic element
  scores use strict list objects that can pass the structured-output boundary
  and normalize to the existing UUID-keyed persistence map. Complete critic
  domain validation runs inside the fresh two-attempt loop, action IDs and
  sliders are schema-bound, and the live canary uses the real critic schema,
  persisted-preview shape, and domain validator. The critic, Owner Console
  incident, and VPS operations skills preserve these rules.
- Verification: 24 focused Validation tests pass locally and in the Linux/amd64
  image, including the persisted mapping and critic-domain retry regressions and
  the 1080×1080 Natal render. The two-test disposable-PostgreSQL full Result
  lifecycle and the clean/idempotent schema journey pass. The in-place release
  `result-v1-20260827-1025-critic-hotfix` then passed the real critic schema,
  MIME-bearing attachment mapping, pixel inspection, and complete domain
  validator before and after cutover, alongside fresh Product Brief,
  correction, candidate, and Pexels canaries. Commander counts were preserved,
  platform counts were unchanged by the application cutover, and all three
  application services are healthy with zero restarts. Dependency, skill,
  public Auth/CORS/bundle, and immediate 1 GB/OOM audits passed. The failed run
  and its five renders remain immutable, and the operation guard is empty for a
  normal Owner Console retry.

## 2026-08-27: Instagram candidates omitted a required visual role

- Symptom: Result run `01a041d9-3a09-7fd4-af84-b9a863a57303` failed during
  its initial directions with `Instagram candidate is missing required
  structured visual roles`. Three of the five provider responses omitted
  `lighting_style`; one of those returned nine items only by substituting
  `decorative_element`.
- Cause: the structured schema allowed zero-to-32 components drawn from both
  required and optional roles. The ordinary generator prompt did not enumerate
  the required nine, while the release canary's special prompt did. Complete
  `CandidateV2` validation also ran after the bridge had already declared the
  call successful, so a schema-valid incomplete document never received the
  advertised fresh retry.
- Durable fix: the Instagram schema now requires exactly nine items and allows
  only the nine required roles. The ordinary prompt and canary share the same
  ordered role list, and full Candidate domain validation runs inside the
  bridge's two-attempt loop. A first response with a missing, duplicate,
  unauthorized, or otherwise invalid role receives one fresh provider call;
  terminal rejection carries the exact failed request provenance. The
  candidate-generator and Owner Console incident skills preserve these rules.
- Separate supplied evidence: the 681-byte inline `data:image/png` payload is
  not a PNG. Its signature ends in `00` instead of the required `0A`, and it
  has no valid PNG header/chunk classification. PTW Result artifacts remain
  authenticated JPEGs, so this malformed inline resource is not the Result
  renderer failure.
- Verification: focused schema, domain-retry, and final-failure provenance
  regressions pass. All 21 Validation tests pass in the Linux/amd64 image,
  including the 1080×1080 Natal render; the full disposable-PostgreSQL Result
  lifecycle and clean/idempotent schema journey pass. Commander tests/demo,
  Owner Gateway tests, 16 Owner web tests, production build, six desktop/
  360 px/iPhone browser journeys, canonical skill verification, and diff
  hygiene also pass locally. The in-place release
  `result-v1-20260827-0930-role-hotfix` then generated and domain-validated an
  exact-nine-role Candidate twice through the live bridge, alongside fresh
  Product Brief, correction, critic, and Pexels canaries. All Commander counts
  were preserved, platform counts were unchanged by the application cutover,
  and all three application services are healthy with zero restarts. Schema,
  dependency, skill, public Auth/CORS/bundle, and immediate 1 GB/OOM audits
  passed. The failed run remains immutable and the operation guard is empty for
  a normal Owner Console retry.

## 2026-08-27: Instagram Result failed on tool IDs parsed as UUIDs

- Symptom: Result run `01a041c0-af7c-7881-bec4-bf4ebc2d23cf` failed during
  the five initial Instagram directions with `badly formed hexadecimal UUID
  string`. Four directions returned UUID-only source references; the fifth
  mixed supplied UUIDs with `studio.*` tool IDs.
- Cause: `visual_components[*].source_ids` was an unrestricted string array in
  the structured output schema even though the domain parser required UUIDs.
  The bridge therefore accepted the model response and the later `UUID(...)`
  conversion exposed a low-level parser exception. The approved-media field
  was likewise UUID-parsed without a schema-level Project-asset allowlist.
- Durable fix: every candidate call now derives the exact UUIDv7 allowlist from
  its server-built input payload and binds that list into the structured
  schema. `media_request.source_asset_id` is separately limited to snapshotted
  approved Project assets plus `null`. The domain boundary repeats both checks
  and reports a typed candidate-contract error instead of a hexadecimal parser
  exception. The Owner Console incident skill records this identifier rule.
- Verification: the focused production-shape regression, all 19 Validation
  tests in the Linux/amd64 image, the full disposable-PostgreSQL Result
  lifecycle, the clean/idempotent schema verifier, Commander tests/demo, Owner
  Gateway tests, canonical skill verification, and diff hygiene pass locally.
  The deployment bridge audit now generates and domain-validates a real
  UUID-allowlisted `CandidateV2` instead of accepting a generic marker object.
  The in-place release `result-v1-20260827-0900-uuid-hotfix` then passed that
  real candidate boundary twice, Product Brief creation/correction, mapped
  critic, Pexels, schema, dependency, skill, public Auth/CORS/retired-route,
  and immediate 1 GB/OOM audits. All Commander counts were preserved, platform
  counts were unchanged by the application cutover, all three application
  services are healthy with zero restarts, the failed run remains immutable,
  and its operation guard is empty for a normal child retry.

## 2026-08-26: Product Brief creation returned HTTP 500

- Symptom: authenticated `POST /api/v1/briefs` returned HTTP 500. The first
  request persisted a queued Product Brief and held the singleton generation
  guard; four repeated submissions then persisted four more queued Briefs and
  failed behind the occupied guard. After the scheduling repair, a real retry
  reached the provider but failed domain validation because the returned
  document language did not match the English source.
- Cause: synchronous FastAPI handlers called `asyncio.create_task()` without a
  running event loop. Brief persistence and operation reservation were also
  separate transactions, startup recovery did not reconcile queued Briefs,
  and retries reused one provider idempotency key. Separately, the server
  inferred the source language only after generation, while the provider
  schema allowed either language. The generic marker canary did not exercise
  the real Product Brief contract, and post-response validation failures lost
  their bridge provenance.
- Durable fix: all five background-starting routes are asynchronous and
  schedule from the running loop. Product Brief persistence and guard
  reservation are atomic; contention returns 409 without an orphan row; and
  startup fails interrupted queued/generating Briefs and clears the guard.
  Each generation attempt now receives a fresh idempotency key, binds the
  server-inferred language as a schema constant and explicit prompt
  requirement, and persists provider provenance on success or rejection. The
  bridge audit now runs the canonical skill prompt, strict `ProductBriefV1`
  schema, and domain validator for creation and correction. Focused repository,
  API, service, and provider regressions cover these boundaries, and the
  Product Brief and Owner Console incident skills carry the reusable rules.
- Verification: 16 Validation tests, including the disposable PostgreSQL full
  Result lifecycle, pass locally and in the Linux/amd64 runtime image. Commander
  tests/demo, Owner Gateway tests, Owner web tests/build, desktop/mobile
  Playwright journeys, schema/corpus/skill checks, and diff hygiene pass. The
  in-place production release `result-v1-20260826-1415-language-hotfix`
  preserved every table count and required no reset. Fresh real Product Brief,
  correction, candidate, critic, and Pexels canaries passed. Retrying the exact
  original Brief completed attempt 2 as English schema v1, with distinct
  provider request lineage for failed attempt 1 and completed attempt 2; the
  guard is empty and the four duplicate Briefs remain preserved as failed.
  All three application services are healthy with zero restarts, and the public
  Auth/CORS/bundle audit plus the immediate 1 GB/OOM audit passed.

## 2026-08-25: Studio Wizard request looked inactive while it was running

- Symptom: after submitting a whole-post Studio Wizard instruction, the owner
  saw no progress and could not tell whether the request was running, had
  failed, or had changed the five templates. The request did complete and
  persisted a review-only proposal; the open recipe was not mutated.
- Cause: the browser waits on one synchronous proposal call with a bounded
  ten-minute deadline, but its only in-flight feedback was disabling a button
  without changing the label. “Whole post” did not say that scope meant only
  the currently open post, and the returned preview appeared below the form
  without an explicit nothing-changed-yet handoff.
- Durable fix: Wizard Preview and Apply now replace their button labels
  immediately, lock the submitted fields, and show an accessible indeterminate
  activity panel with elapsed time, the request limit, and mutation state.
  Scope explicitly excludes the other four posts and saved templates. Preview
  success says nothing changed yet; failure preserves the instruction and
  exposes the correct retry. The generated-person restriction is visible
  before submission, and the service-worker cache is bumped. The canonical Ad
  Studio skill now requires this lifecycle for long Wizard calls.
- Verification: 32 Owner web tests, the production build, all 21 desktop/360
  px/iPhone browser journeys, built-runtime Commander tests, the deterministic
  demo, skill validation, and diff hygiene passed before release. The in-place
  rollout then passed two fresh five-mode bridge canary rounds, Pexels,
  preservation, readiness, Firebase Hosting, and both public-console audits.
  Deliberate Commander, Validation, and Owner Gateway restarts preserved every
  baseline artifact count and the owner's existing 195023-byte review-only
  proposal; the 1 GB audit passed and its 24-hour follow-up is scheduled.

## 2026-08-25: real Studio Wizard revision failed beyond the minimal canary

- Symptom: the deployed `ad_studio_recipe_revision` canary passed, but two
  selected-headline Wizard previews returned 409 after the platform jobs failed
  during structured model execution. Neither attempt persisted a proposal or
  changed the root recipe.
- Cause: the canary used a small fully typed schema, while the real Wizard
  schema left `patch.items` and `document` as unconstrained objects. The Codex
  structured-output boundary rejected that production schema before returning
  model content.
- Durable fix: the Wizard now builds a strict schema from the immutable V2
  recipe instance. Every object forbids additional properties and requires its
  declared fields; frame and modifier variants retain existing instance/tool
  IDs and cardinality; patch entries have typed replace/target/summary fields.
  Server-side diff, component-scope, exact offer/CTA, Project, and lineage
  validation remain independent of model output. The incident skill now
  requires a real recipe-shaped Wizard canary, not only a minimal mode canary.
- Verification: the recursive strict-schema regression and all 50 Validation
  unit tests pass in the Linux/amd64 runtime image. A real selected-headline
  production preview persisted proposal
  `01a03913-eef8-7f72-b69f-cc16503d87fb` without changing its root recipe
  digest. Apply changed only the requested font size, preserved the exact
  headline text/offer/CTA, and created child recipe
  `01a03915-594d-73ee-a7e2-13a1b2ae5e66` plus render
  `01a03915-594d-7fc5-af8a-fcf4232e539b`. Two repeat Apply calls returned the
  same IDs. The applied proposal, preview digest/ETag, child, and render history
  all reloaded after restarting Validation.

## 2026-08-25: combined Studio inspection mis-displayed repeated CTA regions

- Symptom: production sample-set creation completed with valid recipes,
  manifests, and 1080×1080 JPEGs, while a combined five-image inspection
  response appeared to replace alternating CTA labels with dark rectangles.
  Opening the same files in different response positions changed which labels
  appeared absent.
- Cause: the inspection presentation mis-composited repeated CTA regions. The
  stored JPEGs were not corrupt: Pillow and ffmpeg independently decoded the
  complete CTA crops to identical pixel hashes, and OCR read the same two-line
  CTA from every file. A first diagnosis incorrectly attributed the display to
  a stale Pillow drawing context.
- Durable fix: Studio acceptance now verifies authoritative bytes, decoded crop
  hashes, OCR/pixel structure, and one-at-a-time views before classifying a
  render defect. The renderer still defensively rebinds `ImageDraw` after RGB
  composites, with a repeated-render pixel regression, but inspection chrome
  alone is no longer evidence that persisted output changed.
- Verification: the focused repeated-render regression and all 49 Validation
  unit tests pass in the Linux/amd64 runtime image. The in-place release passed
  fresh five-mode bridge, Pexels, schema, dependency, restart, resource, and
  public-console audits. All five replacement JPEGs are 1080×1080, their ZIP
  matches its declared SHA-256, and independent ffmpeg crop hashes plus OCR
  confirm the exact CTA in every export.

## 2026-08-25: Studio graphic canary rejected the current Codex trace shape

- Symptom: the in-place five-post release passed the three retained validation
  modes and the JSON-only Studio revision mode, then stopped before migrations
  because the Studio graphic canary reported `must call imagegen exactly once`.
  The release guard restored the prior platform API and worker; Commander,
  Validation, Owner Gateway, PostgreSQL, and Hosting were not cut over.
- Cause: the bridge worker counted only the older
  `item.completed`/`mcp_tool_call`/`image_gen`/`imagegen` JSONL tuple. The live
  CLI completed image generation but emitted no distinct tool-completion item;
  its fresh session instead contained one built-in
  `exec-<request-uuid>.png` receipt. The first recovery broadened event parsing
  but still rejected that verified receipt-only behavior.
- Durable fix: when Codex emits a completed MCP-shaped or dedicated image call,
  the worker counts and deduplicates that event. When it emits no call event,
  the worker requires exactly one session-scoped `exec-<request-uuid>.png`
  receipt. It still validates exactly one bounded PNG, and rejects arbitrary
  filenames, zero or multiple receipts/events, prompt-text claims, unsafe
  paths, invalid bytes, or digest disagreement. The platform operations
  contract and VPS skill cover both proof forms.
- Verification: the complete platform suite passes. The successful in-place
  retry ran fresh live five-mode bridge canaries twice, including exactly one
  bounded Studio graphic and authenticated digest/ETag asset download, before
  and after the application dependency gate. The serial release, services,
  PostgreSQL schema, resource audit, and public Owner Console checks passed.

## 2026-08-24: malformed inline PNG reported as a resource failure

- Symptom: the browser reported a resource-load error for an inline
  `data:image/png;base64,...` payload while the owner was inspecting Ads.
- Cause: the supplied payload is not a valid PNG. Its eight-byte signature ends
  in `00` instead of the required `0a`, it has no valid initial image chunk, and
  the 683 decoded bytes are incomplete. PTW does not emit inline PNGs for Ads:
  it owner-authenticates the authoritative JPEG response and displays a local
  `blob:` URL. All five production assets independently decode as 1080×1080
  JPEGs, match their stored SHA-256 values, and pass HTTP media-type, ETag, and
  byte-equality checks. No PTW API or stored-asset failure was found.
- Durable fix: the Owner Console now verifies the authenticated response's
  exact `image/jpeg` media type, SHA-256, and exposed ETag before constructing
  the browser Blob. HTTP, empty-body, MIME, integrity, ETag, and browser-decode
  failures render an explicit Ads alert with the Creative UUID and one bounded
  retry instead of leaving only a browser resource error. The incident skill
  records how to distinguish PTW JPEG/blob delivery from unrelated malformed
  inline PNG resources.
- Verification: 15 Owner web unit tests, the production build, 15 desktop/
  360 px/iPhone browser journeys, 15 active Owner Gateway built-image tests,
  Commander tests/demo, skill validation, and live five-asset integrity checks
  pass. Matching application images and the v31 Owner Console are live; the
  independent platform release is unchanged. The public bundle/Auth/CORS audit,
  serial restart, repeated five-asset integrity check, and immediate 1 GB/OOM
  audit pass. The prior failure-notification audit count remains unchanged, and
  the scheduled 24-hour resource audit remains active.

## 2026-08-24: valid Ad offer failed on terminal punctuation

- Symptom: creative batch `01a03327-a038-72a6-85ae-e50983b0e6f4` failed with
  only `every creative must retain the Product Brief offer exactly` in Ads and
  no Telegram notification.
- Cause: the approved offer was `Free 15-minute mentor call.`. All five bridge
  drafts preserved its words, but curiosity and problem-first continued the
  sentence after `call`, so a raw substring check required the Brief's terminal
  period in the middle of a sentence. The documented per-creative offer was
  also absent from the structured output schema, and the UI exposed only the
  validator exception.
- Durable fix: every creative now has exact schema-bound `cta` and `offer`
  fields. Visible copy must retain normalized offer wording but may use normal
  surrounding sentence punctuation. Failure messages identify the ordinal and
  angle; Ads explains the rule, approved offer, atomic rollback, and Telegram
  state. A terminal failed batch reserves an append-only audit event before one
  direct send through the existing allowlisted bot, records sent/failed/
  ambiguous/suppressed, and never auto-retries ambiguous delivery. The API
  retains the latest failed attempt after a successful retry so Ads can show a
  recovered-incident summary instead of erasing the original reason.
- Verification: the first incident release passed built-image and disposable-
  PostgreSQL suites, bridge/dependency/public-console audits, delivered one
  audited message for the original attempt, and completed retry attempt 2 with
  five unique verified 1080×1080 JPEGs whose offers and CTAs match the approved
  Brief exactly. The recovered-history follow-up passed 25 Validation tests,
  15 active Owner Gateway tests, 12 Owner web unit tests, 12 desktop/360 px/
  iPhone journeys, and three disposable-PostgreSQL integration tests. Production
  runs matching application images, the public v30 cache/Auth/CORS/retired-route
  audit passes, and the independent platform release is unchanged. Serial
  restart preserved the completed batch, original reason, sent notification,
  empty operation guard, and exactly one notification reservation/result pair;
  the immediate 1 GB/OOM audit also passes.

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
