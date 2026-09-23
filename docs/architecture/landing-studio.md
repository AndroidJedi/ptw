# Project-scoped Landing Studio

Landing / Лендінг is the third private Owner Console destination and the owner
of Natal's bounded publication workflow. A private Landing belongs to one
Project and starts from one immutable approved Post version plus its source
approved Product Brief. Publishing exposes only an explicitly selected approved
Landing version. The public shell emits the bounded cookieless first-party
events defined in
[Analytics and reviewed Creative Skills](analytics-and-creative-learning.md);
Landing still has no forms, lead storage, or public Project directory.

## Bounded page contract

The sole v4 page template keeps this semantic order: Hero, three feature cards,
social proof, a generated visual break, contacts, and three FAQs. The owner can
edit bounded content and theme/layout controls but cannot add HTML, CSS,
scripts, arbitrary sections, or reorder the composition. Hero and visual-break
art are independently generated owner-directed PNGs; each retains its newest three
digest-checked raw images and supports exact-image enhancement and selection.
Both image prompts also accept the shared optional [Image Reference input](post-studio.md#phone-metrics). Uploaded references are temporary
operation inputs, never Landing assets or saved page state.

Initial AI composition receives the approved Brief, the frozen Post version’s
design snapshot, the live Landing catalog, and active typed Project/global
Creative Skills. It records their exact snapshot IDs/digests. It must not invent
social proof or contact endpoints. Evidence is optional:
zero entries hide the entire section, while supplied entries require a heading,
statement, and attribution. One validated email, phone, or direct Telegram bot
link is required
before approval, together with both visuals, essential copy, all three features,
and all three FAQs. A direct CTA also requires its selected endpoint. Approval
validates pending content and its note before writing workspace files or a version.

## Authority and lifecycle

The first page for a Post version is idempotently reserved. A variant is
available only after the latest sibling has an immutable approved version. A
Landing captures its source Post snapshot at reservation; future Post edits
never synchronize into it.

PostgreSQL stores Landing metadata, workspace files, visual bytes, composition
and visual generation runs, immutable versions, and checkpoints with explicit
Project, Brief, and Post-version graph lineage. Historical Save-era Landing
learning rows remain preserved but inactive; reviewed typed rules use the shared
Analytics authority. Loopback provides the
same append-only metadata contract and per-page workspace files. Editor APIs are
authenticated and Project/page scoped under `/api/v1/landings`; visual bytes are
private and `no-store`.

Migration `004_public_landing_v1.sql` adds one stable `landing_publications`
record per Project and append-only `landing_publication_events`. First Publish
requires a selected approved version plus a manually confirmed `ai`, `la`, or
`wa` lane and a 3–63 character lowercase ASCII slug. `(namespace, slug)` is
unique and permanent: rename, Unpublish, and republish never change or release
it. Each publish event points to the exact immutable Landing version. A later
publish atomically changes the current version, so publishing an earlier event
is the rollback mechanism. Unpublish appends an event and makes public reads
return 404; it cannot recall already cached or downloaded files.

Authenticated owner routes live at
`/api/v1/landings/projects/{project_id}/publication...`. The only unauthenticated
routes are bounded `GET`/`HEAD` snapshot and selected-asset reads below
`/api/v1/public/landings/{namespace}/{slug}`. Snapshot JSON allowlists the
Project display name, canonical URL, normalized approved configuration/content,
two selected asset URLs, version digest, and publication time. IDs, history,
provenance, Analytics data, and unselected assets remain private. JSON is
`no-store`; digest-addressed current PNGs are immutable-cacheable.

Save and Approve create only a Landing checkpoint when state changed; Approve
also writes the immutable version. They do not call a learner or create rules.
Performance learning starts only from Analytics and may propose inactive
Project rules or global spirit principles for explicit owner review.

## Page design and editing

One shared browser renderer powers inline Edit, Preview, and native fullscreen
views. The page has bundled, licensed browser fonts (including Ukrainian and
italic variants), a compact navigation/hero, benefit cards, optional evidence,
bounded supporting artwork, an actionable contact panel, and collapsed FAQs.
Breakpoints follow the page container rather than the Owner Console viewport.
Desktop/tablet/mobile previews use 1280/768/360 CSS pixels with proportional fit.
Mobile opens at 360px and switches between editor and preview surfaces.

The section navigator and clickable preview select a focused inspector. Existing
bounded theme and layout controls are exposed alongside a `presentation` block:
`language` (uk/en), `cta_target` (contacts/url/email/phone, where `url` is the
backward-compatible stored key for a direct Telegram bot link), `heading_scale`
(0.85–1.15), `spacing` (compact/comfortable/airy), and `hero_focus` /
`visual_break_focus` (x/y, 0–100). Its display defaults are Ukrainian, the contacts
section, scale 1, comfortable spacing, and centered crops. The block is optional
in stored v1 configuration; reading a document never inserts it. No migration is
required. New AI composition includes it and derives language from the Brief.

Page labels have their own language; console language changes do not translate
saved copy. Contacts use validated direct `https://t.me/<bot_username>`,
Instagram profile, mailto, and tel links. Telegram usernames must end in `bot`;
Instagram accepts only one direct HTTPS profile path and renders the profile
handle with the Instagram icon. Both social links open separately. The optional
Instagram field is absent from older v1 content until the owner supplies it, so
reading an existing Landing does not rewrite its state digest. Empty proof and
editor placeholders never reach Preview.
Long copy wraps within the page; section text fields expose backend limits.

Save feedback shows the immutable checkpoint result without a learning dialog,
proposal, or retry. Image selection persists pending edits before changing the
selected raw image. Failed mutations retain editable local input.
Font files are bundled from canonical assets and their OFL notices ship in
`dist/font-licenses`; the dev server permits only those additional asset paths.

The editable Landing also exposes the shared Post Studio **Agent mode**. A turn
may adjust only the complete bounded configuration/content supplied from the
current unsaved editor and may request existing generation for `hero_visual`
and/or `visual_break_visual`. Each image action must repeat that slot's returned
visual direction; enhancement requires an existing selected image. The browser
persists the returned draft through the normal configuration route before calling
the existing generation route. Contact endpoints and the full social-proof block
are preserved exactly, while their ordinary supporting layout/copy controls stay
editable. Up to four normalized screenshots are temporary inputs only. The agent
cannot save, approve, publish, add sections, invent evidence, or modify code.

Browser coverage includes desktop, 360px, iPhone WebKit, real font loading,
maximum-length copy, focal points, section selection, contact actions, FAQ,
page-language independence, and fullscreen focus restoration. Backend tests
cover approval without proof, invalid contacts, failed-approval atomicity,
bounded configuration, immutable versions, zero Save/Approve learner calls, and
cookieless event semantics.

## Natal identity, themes, and visual styles

Every app uses the fixed Natal identity. The shared renderer bundles the canonical
`natal/assets/logo-natal.png` lock-up unchanged, including its app name, and the web
build checks its SHA-256. The logo sits directly on the page background without
a white badge. Neither Brief composition nor page themes can rename
Natal, replace its logo, or request an owner brand kit.
Post Studio's Project-default symbol/name colors are intentionally separate and
do not recolor Landing drafts, versions, or publications.

The Page design inspector offers three coordinated presets: Studio (crisp blue),
Editorial (warm paper and serif headings), and Soft bloom (sage and rounded surfaces).
A preset applies palette, fonts, radius, button/card/icon treatments, contact panel,
and FAQ styling while preserving copy, crop settings, and generated images.
The backend catalog owns the presets in `validation_pipeline/landing_design.py`.

The optional `components` block exposes Filled/Outlined/Elevated/Text buttons,
Square/Rounded/Pill button shapes, independent button/text colors,
Filled/Outlined/Elevated/Minimal cards, Soft/Solid/Line/Hidden icons, and
Contrast/Surface/Accent contact panels. Feature and evidence cards share the card
style. These bounded controls are available in the relevant section inspectors;
all changes use the existing configuration, checkpoint, and immutable-version paths.

Each `image_directions` slot stores one of the same ten visual styles used by Post
Studio plus a Scene or Isolated key element background. The picker reuses Post's
component and localized descriptions. The service expands server-owned directives
into automatic-generation, manual-generation, and exact-enhancement prompts.
Current Landing palette and selected art direction take precedence over conflicting
frozen Post style; the Post snapshot remains provenance. Hero and supporting images
retain independent choices and crop-aware subject directions. A style change leaves
existing pixels/history intact until Generate or Enhance is requested. Pending edits
are persisted first, and the prompt uses that persisted configuration's digest.
Both slots use the [shared versioned image policy](post-studio.md#shared-image-generation-policy),
including instruction origins, pinned current Brief/settings, reference precedence
and immediate display of technically valid output. The Hero in phone mode is a
backdrop behind the phone overlay, not an app-screen aperture; image-only mode
uses standalone artwork, and the visual-break slot carries its responsive crop
and focus settings. Original Manual Agent messages remain distinct from their
interpretations. Generated directions never acquire owner priority merely by
being saved. Source Post metric hypotheses remain unvalidated copy, never facts
or social proof for Landing composition.
Those image controls introduce no new provider mode. Publication is a separate read authority
over approved versions and never influences Landing or Post generation.

## App feature phone

The local Hero and App feature inspectors offer **Visual mode: Phone frame &
buttons / Image only**. Optional `configuration.visual_mode` accepts `phone` or
`image`, defaulting to the existing phone view when omitted. Image mode removes
the phone and all of its UI, showing the selected hero artwork at full opacity
with the existing placement and crop controls. Screen settings and content are
preserved and return when toggled back. Save, approval, and the shared
inline/fullscreen/public renderer retain the mode. No deployment or publication
is part of this local milestone.

Every service is presented as a Natal app by default. The hero uses Post Studio's bundled,
digest-checked iPhone 15 Pro front frame, with a responsive HTML screen behind its
original aperture. Generated hero art is atmospheric context behind the phone;
surrounding text, controls, identity and hardware are renderer-owned. Requested
text/UI/devices inside artwork are allowed by the shared generation policy.
The separate App feature inspector selects Light, Dark, or Glass screen themes
and Overview, Booking, or Checklist layouts independently of page/art themes.

`configuration.phone_mockup` stores bounded theme/layout enums. `content.app_feature`
stores the screen title (72 characters), description (160), action label (36), and
three label/detail rows (60/80). The owner can change the demonstrated task and
all screen copy. New composition selects a Brief-grounded task even for physical
services, such as energy consumption or booking a visit. Unestablished values,
availability, and capabilities must not be invented. Optional details may be empty;
supplied screens need all required labels before approval. Validation happens before
approval writes, and screen edits use existing saves, learning, and immutable versions.

Existing documents can omit these blocks: the renderer resolves a light overview
from saved feature copy without rewriting storage. New composition requires an
explicit app feature screen. Page language governs renderer labels; saved screen
copy is never translated by switching console language. Preview rows toggle local
selection (multiple for checklists), and the screen action follows the same validated
CTA destination as the page. The visible interface-preview caption distinguishes
this demonstration from a live booking or account. Long copy scrolls inside the
phone while its action remains visible. Inline/fullscreen use the same component.

## Global template authoring

[Templates mode](templates-mode.md) registers this existing Landing definition
as its protected first gallery item. Its authoritative gallery preview uses the
same `LandingPage` renderer with neutral fixtures and no contacts or social proof.
New declarative Landing templates can be authored independently or alongside a
separately versioned Post definition. Their optional exact Post-template reference
contains no Project content or approved-version data. Existing Landing pages,
approvals, assets, publication and analytics retain their current behavior.
