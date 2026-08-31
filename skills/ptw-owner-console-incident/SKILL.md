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
- Deployed production navigation remains exactly Product Briefs and Instagram
  post until an explicitly authorized Universal Ad Studio release. The local
  owner-only Studio may be a third destination without entering the normal
  Result journey. The normal post journey exposes one approved Brief, one
  create action, three bounded progress labels, one final immutable post, its
  selection summary, Download/Use, retry, feedback, and a collapsed bounded
  trace. Never expose a Text profile or task field.
- Provision the digest-pinned Natal logo, palette, and Inter brand kit on the
  server before an Instagram run. The public Gateway and Owner Console must not
  expose Project asset upload or brand-kit setup routes, fields, or blockers.
- The EN/УКР control must change the complete visible Owner Console and persist
  across reloads. Render new-Project creation as a separate mode from an
  existing Project's Brief history and detail; never stack both workflows.
- Ads, batches, the retired Studio editor/Wizard, Landing,
  Admin/Jobs/terminal, Positioning, research, publishing, campaign, traffic,
  UTM, and public lead routes must be absent and return 404. Do not confuse the
  retired Studio product with the bounded owner-only Universal Ad Studio.
- Result images are owner-authenticated JPEG responses displayed through
  `blob:` URLs. Validate stored bytes, SHA-256, dimensions, content type, ETag,
  and proxy byte equality before debugging browser decode failures.
- Never expose template controls, internal alternatives, prompt secrets, raw
  base64, credentials, or require the owner to enter a UUID.

## Stage checks

- Product Brief: raw idea only; inferred `uk` or `en`; one strict hypothesis;
  exact bounded document; immutable correction; owner approval of promise and
  offer; no research/SEO/YouTube call.
- Context: only approved Brief, the fixed server-owned Instagram task Source,
  canonical Natal brand kit, approved Project/Pexels assets, bounded tool
  catalog, one template, deterministic writing references, and four to six
  positive excerpts. Overflow fails explicitly.
- Generation: exactly five distinct template IDs, isolated calls, server UUIDv7
  elements, exact offer/CTA, honest claims, and candidate eligibility only after
  schema/media/recipe/render/protected-copy checks.
- Critic: exactly three logical passes; anonymous template identity; five, five,
  then two active candidates maximum; four improvement calls total; bounded
  slider changes; no generation in pass three; fail closed when nothing is
  eligible.
- Local Universal critic exception: independently screen three action-free
  candidates, then independently screen two action-free candidates, then send
  only those two group winners plus both structured screening summaries.
  Require exact attachment counts `[3, 2, 2]`; never send all five local images
  in one call or carry Pass 1 summaries into the independent Pass 2 screen.
- Instagram: approved/Pexels real image or explicitly allowed reviewed
  non-human graphic; one square `StudioRecipeV2`; exact 1080×1080 JPEG; safe
  crop, collision, hierarchy, legibility, brand, caption, and alt-text gates.
- Universal Ad Studio: expose only one `universal_ad` catalog entry and the
  background, optional sticker, hero title, supporting text, optional bullets,
  CTA, and optional logo roles. Require strict bounded configuration, exactly
  the `background_image`, `sticker_object`, and `logo` asset slots, Pexels
  provenance for sourced media, and the single documented sticker cutout.
  Preview and immutable-version PNGs must be authenticated, no-store, digest-
  and ETag-checked. `/studio/templates`, arbitrary operations, references, and
  calibration routes must remain absent.
- Configured Instagram rendering requires exactly five digest-synchronized v3
  strategy/Studio definitions. Each must have a distinct component-tree
  signature and materially distinct decoded render from one fixed input. Never
  repair sameness with renderer branches: validate the predefined catalog,
  immutable template snapshot, protected bindings, exact sliders, ordered typed
  patch, component UUID map, parent lineage, and enriched manifest. Run
  `python3 -m validation_pipeline.verify_studio_templates` in the built image;
  any recipe replay, pixel replay, manifest, or pairwise-distinction failure
  blocks release.
- If all final candidates fail despite an adequate Brief, compare candidate
  fields, active Studio bindings, persisted pixels, and critic observations.
  The generator must receive the exact Studio snapshot; visible headline/body
  must bind to `headline`/`primary_text`; the critic must receive resolved
  frames; improvements must change their declared pixels. Reject localized
  static template copy and require the dark Natal logo to sit on the topmost
  containing light surface. Never tell the owner to clarify a fixed server task
  or upload an asset through a Console that exposes neither control.
- Feedback: resolve the displayed final Creative UUID server-side and append
  HumanFeedback, zero-delta WeightUpdate, generator and critic lesson proposals,
  outcomes, and required `evaluates`, `adjusts`, `contains`, and `derived_from`
  edges. Skills never learn silently.

## Failure handling

- Treat the Universal Studio state digest as the concurrency boundary across
  configuration, semantic content, asset digests, and source metadata. A stale
  save must conflict. For an approval incident, replay the active
  `STUDIO_WORKSPACE_PATH` state and verify exact PNG, configuration, content,
  asset provenance/digests, primitive snapshot/digest, and render digest.
- If Pexels sticker isolation removes the object or produces a poor complex-
  scene cutout, select another simple object source or use an owner-supplied
  transparent PNG/WebP. Do not add a second sticker family or hide the
  transformation provenance.
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
- Bind Instagram candidate output to exactly the nine required visual roles;
  unrestricted role arrays allow schema-valid drafts to omit `lighting_style`
  or replace it with decoration. Run the complete `CandidateV2` domain
  validator inside the provider's two-attempt loop so a schema-valid but
  incomplete first response receives the promised fresh retry. The ordinary
  generator prompt and the release canary must use the same explicit role list.
- Build critic attachments from the canonical persisted preview shape:
  `candidate_id`, `bytes`, `sha256`, `mime_type`, `width`, and `height`. Validate
  the stored JPEG content type, profile-specific exact dimensions, digest, byte
  bounds, and candidate uniqueness before transport. Production profiles use
  their full-size preview. The loopback Universal experiment uses only its
  persisted 480×480 analysis derivative bound to the authoritative 1080×1080
  PNG and preview digests; never downscale ephemerally inside the provider. The
  release canary must use this same pre-encoding field set; omitting
  `mime_type` can hide a mapper mismatch. Run complete critic-domain validation
  inside the provider's two-attempt loop, not after a schema-only success.
- Candidate identifier arrays must be constrained in the structured output
  schema to the exact server-supplied UUID allowlist. Never leave
  `visual_components[*].source_ids` as unrestricted strings: tool IDs can then
  pass bridge validation and fail later as a raw UUID parser error. Constrain
  `media_request.source_asset_id` separately to approved Project asset UUIDs
  plus `null`, and repeat both checks at the domain boundary. The release
  canary must generate and domain-validate a real Candidate with these exact
  schema constraints; a generic marker object does not prove this boundary.
- Preserve exact provider request IDs and failed retry provenance. Present an
  actionable failure and create a new immutable child run on owner retry.
- A failed local Result with persisted candidates or critic passes must expose
  its bounded intermediate evidence without requiring a final Result: all five
  authenticated previews, each candidate's screening pass, hard-gate failures,
  weighted and dimension scores, eligibility, reason codes, rankings,
  pairwise results, observations, and explicit no-selection decision. Never
  collapse completed critic work into only the terminal exception string.
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
