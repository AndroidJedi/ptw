# Commander current state

Updated: 2026-09-04
Branch: `codex/web-only-commander`
Deployment: owner-authorized production release in verification

## Current milestone

Universal Studio now has two bounded server-owned templates: existing
`universal_ad` at 1080×1080 and `phone_metrics` v17 at 1080×1350. Applying either
template replaces all mutable configuration, owner copy, and mutable assets;
immutable versions remain byte-for-byte historical records. Missing selection
metadata retains the legacy Universal Studio behavior.

`phone_metrics` is the owner-approved 4:5 Natal composition: off-white texture,
canonical Natal lock-up upper-left, dark left-safe copy, a licensed black
front-facing iPhone, three compact equal statistic buttons, and a cobalt bottom
CTA band. Each statistic button now has independent saved value/label copy,
Filled or Outlined style, text colour, background/border colour, and Square,
Rounded, or Pill shape. The owner-approved default remains exactly the prior
cobalt fill, white text, and smooth rounded corners. Its sole static frame is
checked in with a source/license/SHA-256 manifest and is never fetched at
runtime; the angled frame was removed.

The phone screen is a real fixed app composition rather than generated
wallpaper clipped behind a device aperture. One server-generated square hero
artwork is placed in a deterministic screen with crisp time, four ascending
cellular bars, a complete three-arc Wi-Fi glyph and dot, battery status, the
canonical Natal lock-up, optional owner title, three app actions, and home indicator;
the complete
upright screen is fitted into the fixed front aperture before its hardware is
composited. Device, UI, copy, and artwork remain one downstream layer and cannot
drift apart, while the screen text and CTA stay crisp and horizontal. Standalone
Studio now exposes a bounded visual-direction field and “Generate &
apply” action; it saves current draft copy/configuration first and replaces only
the mutable in-phone artwork. An “Enhance current image” checkbox is enabled and
checked by default whenever a generated raw hero exists. Enhance supplies that
exact raw artwork—not the phone screenshot or renderer-owned UI—as the provider
image input and applies the new direction as an edit; turning it off generates
from scratch. A first generation with no current asset keeps Enhance disabled,
then enables it for the next iteration. Generation defaults to the built-in image tool of
the existing ChatGPT-authenticated Codex CLI and therefore needs no separately
configured Platform API key; PTW never reads or copies Codex authentication. An
explicit direct Images API mode remains available for separately keyed runtimes.
The Codex path confines the temporary reference PNG to its read-only worker
directory; the direct API path uses the GPT Image edits endpoint. Saved
provenance records generate-versus-enhance mode and, for enhancement, the exact
reference asset SHA-256. Neither path persists a temporary reference copy.
Studio retains the three newest distinct raw iPhone hero images in a digest-
verified local history. A compact authenticated thumbnail selector marks the
active image and lets the owner restore any retained hero without regenerating
it; that selection becomes both the authoritative rendered hero and the next
Enhance reference. Selecting an image saves pending copy/configuration first,
does not reorder recency, and keeps all three entries. A fourth successful
generation evicts only the oldest retained raw hero and its file. Legacy
workspaces expose their current raw hero as the first history item immediately;
previously overwritten images cannot be reconstructed.
The prior polished sculptural fixture remains the zero-cost fallback, and a
failed generation preserves the current visual. The local Post flow continues
to derive its direction from the approved Brief.
Hero artwork spans the full screen width without inset white gutters. Its sharp
subject is lowered slightly farther beneath the fixed status/logo header, while a feathered,
image-derived continuation still reaches the top edge without a blank band or
hard seam. The artwork and its selected texture now dissolve together through
a longer eased transition into the lower white content area, without a straight
cutoff above the headline. A deterministic material grain textures the hero while remaining beneath the crisp
renderer-owned UI. Generated pixels remain text-, logo-, UI-, number-, chart-,
and device-free; the browser never
receives provider authentication, and non-secret direction/provider provenance
is retained with the asset.

The bottom of the app screen now matches the owner reference with three actions:
a blue filled “Створити новий акаунт”, elevated white “Увійти”, and blue
text-only “Можливо пізніше”. Each independently saves and previews its text,
Filled/Elevated/Outlined/Text-only style, text colour, background/border colour,
and Square/Rounded/Pill shape. These actions remain separate from the outer
post CTA. Mutable v1–v6 phone configuration and v1 content upgrade in memory to
the reference buttons without rewriting immutable versions.

The phone Studio now exposes a saved eyebrow visibility toggle. Turning it off
removes the `offer` primitive, semantic role, and binding rather than rendering
empty text, retains the owner copy for a later re-enable, and reflows the
headline into the released space. Supporting copy now has selection-based bold
and accent-colour markup, a bounded 20–38px size control, and an accent-colour
picker. All three are saved and rendered into the authoritative PNG through the
generic `rich_text` primitive; markup delimiters are not painted. Existing
mutable v1/v2 configuration upgrades to the prior visible-eyebrow, 29px, and
blue-accent defaults; immutable versions are not rewritten.

It also exposes three saved texture selectors. The full post background offers
`Off`, Grain, Concrete, and Travertine; a separate rounded surface bounded to
the upper-left Natal and copy area offers the same choices; and the in-phone
hero independently offers `Off`, Fine grain, Soft paper, and Frosted glass.
The effects are deterministic and stay below copy and fixed phone UI. Each
`Off` state removes its renderer-owned texture layer. Mutable v1 through v5
configuration upgrades to Concrete, no left-copy texture, Fine grain, and the
reference metric-button treatment so existing mutable previews retain their
previous appearance.

The screen matte deliberately overbleeds beneath the upper bezel. Pixel-level
coverage of both antialiased aperture curves prevents the off-white outer
canvas from appearing as wedges inside the phone's top corners.

Natal is the only visible identity in new Studio and local Post drafts. The
canonical lock-up is always enabled. Owner logo upload/toggle/brand substitution
is absent from the new template controls; immutable legacy versions remain
readable.

Production integration now exposes the complete bounded Studio route set through
Firebase-authenticated Owner Gateway. Production phone generation uses the
existing server-side Result media bridge; Enhance supplies one digest-checked PNG
attachment to the same bounded non-human graphic mode. PostgreSQL is the complete
production Studio authority: it owns the singleton workspace snapshot and PNG
bytes, immutable asset/version UUID entities, and explicit `contains`,
`derived_from`, and `supersedes` edges. Validation restores its disposable
renderer cache from PostgreSQL after replacement. The release gate performs real
provider generate/edit canaries before reset and compares exact Studio workspace
and state IDs across a forced Validation API replacement after reset.

The local Post start screen exposes both template choices before the draft is
created and locks the choice afterward. Phone drafts collect bounded copy,
exactly three owner metrics, and all three texture choices, then generate a
server-side OpenAI text-free hero
visual under an explicit no-text/no-logo/no-UI contract. They have no
after-start Tune action. Universal drafts retain the existing bounded Pexels
and comment-tuning flow. It remains absent from production Owner Gateway and
does not alter Brief handoff or Telegram behavior.

Mutable local Post v1 drafts created before template selection and the fixed
Natal lock-up are recovered once, append-only, when their Studio state digest
is stale: they become an explicit `universal_ad` v2 draft with the current
Studio preview digest. Any v2 draft, phone draft, or immutable approval still
fails closed on a digest mismatch.

## Verification status

- Validation pipeline: 100 tests passed in the repository virtual environment;
  the four Owner Gateway tests also passed.
- Focused Post/Studio/phone regressions: 58 tests passed, including authenticated
  Codex built-in image generation, generated-path confinement and cleanup, static
  frame digest/no-runtime-fetch, front-facing app-shell composition,
  renderer-owned phone copy/actions/CTA, Natal-only identity, template replacement,
  legacy-version preservation and recovery, three-metric validation, compact
  tunable buttons, textured phone art, real eyebrow removal/reflow, v1–v5 phone
  configuration migration, supporting-copy markup/size/colour rendering, all
  texture selections and both real `Off` states, 1080×1350 rendering, bounded
  owner-directed phone-screen generation, authenticated local routing, saved
  provider/direction provenance, current-image enhancement through both Codex
  and direct API provider boundaries, reference digest lineage, and preservation
  of the deterministic fallback. History coverage verifies the exact three-item
  retention cap, oldest-file eviction, digest-checked authenticated reads,
  selection without recency reordering, selected-image rendering, and use of
  the selected raw bytes for the next enhancement.
- Extended Studio visual audit passed six universal variants plus six exact
  full-resolution `phone_metrics` 1080×1350 states. It checks every
  texture option, all three actual `Off` states, a left-copy-only isolation
  render, and one mixed button render covering both styles and all three shapes,
  Natal placement, left-safe copy, upper-right front-facing phone, metric
  cards, CTA, bounds/collisions, the crisp upright Natal app shell, complete
  status-bar network signal, three horizontal tunable in-phone actions, lowered
  hero-subject
  placement, full-width artwork with an
  image-derived continuation to the top, seamless header blending, sealed upper
  screen corners, an eased image-and-texture transition into the white content
  area, text-free phone hero artwork, compact smooth metric cards,
  eyebrow removal with headline reflow, supporting-copy bold and colour markup,
  default/maximum supporting font size, and independent metric-button text,
  foreground/background colours, and shape. The in-phone controls were checked
  across Filled, Elevated, Outlined, and Text-only styles, all three shapes,
  independent labels/colours, and the reference elevation shadow. The creative render was
  visually inspected without social-app chrome. The live Studio editor was
  inspected at 1440 and 360 CSS pixels with reduced motion, keyboard controls,
  all per-button fields, the original default and a mixed styled preview, the
  real one-thumbnail legacy state and an exact three-thumbnail selection state,
  refreshed authoritative preview pixels, and no horizontal overflow.
- Owner Console: 44 Vitest tests and the production TypeScript/Vite build
  passed.
- Production-integration gates: the single baseline schema applied twice against
  disposable PostgreSQL; one real workspace, generated-asset entity, approved-
  version entity, and three graph edges survived cache reconstruction with the
  same UUIDs and render digest. The independent Result bridge passed 30 tests,
  including exact reference attachment, prompt base64 exclusion, attachment-use
  proof, provenance, and temporary-file cleanup.
- Commander: host suite passed 6 tests with 2 FastAPI-dependent skips; the
  built runtime image passed all 8 tests. The deterministic Commander demo
  completed.
- Canonical skill synchronization and skill verification passed.

The release is targeted as `studio-phone-v17-20260904-0513`; production results
are recorded only after all serial deployment and live verification gates pass.

## Next work

Complete the owner-authorized serial production release and record its exact
application/platform revisions and live verification. Keep the simple Post flow
local-only. Studio approval remains the only operation that creates an immutable
Studio version; generated phone heroes are immutable source assets but never
implicitly approved versions.
