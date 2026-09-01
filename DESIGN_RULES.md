# PTW Result owner-console rules

Status: canonical
Updated: 2026-08-30

## Navigation and trust

- Primary navigation is Product Briefs, Social posts, and owner-only Universal
  Ad Studio. Social posts has one compact Project selector and keeps historical
  post selection in the selected-result toolbar; Project creation and renaming
  stay in Product Briefs. Studio is a separate one-template workspace.
- Old page locations and retired domain APIs do not exist.
- Design first for 360 px and one-hand use with 44×44 CSS-pixel targets, no
  horizontal overflow, keyboard access, and reduced-motion support.
- Console chrome is monochrome. A final reviewed creative uses Natal colors and
  may use full-color approved photography.
- Empty production state is valid. Never seed fake Briefs, creatives, metrics,
  proof, testimonials, urgency, scarcity, or assets.

## Product Brief

- One raw idea creates one Project, permanent Source, and complete immutable
  Brief.
- A correction creates a new UUID and complete replacement.
- Approval explicitly confirms that the promise and exact offer can be
  honored, then opens Social posts. It does not auto-generate.

## Result

- Normal input is an approved Brief plus Instagram or TikTok. The server maps
  the platform to a fixed task/profile and supplies the canonical Natal
  identity; there is no text-profile choice, task field, asset upload, or
  brand-kit form.
- Running state shows only queued/generating five directions, elapsed/bounded
  maximum, and retry/failure state.
  The loopback-only local review flow also shows one confirmation-gated
  Terminate action while a run is active; production Owner Console does not
  expose it.
- Awaiting-review state shows exactly five authenticated Creative cards.
  Selecting one enables Approve or Tune; Regenerate all applies to the set.
  Tune requires a 3–2000 character comment and replaces one slot. Approved
  state shows the native post and unlocked export.
- Owner actions append feedback, WeightUpdates, rules, snapshots, outcomes, and
  graph lineage immediately. Do not show subjective scores, ranks, comparisons,
  eligibility judgments, or automatic choice.
- Do not expose templates, sliders, UUID entry, layers,
  recipes, prompts, or model controls in the normal journey.
- Social posts remains a creation/review surface in production and loopback. It
  does not expose Project asset upload/Pexels sourcing, duplicate local Project
  evidence or run/snapshot history, or explanatory copy about server integrity
  checks and absent automatic evaluation. Asset sourcing belongs to Studio.
- Universal Ad Studio exposes only the fixed background, optional sticker,
  hero title, supporting text, optional bullets, CTA, and optional logo roles;
  meaningful mood/layout controls; three fixed asset slots; and immutable
  version approval. Primitive trees, arbitrary properties, references,
  calibration, and template-library controls remain internal or absent.
- Every local five-direction generation must contain exactly three image-backed
  candidates sourced as three fresh, distinct Pexels photographs with retained
  provider/license provenance and visibly different treatments. Generated,
  procedural, bundled, or repeated image fallbacks are forbidden. A visible
  sticker must be an isolated ultra-realistic Pexels photograph whose lighting,
  palette, material, grain, perspective, and surface treatment fit its
  background. The logo is a transparent mark only: no renderer backing surface
  or editor backing controls are allowed.
- Loopback-only Tune mode may expose a Test generation wizard for project idea,
  desired implementation, and iterative feedback. It must isolate code changes,
  enforce a Studio-only file allowlist, verify before copy-back, and remain
  absent from production Owner Gateway and Validation route surfaces.
- Studio preview and immutable-version renders are authenticated,
  digest-checked, and no-store. Approval stores the exact PNG, configuration,
  semantic content, asset provenance/digests, and internal template digest.
- Owner learning may show ID-explicit actions, child lineage, exact comments,
  active Project rules, digests, and notification state. It may not expose
  chain-of-thought, credentials, raw media bytes, or unrestricted sources.
- There is no publishing, campaign, traffic, UTM, analytics, or optimization
  action.

## Caching and reset

- Cache only public shell resources. Never cache API, authenticated render,
  review, export, notification, or feedback responses.
- The reset preview names only `ptw_commander.public`, explicitly states that
  the independent platform database is preserved, and requires
  `RESET PTW PRODUCTION`.
