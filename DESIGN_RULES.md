# PTW owner-console rules

Status: canonical
Updated: 2026-09-04

## Navigation and trust

- Navigation contains Brief, Post, Landing, Ads, Commander and Settings.
- The Project selector appears only in project-scoped destinations, never Commander or Settings.
- The lower navigation controls include a compact Settings control. The language
  switcher lives inside Settings. Settings always retains ChatGPT Authorization,
  including when local GOD mode is available. It may expose authorization state and the
  device-login URL/code only; access and refresh tokens, CLI output, and provider
  credentials never enter browser state, API responses, or logs.
- Commander is one conversation workspace at `?page=commander`: compact header,
  history drawer, Markdown timeline and sticky composer. Mode, available model
  and compatible effort controls sit beside messages. Reply quotes its target;
  Send steers active work and Stop remains separate. Questions and release
  outcomes belong in the timeline, not unrelated page panels. Explicit deploy
  instructions and Deploy need no second confirmation. Always distinguish newer
  local changes from an earlier successful release.
- Design first for 360px and one-hand use with 44×44 CSS-pixel targets, no
  horizontal overflow, keyboard access, and reduced-motion support.
- Empty state is valid. Never seed fake Briefs, metrics, proof, testimonials,
  urgency, scarcity, or assets.

## Product Brief

- One raw idea creates one Project, permanent Source, and immutable Brief.
- Correction creates a new complete Brief with feedback and weight lineage.
- Approval requires an honor confirmation and a common-template selection.
  Phone Metrics also requires a style and background treatment before Studio
  AI starts its first hero image. Approval returns the reserved creative and
  navigates to its Post progress screen.

## Post Studio

- Every creative belongs to the selected Project and one approved Brief.
- Common templates are square `universal_ad` and 4:5 `phone_metrics`.
  Template code remains common; a creative stores only bounded state and the
  selected template version/digest.
- Show generation progress as queued, composing, generating image when
  applicable, then editable draft. Failures expose stage-specific retry.
- Natal is fixed. Arbitrary primitive edits, template imports, owner logo
  replacement, and unsupported fields do not enter the editor.
- Phone hero generation is text-free, keeps three selectable raw images, and
  may enhance exactly the selected raw hero. The checked-in phone frame is
  digest-verified and never fetched at runtime.
- The saved Phone hero direction has a 44px edit/reset control. Replacing it
  keeps the current image and history intact until Generate is pressed again.
- Save creative and Approve creative atomically include all pending edits.
  A changed checkpoint shows its edit summary, automatic Project lesson, and
  sanitized global proposal with Apply globally/Keep project-only actions.
  Live edits, no-op saves, and the initial AI baseline never teach the agent.
- Preview/history/version responses are authenticated, digest-checked, and
  no-store. Approval stores the exact state and PNG as an immutable version.
- Loopback Tune mode remains guarded and absent from production routes.

## Landing Studio

- Every app uses the canonical Natal logo and name. Page themes may style components
  but never substitute another app identity or request a new brand kit.
- Every service is experienced through a Natal app. The Landing hero demonstrates
  one editable, Brief-grounded task inside Post Studio's canonical phone frame.
  Bounded screen themes/layouts and copy are separate from generated text-free art.
  UI row interactions are local demonstrations; the phone action uses the page CTA.
- Coordinated page themes remain editable through bounded component controls.
  Per-image Post style/background presets are persisted and expanded into generation
  and enhancement prompts; changing a style alone does not regenerate existing art.

- A Landing belongs to the selected Project, its approved Brief, and one immutable
  approved Post version. It captures Post style once and does not synchronize later edits.
- Its fixed order is Hero, three features, optional owner evidence social proof, one generated
  visual break, contacts, and three FAQs. Each has bounded editable controls.
  Approved versions have an explicit publication action; private drafts remain protected.
  No page builder, form submission, or lead storage exists.
- Hero and visual-break artwork inherit the frozen Post visual profile, are text-free,
  digest-checked, private/no-store, and retain at most three selected raw images per slot.
- Approval requires both visuals, essential section copy, all FAQs/features, and at least
  one validated email, phone, or HTTPS contact endpoint. Proof is optional and absent
  entries are hidden; supplied entries require complete statements and attribution.
  A direct CTA requires its selected endpoint. Validate before persisting approval.
  Landing learning remains
  in its own global/Project namespaces and never changes Post learning.
- Edit mode selects bounded sections directly; Preview mode enables page navigation,
  contacts, and collapsed FAQs. The same renderer serves 1280/768/360px and fullscreen.
  Phone layouts switch between inspector and preview. All selectable browser fonts
  are bundled, page language is independent of console language, and long copy wraps.

## Removed surfaces

- There is no separate Studio page, owner-wide workspace, retired Social Post
  workflow, review grid, notification, analytics, or automatic optimization action.
- Approved Post versions support single-image Instagram publication and export.
  Website and Direct ads stay in Ads; all new Meta objects are PAUSED. Launch and
  schedule changes happen in Ads Manager. Export never implies publication.
- Retain the promotional CTA inside both Post renderers and its editor controls.
  The website ad’s native Learn more CTA is separate and links to the server-resolved
  published Landing. Organic images do not gain clickable buttons.
- Bare Studio mutations, `/api/v1/posts`, historical payload adapters, and
  migration/assignment UX do not exist.

## Caching and reset

- Cache only public shell resources. Never cache APIs or authenticated renders.
- Production reset names only `ptw_commander.public`, preserves the independent
  platform database, and requires `RESET PTW PRODUCTION`.
