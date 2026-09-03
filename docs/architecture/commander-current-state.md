# Commander current state

Updated: 2026-09-03
Branch: `codex/web-only-commander`
Deployment: not authorized; local checkout only

## Current milestone

Universal Studio now has two bounded server-owned templates: existing
`universal_ad` at 1080×1080 and `phone_metrics` v11 at 1080×1350. Applying either
template replaces all mutable configuration, owner copy, and mutable assets;
immutable versions remain byte-for-byte historical records. Missing selection
metadata retains the legacy Universal Studio behavior.

`phone_metrics` is the owner-approved 4:5 Natal composition: off-white texture,
canonical Natal lock-up upper-left, dark left-safe copy, a licensed black
front-facing iPhone, three compact equal cobalt statistic cards with smoother
corners, and a cobalt bottom CTA band. Its sole static frame is checked in with
a source/license/SHA-256 manifest and is never fetched at runtime; the angled
frame was removed.

The phone screen is a real fixed app composition rather than generated
wallpaper clipped behind a device aperture. One server-generated square hero
artwork is placed in a deterministic screen with status details, the canonical
Natal lock-up, optional owner title, owner CTA, and home indicator; the complete
upright screen is fitted into the fixed front aperture before its hardware is
composited. Device, UI, copy, and artwork remain one downstream layer and cannot
drift apart, while the screen text and CTA stay crisp and horizontal. Standalone
Studio now exposes a bounded visual-direction field and local-only “Generate &
apply” action; it saves current draft copy/configuration first and replaces only
the mutable in-phone artwork. Generation defaults to the built-in image tool of
the existing ChatGPT-authenticated Codex CLI and therefore needs no separately
configured Platform API key; PTW never reads or copies Codex authentication. An
explicit direct Images API mode remains available for separately keyed runtimes.
The prior polished sculptural fixture remains the zero-cost fallback, and a
failed generation preserves the current visual. The local Post flow continues
to derive its direction from the approved Brief.
Hero artwork spans the full screen width without inset white gutters, continues
behind the fixed status/logo header without a hard horizontal edge, and fades
vertically into the lower content area. A deterministic material grain textures
the hero while remaining beneath the crisp renderer-owned UI. Generated pixels
remain text-, logo-, UI-, number-, chart-, and device-free; the browser never
receives provider authentication, and non-secret direction/provider provenance
is retained with the asset.

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
`Off` state removes its renderer-owned texture layer. Mutable v1 through v4
configuration upgrades to Concrete, no left-copy texture, and Fine grain so
existing mutable previews retain their previous appearance.

The screen matte deliberately overbleeds beneath the upper bezel. Pixel-level
coverage of both antialiased aperture curves prevents the off-white outer
canvas from appearing as wedges inside the phone's top corners.

Natal is the only visible identity in new Studio and local Post drafts. The
canonical lock-up is always enabled. Owner logo upload/toggle/brand substitution
is absent from the new template controls; immutable legacy versions remain
readable.

The local Post start screen exposes both template choices before the draft is
created and locks the choice afterward. Phone drafts collect bounded copy,
exactly three owner metrics, and all three texture choices, then generate a
server-side OpenAI text-free hero
visual under an explicit no-text/no-logo/no-UI contract. They have no
after-start Tune action. Universal drafts retain the existing bounded Pexels
and comment-tuning flow. No production Owner Gateway, Brief handoff, Telegram,
database, Firebase, or deployment behavior changed.

Mutable local Post v1 drafts created before template selection and the fixed
Natal lock-up are recovered once, append-only, when their Studio state digest
is stale: they become an explicit `universal_ad` v2 draft with the current
Studio preview digest. Any v2 draft, phone draft, or immutable approval still
fails closed on a digest mismatch.

## Verification status

- Validation pipeline: 90 tests passed in the repository virtual environment.
- Focused Post/Studio/phone regressions: 51 tests passed, including authenticated
  Codex built-in image generation, generated-path confinement and cleanup, static
  frame digest/no-runtime-fetch, front-facing app-shell composition,
  renderer-owned phone copy/CTA, Natal-only identity, template replacement,
  legacy-version preservation and recovery, three-metric validation, compact
  smooth cards, textured phone art, real eyebrow removal/reflow, v1 phone
  configuration migration, supporting-copy markup/size/colour rendering, all
  texture selections and both real `Off` states, 1080×1350 rendering, bounded
  owner-directed phone-screen generation, authenticated local routing, saved
  provider/direction provenance, and preservation of the deterministic fallback.
- Extended Studio visual audit passed six universal variants plus five exact
  full-resolution `phone_metrics` 1080×1350 texture states. It checks every
  texture option, all three actual `Off` states, and a left-copy-only isolation
  render,
  Natal placement, left-safe copy, upper-right front-facing phone, metric
  cards, CTA, bounds/collisions, the crisp upright Natal app shell, horizontal
  in-phone CTA, full-width and continuous header hero artwork, sealed upper
  screen corners, text-free phone hero artwork, compact smooth metric cards,
  eyebrow removal with headline reflow, supporting-copy bold and colour markup,
  and default/maximum supporting font size. The creative render was
  visually inspected without social-app chrome. The live Studio editor was
  inspected at 1440 and 360 CSS pixels with reduced motion, keyboard controls,
  texture selection, the new generation field and unavailable-provider state,
  refreshed preview pixels, and no horizontal overflow.
- Owner Console: 40 Vitest tests and the production TypeScript/Vite build
  passed.
- Commander: host suite passed 6 tests with 2 FastAPI-dependent skips; the
  built runtime image passed all 8 tests. The deterministic Commander demo
  completed.
- Canonical skill synchronization and skill verification passed.

No production state was touched.

## Next work

Keep both Studio templates and the Post milestone local until the owner
explicitly requests production integration. That future work must define
PostgreSQL entity/edge and PNG authority, add authenticated Owner
Gateway/internal routes, verify restart/idempotency, and preserve the rule that
only explicit approval creates an asset. Do not reuse the retired Result
schema, routes, or local data.
