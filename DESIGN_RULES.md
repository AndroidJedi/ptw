# PTW Result owner-console rules

Status: canonical
Updated: 2026-08-26

## Navigation and trust

- Primary navigation is Product Briefs and Instagram post, scoped by a
  human-readable Project switcher.
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
  honored, then opens the Instagram post action. It does not auto-generate.

## Result

- Normal input is one approved Brief summary and Create Instagram post. The
  server supplies the fixed task and canonical Natal identity; there is no
  text-profile choice, task field, asset upload, or brand-kit form.
- Running state shows only: Creating five directions, Improving the strongest
  direction, Final review, elapsed/bounded maximum, and retry/failure state.
- Completed state shows one final Instagram post, its caption, two-to-four
  selection observations, Download/Use post, Create another, and simple
  feedback.
- Do not expose templates, sliders, alternate candidates, UUID entry, layers,
  recipes, prompts, or model controls in the normal journey.
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
