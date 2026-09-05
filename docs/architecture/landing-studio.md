# Project-scoped Landing Studio

Landing / Лендінг is the third private Owner Console destination. A Landing is
not a public site, publishing workflow, campaign, analytics surface, or lead
collector. It belongs to one Project and starts from one immutable approved
Post version plus its source approved Product Brief.

## Bounded page contract

The sole v4 page template keeps this semantic order: Hero, three feature cards,
social proof, a generated visual break, contacts, and three FAQs. The owner can
edit bounded content and theme/layout controls but cannot add HTML, CSS,
scripts, arbitrary sections, or reorder the composition. Hero and visual-break
art are independently generated text-free PNGs; each retains its newest three
digest-checked raw images and supports exact-image enhancement and selection.

Initial AI composition receives the approved Brief, the frozen Post version’s
design snapshot, the live Landing catalog, and Landing-only global/Project
skills. It must not invent social proof or contact endpoints. Evidence is optional:
zero entries hide the entire section, while supplied entries require a heading,
statement, and attribution. One validated email, phone, or HTTPS URL is required
before approval, together with both visuals, essential copy, all three features,
and all three FAQs. A direct CTA also requires its selected endpoint. Approval
validates pending content and its note before writing workspace files or a version.

## Authority and lifecycle

The first page for a Post version is idempotently reserved. A variant is
available only after the latest sibling has an immutable approved version. A
Landing captures its source Post snapshot at reservation; future Post edits
never synchronize into it.

PostgreSQL stores Landing metadata, workspace files, visual bytes, composition
and visual generation runs, immutable versions, checkpoints, and Landing-only
learning snapshots/proposals with explicit Project, Brief, and Post-version
graph lineage. Loopback provides the
same append-only metadata contract and per-page workspace files. All APIs are
authenticated and Project/page scoped under `/api/v1/landings`; visual bytes are
private and `no-store`. Bare or public Landing endpoints do not exist.

Save and Approve create a Landing-only checkpoint when state changed. Learning
may append Landing global and Project rules, but never alters Post Studio skills
or generation. The bridge retains its four existing JSON modes and existing
text-free media mode; Landing uses its own strict schemas and canonical skills.

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
`language` (uk/en), `cta_target` (contacts/url/email/phone), `heading_scale`
(0.85–1.15), `spacing` (compact/comfortable/airy), and `hero_focus` /
`visual_break_focus` (x/y, 0–100). Its display defaults are Ukrainian, the contacts
section, scale 1, comfortable spacing, and centered crops. The block is optional
in stored v1 configuration; reading a document never inserts it. No migration is
required. New AI composition includes it and derives language from the Brief.

Page labels have their own language; console language changes do not translate
saved copy. Contacts use validated HTTPS, mailto, and tel links. External HTTPS
links open separately. Empty proof and editor placeholders never reach Preview.
Long copy wraps within the page; section text fields expose backend limits.

Save feedback shows an immutable checkpoint's edit summary, Project lesson, and
global proposal. Decision/retry uses existing scoped routes; a proposal must
belong to the requested page. Image selection persists pending edits before
changing the selected raw image. Failed mutations retain editable local input.
Font files are bundled from canonical assets and their OFL notices ship in
`dist/font-licenses`; the dev server permits only those additional asset paths.

Browser coverage includes desktop, 360px, iPhone WebKit, real font loading,
maximum-length copy, focal points, section selection, contact actions, FAQ,
page-language independence, and fullscreen focus restoration. Backend tests
cover approval without proof, invalid contacts, failed-approval atomicity,
bounded configuration, immutable versions, and page-scoped learning decisions.

## Natal identity, themes, and visual styles

Every app uses the fixed Natal identity. The shared renderer bundles the canonical
`natal/assets/logo-natal.png` lock-up unchanged, including its app name, and the web
build checks its SHA-256. The logo sits directly on the page background without
a white badge. Neither Brief composition nor page themes can rename
Natal, replace its logo, or request an owner brand kit.

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
No new provider mode, public endpoint, storage authority, or migration is introduced.

## App feature phone

Every service is presented as a Natal app. The hero uses Post Studio's bundled,
digest-checked iPhone 15 Pro front frame, with a responsive HTML screen behind its
original aperture. Generated hero art is atmospheric context behind the phone;
text, controls, identity, and hardware are never generated into those pixels.
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
