---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Product Briefs, Results, Commander, Validation, the platform bridge, PostgreSQL, Pexels, deterministic rendering, and the existing Telegram emergency boundary.
---

# PTW Owner Console Incident

Trace a public symptom through browser → Firebase Hosting/Caddy → Owner Gateway
→ Validation → PostgreSQL or the independent structured bridge/Pexels API. A
healthy Gateway alone does not prove Product Brief or Result readiness.

## Public boundary

- Verify hashed bundles, the `ptw-result-v1` service-worker cache, Firebase Auth
  persistence, App Check, exact Owner CORS origins, and unauthenticated
  rejection.
- Navigation is exactly Product Briefs and Result. The normal Result journey
  exposes one approved Brief, Text/Instagram choice, one task, three bounded
  progress labels, one final immutable Result, its selection summary,
  Download/Use, retry, feedback, and a collapsed bounded trace.
- Ads, batches, Studio editor/Wizard, Landing, Admin/Jobs/terminal, Positioning,
  research, publishing, campaign, traffic, UTM, and public lead routes must be
  absent and return 404.
- Result images are owner-authenticated JPEG responses displayed through
  `blob:` URLs. Validate stored bytes, SHA-256, dimensions, content type, ETag,
  and proxy byte equality before debugging browser decode failures.
- Never expose template controls, internal alternatives, prompt secrets, raw
  base64, credentials, or require the owner to enter a UUID.

## Stage checks

- Product Brief: raw idea only; inferred `uk` or `en`; one strict hypothesis;
  exact bounded document; immutable correction; owner approval of promise and
  offer; no research/SEO/YouTube call.
- Context: only approved Brief, task Source, current Project brand kit, approved
  Project assets, bounded tool catalog, one template, deterministic writing
  references, and four to six positive excerpts. Overflow fails explicitly.
- Generation: exactly five distinct template IDs, isolated calls, server UUIDv7
  elements, exact offer/CTA, honest claims, and candidate eligibility only after
  schema/media/recipe/render/protected-copy checks.
- Critic: exactly three logical passes; anonymous template identity; five, five,
  then two active candidates maximum; four improvement calls total; bounded
  slider changes; no generation in pass three; fail closed when nothing is
  eligible.
- Instagram: approved/Pexels real image or explicitly allowed reviewed
  non-human graphic; one square `StudioRecipeV2`; exact 1080×1080 JPEG; safe
  crop, collision, hierarchy, legibility, brand, caption, and alt-text gates.
- Feedback: resolve the displayed final Creative UUID server-side and append
  HumanFeedback, zero-delta WeightUpdate, generator and critic lesson proposals,
  outcomes, and required `evaluates`, `adjusts`, `contains`, and `derived_from`
  edges. Skills never learn silently.

## Failure handling

- Any FastAPI route that schedules `asyncio` background work must itself be an
  async route and have a built-image HTTP regression proving it returns the
  accepted response while the task starts. A healthy service plus
  `RuntimeError: no running event loop` in Validation logs means a synchronous
  route was dispatched to FastAPI's worker thread.
- Product Brief persistence and the singleton generation reservation must
  commit atomically. Busy admission returns an explicit conflict without
  leaving another queued Project or Brief. On startup, fail both queued and
  generating orphan Briefs as interrupted and clear their operation guard so
  the owner can retry one immutable artifact.
- Bind the server-inferred Product Brief language as a structured-schema
  constant, include the generation-attempt number in the bridge idempotency
  key, and persist bridge request provenance even when post-response domain
  validation fails. The release canary must validate a real `ProductBriefV1`,
  not a generic marker object.
- Persist checkpoints after every candidate, render, critic pass, action, and
  final materialization. Resume only idempotent JSON stages and deterministic
  rendering. Never duplicate reserved candidates, actions, Results, or calls.
- A failed initial template after its one fresh JSON retry fails the run. An
  ambiguous graphic call terminates it without retry. Incomplete runs remain
  internal and are never exposed as a Result.
- Preserve exact provider request IDs and failed retry provenance. Present an
  actionable failure and create a new immutable child run on owner retry.
- For offer/CTA failures, compare byte-exact protected fields from Brief,
  candidate, recipe, rendered text, and final Result. Never truncate or rewrite
  protected copy to make a render pass.

## Release acceptance

Run the clean-schema verifier, bridge and Pexels canaries, built-image tests,
Commander tests/demo, skill verification, Owner Gateway tests, Owner web
tests/build/Playwright at desktop/360 px/iPhone widths, restart-stage tests,
`git diff --check`, the dependency audit, public live audit, and the 1 GB audit.

Telegram remains notifications plus `/help`, `/status`, and `/stop`. Before
claiming it works, verify the deployed help text, authorization, established
poller ownership, real end-to-end response, emergency persistence/restart, and
failure path. Do not add another poller, webhook, command, or token.
