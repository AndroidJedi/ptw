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
- Running state shows only: Creating five directions, Improving the strongest
  direction, Final review, elapsed/bounded maximum, and retry/failure state.
- Completed state is a platform-native Instagram square or TikTok vertical
  photo mock post. Redundant source, hook/headline/body/CTA transcription, and
  rationale are absent. Alt text, metadata, and bounded decision trace live in
  one collapsed advanced panel.
- Ready appends accepted feedback and unlocks image/copy export. Improve
  requires a 3–2000 character comment, appends rejected feedback plus a
  zero-delta WeightUpdate, and creates a lineage-linked child run. Review state
  is always the latest immutable feedback projection.
- Do not expose templates, sliders, alternate candidates, UUID entry, layers,
  recipes, prompts, or model controls in the normal journey.
- Universal Ad Studio exposes only the fixed background, optional sticker,
  hero title, supporting text, optional bullets, CTA, and optional logo roles;
  meaningful mood/layout controls; three fixed asset slots; and immutable
  version approval. Primitive trees, arbitrary properties, references,
  calibration, and template-library controls remain internal or absent.
- Loopback-only Tune mode may expose a Test generation wizard for project idea,
  desired implementation, and iterative feedback. It must isolate code changes,
  enforce a Studio-only file allowlist, verify before copy-back, and remain
  absent from production Owner Gateway and Validation route surfaces.
- Studio preview and immutable-version renders are authenticated,
  digest-checked, and no-store. Approval stores the exact PNG, configuration,
  semantic content, asset provenance/digests, and internal template digest.
- A collapsed owner-only explanation may show all five initial candidate
  previews, their exact five parameter values, and a visual rendering of the
  persisted gate, score, ranking, pairwise, action, observation, and final-
  selection trail. Deeper debug may expose bounded versions, IDs, digests,
  retry counts, and lineage. Neither surface may expose chain-of-thought,
  credentials, raw attachment base64, or unrestricted source contents.
- There is no publishing, campaign, traffic, UTM, analytics, or optimization
  action.

## Caching and reset

- Cache only public shell resources. Never cache API, authenticated render,
  debug, or feedback responses.
- The reset preview names only `ptw_commander.public`, explicitly states that
  the independent platform database is preserved, and requires
  `RESET PTW PRODUCTION`.
