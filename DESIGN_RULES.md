# PTW Validation owner-console rules

Status: canonical
Updated: 2026-08-24

## Product and navigation

- The Brief/creative language is inferred as Ukrainian or English from the raw
  idea. IDs, source text, logs, and provider errors remain verbatim.
- Primary navigation is Product Briefs, Ad Studio, Ads, Landing, and Admin. Admin
  contains Jobs plus Docs/System/Terminal.
- A global human-readable Project switcher scopes Product Briefs, Ad Studio, Ads, and
  Landing. Keep Project, Brief, and batch UUIDs visible as metadata rather than
  using raw UUIDs as selector labels. Admin remains global.
- Old page locations redirect to Product Briefs. Old domain APIs do not exist.
- Design first for 360 px and one-hand use, with 44×44 CSS pixel targets, no
  horizontal page overflow, keyboard access, and reduced-motion support.
- Keep active Owner Console chrome strictly monochrome: black, white, and
  neutral grays only. Communicate selection, success, failure, and destructive
  state with contrast, borders, patterns, icons, and text rather than hue.
  Reviewed Ad photography may remain full color.

## Product Briefs

- Start from one raw idea only. Generating the initial Brief atomically creates
  and selects its Project. Show Project, Brief, and owner-idea Source UUIDs.
- Present one product, first customer, pain, promise, three to five benefits,
  CTA, trust strategy, and a visually prominent strong offer.
- A correction creates a complete immutable replacement with a new UUID.
- Approval must explicitly say the owner can honor the promise and offer; it
  starts exactly one five-creative batch.

## Ads and Landing

- Ad Studio is a parallel manual workspace and does not replace the automatic
  five-Ad generator. It uses constrained framed tools with visible semantic IDs,
  immutable Project brand-kit and recipe revisions, and reusable Project
  templates. Applying a template rebinds the selected approved Brief's exact
  offer and CTA.
- Studio canvas output may use Project colors; all editor chrome remains
  monochrome. Only explicitly published renders become feedback targets and
  training examples.

- Ads shows only batches from the selected Project and labels generations by
  origin, product, status, and time. It still shows all five complete posts,
  exact UUIDs, angle, copy, authenticated
  1080×1080 image, artifact digest, Pexels photographer/source/license
  attribution, retry state, and feedback control for each creative.
- A failed batch shows the actionable validation rule, approved offer when
  relevant, atomic rollback outcome, and audited Telegram delivery state. Keep
  the latest failed attempt visible after a successful retry.
- Landing shows only `Stage 3 pending`; it has no active controls or API calls.
- There is no campaign, publish, traffic, UTM, click, or analytics action.
- Product/creative generation never invents proof, testimonials, ratings,
  customer results, urgency, or scarcity.

## Admin
- Jobs use one review-first flow: describe the job, review the read-only steps,
  then explicitly run them. Planning and execution remain visibly distinct and
  digest-bound without exposing a misleading mode switch. The root terminal is
  labelled break-glass and retains bounded lifetimes.
- The irreversible reset preview names only `ptw_commander.public` and requires
  `RESET PTW PRODUCTION`.

## Trust and caching

- Empty production state is valid. Never seed fake Briefs, creatives, proof,
  or assets.
- PWA caching is limited to public shell resources. API, authenticated images,
  terminal, and sensitive responses are never cached by the service worker.
- Do not show invented metrics, proof, testimonials, urgency, scarcity,
  limitations, or competitive facts.
