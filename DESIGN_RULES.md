# PTW Validation owner-console rules

Status: canonical
Updated: 2026-08-24

## Product and navigation

- The Brief/creative language is inferred as Ukrainian or English from the raw
  idea. IDs, source text, logs, and provider errors remain verbatim.
- Primary navigation is Product Briefs, Ads, Landing, and Admin. Admin
  contains Jobs plus Docs/System/Terminal.
- Old page locations redirect to Product Briefs. Old domain APIs do not exist.
- Design first for 360 px and one-hand use, with 44×44 CSS pixel targets, no
  horizontal page overflow, keyboard access, and reduced-motion support.
- Keep active Owner Console chrome strictly monochrome: black, white, and
  neutral grays only. Communicate selection, success, failure, and destructive
  state with contrast, borders, patterns, icons, and text rather than hue.
  Reviewed Ad photography may remain full color.

## Product Briefs

- Start from one raw idea only. Show Brief and owner-idea Source UUIDs.
- Present one product, first customer, pain, promise, three to five benefits,
  CTA, trust strategy, and a visually prominent strong offer.
- A correction creates a complete immutable replacement with a new UUID.
- Approval must explicitly say the owner can honor the promise and offer; it
  starts exactly one five-creative batch.

## Ads and Landing

- Ads shows all five complete posts, exact UUIDs, angle, copy, authenticated
  1080×1080 image, artifact digest, Pexels photographer/source/license
  attribution, retry state, and feedback control for each creative.
- Landing shows only `Stage 3 pending`; it has no active controls or API calls.
- There is no campaign, publish, traffic, UTM, click, or analytics action.
- Product/creative generation never invents proof, testimonials, ratings,
  customer results, urgency, or scarcity.

## Admin
- Plan and Execute remain visibly distinct and digest-bound. The root terminal
  is labelled break-glass and retains bounded lifetimes.
- The irreversible reset preview names only `ptw_commander.public` and requires
  `RESET PTW PRODUCTION`.

## Trust and caching

- Empty production state is valid. Never seed fake Briefs, creatives, proof,
  or assets.
- PWA caching is limited to public shell resources. API, authenticated images,
  terminal, and sensitive responses are never cached by the service worker.
- Do not show invented metrics, proof, testimonials, urgency, scarcity,
  limitations, or competitive facts.
