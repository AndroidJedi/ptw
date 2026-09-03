# Universal Studio

Universal Studio is an owner-only, standalone workspace. It does not depend on
Product Brief approval and does not create posts, content runs, review sets, or
publication records. The local-only Post flow has a separate per-post Studio
workspace and never mutates the standalone workspace.

## Bounded templates

Studio has exactly two server-owned selections: `universal_ad` at 1080×1080
and `phone_metrics` at 1080×1350. Selecting either replaces every mutable
configuration, content field, and mutable workspace asset; it never changes an
immutable version. A workspace without a selection remains the legacy
`universal_ad` workspace.

`universal_ad` retains its fixed semantic structure: background, optional
sticker, hero title, supporting text, optional benefits, CTA, and Natal.
`phone_metrics` v17 is a fixed 4:5 composition: off-white mineral texture,
canonical Natal lock-up in the upper-left, dark left-safe-area copy, a
front-facing black phone at upper-right, three compact equal metric buttons,
and a full-width cobalt CTA band. Each metric button independently exposes its
value, label, Filled or Outlined style, text colour, background/border colour,
and Square, Rounded, or Pill shape. The reference default remains the approved
cobalt fill, white text, and smooth rounded corners. The app screen now ends in
three independently tunable action buttons. Each exposes text, Filled,
Elevated, Outlined, or Text-only style, text colour, background/border colour,
and Square, Rounded, or Pill shape. Their fixed reference defaults are a blue
filled primary “Створити новий акаунт”, elevated white “Увійти”, and blue
text-only “Можливо пізніше”. They remain separate from the outer post CTA. The
template accepts an optional
eyebrow, headline, supporting text, CTA, exactly three owner statistics, and an
optional renderer-owned in-phone title. Disabling the eyebrow removes its
primitive and semantic binding and reflows the headline upward while retaining
the saved eyebrow copy. Supporting copy accepts only two bounded inline marks:
`**bold words**` and `==accent-colour words==`. The editor wraps the current
selection with either mark and exposes a 20–38px font-size range plus one
accent-colour picker. These values belong to the saved configuration and the
authoritative PNG renderer; delimiter characters are not painted. Unknown
fields, an absent statistic, or a fourth statistic fail closed. Three saved,
bounded texture selectors provide `Off` plus three finishes per surface: Grain,
Concrete, and Travertine for the full post background; the same three choices
for a separately clipped rounded surface behind only the upper-left Natal and
left copy; and Fine grain, Soft paper, and Frosted glass for the in-phone hero.
`Off` removes the corresponding renderer layer rather than substituting an
empty or transparent effect. Mutable v1 through v6 phone configuration upgrades
to the previously implicit eyebrow, font-size, accent-colour, Concrete full
background, no left-copy texture, Fine-grain screen, and reference metric-button
defaults and the three reference in-phone buttons; mutable v1 content gains the
three reference labels. Immutable versions are not rewritten.

The internal primitive tree is built server-side. API callers cannot import
templates or mutate arbitrary nodes. The shared `StudioRenderer` produces the
authoritative PNG and resolved-node diagnostics. Primitive catalog v2 adds the
generic `rich_text` primitive with bold-weight and highlight-colour properties;
existing plain `text` nodes and their normalized documents remain unchanged.

## Natal and assets

Natal is the sole visible identity in all new Studio and local Post drafts. Its
canonical lock-up is always enabled. Owner logo uploads, logo toggles, and
brand-name substitution are absent from the control catalog; retained legacy
configuration fields exist only so historical immutable versions remain
readable.

The active `phone_metrics` frame is the previously sourced WithFrame iPhone 15
Pro black front mockup. Its adjacent manifest records source, license,
download date, and SHA-256. Runtime code reads only this local digest-checked
asset and never fetches a device frame. The generated hero art is placed inside
a deterministic Natal app shell with crisp time, cellular, complete multi-arc
Wi-Fi, and battery status details, canonical lock-up, optional owner title,
three owner-tunable app actions, and home indicator. The complete upright
screen is composited into the transparent rounded aperture before the hardware
is added. Device, UI, copy, and artwork therefore remain one image layer and
cannot drift apart, while readable screen elements receive no perspective
distortion. Hero artwork spans the complete app-screen width. Its sharp subject
is lowered slightly farther away from the fixed status and Natal header, while an image-derived
continuation still reaches the screen's top edge and feathers into the sharp
layer at the same source row. The artwork and its selected finish dissolve
together through a long eased fade into the lower white content area; no inset
card mask, white side gutters, blank top
band, duplicated hard edge, or horizontal seam beneath the logo remain. The
selected deterministic screen finish is composited beneath the fixed interface
without softening renderer-owned UI. The screen matte extends beneath the upper bezel so the
outer creative background cannot show through the antialiased aperture curves.

`universal_ad` retains bounded background and Pexels-screened sticker assets.
`phone_metrics` has no owner-uploadable screen artwork. Standalone Studio keeps
the deterministic text-free sculptural fixture as its zero-cost fallback and
accepts one bounded owner visual direction to generate and immediately apply a
replacement hero artwork. The default local provider invokes the built-in image
generation tool through the same ChatGPT-authenticated Codex CLI already used
for structured generation; PTW never reads or copies Codex authentication.
`STUDIO_PHONE_IMAGE_PROVIDER=openai_api` remains an explicit fallback for a
server-side `OPENAI_API_KEY`, rather than a prerequisite for local Studio.
When a mutable raw hero already exists, “Enhance current image” is enabled and
checked by default. It passes that raw source image with the direction as an
edit, never the composited phone, fixed Natal identity, title, actions, or
hardware. Turning the checkbox off preserves the existing generate-from-scratch
behavior. With no current raw image the control is disabled until the first
successful generation, then becomes the default for the next iteration. The
Codex provider exposes a temporary read-only reference path only to its bounded
image worker; the direct API provider sends a multipart request to the GPT Image
edits endpoint. Persisted non-secret provenance distinguishes `generate_new`
from `enhance_current` and links enhancements to the exact previous asset
SHA-256. Temporary reference images are removed after the provider call.
The local-only action saves any current copy/configuration first, preserves the
previous visual on provider failure, validates the result as PNG, and records
the non-secret direction and provider provenance. The local Post flow separately
obtains one square Brief-derived hero artwork server-side through the same
provider boundary. Both prompt contracts prohibit visible text,
numbers, logos, UI, buttons, charts, metrics, and devices in generated pixels;
all readable screen content is rendered deterministically afterward. The
browser never receives provider authentication. Production Studio does not expose
the local generation route.

A saved version stores exact configuration, content, asset digests, template
digest, and PNG bytes below `.local/studio-workspace`; authenticated render
responses are private/no-store.

## Pexels sticker boundary

The canonical Natal logo/font are deterministic defaults. A Sticker may be
isolated only from an approved photographic object while retaining source and
transformation provenance. Query and provider metadata do not approve the
visual: isolation rejects retained scenes and edge-cropped subjects before the
asset can enter the Sticker slot. When Pexels is configured and the Sticker slot
is empty, the component action sources the bounded starter query and enables the
component in one owner action; it remains disabled only when Pexels is
unavailable. Studio never sends provider credentials to the browser.

## Visual gate and local Tune

`skills/studio-ui-visual-audit/scripts/audit_universal_studio.py` renders both
the representative universal variants and the exact 1080×1350 phone template
in six representative states, including every texture finish, all three `Off`
states, a left-copy-only isolation render, and one mixed metric-button render
covering both styles and all three shapes.
The phone checks read full-resolution pixels and resolved bounds for the
off-white texture, upper-left Natal, dark left copy, upper-right front-facing
device, equal tunable metric buttons, CTA band, no clipping/overlap/unsafe bounds,
the crisp upright app shell, complete status-bar network signal, three
horizontal in-phone actions, and the text-free hero-art fixture. Pixel checks cover both
hero-art side edges, the former
below-logo boundary, and both upper aperture curves to prevent white gutters or
a horizontal or outer-background seam. They also verify compact equal button
geometry, the reference rounded corners, all nine optional texture finishes, the
rounded bounds of the left-copy surface, real texture-layer removal in all
three `Off` states, complete eyebrow-node removal, and headline reflow.
Supporting-copy checks exercise both markup modes, the
default and maximum font size, two accent colours, resolved layout diagnostics,
and actual accent pixels in the PNG. Metric-button checks verify independent
copy, filled/outlined rendering, text and surface colours, shape pixels, equal
geometry, and unclipped labels. In-phone action checks cover the reference
filled/elevated/text-only stack plus the Outlined style, all three shapes,
independent labels and colours, elevation shadow, and horizontal final-frame
resampling. A passed
audit is followed by a full-resolution visual inspection of the creative area
only; social-app chrome and reference brand wording are not part of the Studio
output. Browser checks also cover the enhancement checkbox at desktop and 360px:
disabled without a raw current hero, checked by default with one, keyboard
operable, and mapped to the bounded boolean API field.

`STUDIO_TUNE_MODE=1` enables the loopback Tune wizard. It captures one requested
Studio implementation, runs Codex in an isolated worktree, enforces a
Studio-only allowlist, verifies focused tests/build checks, and presents a
preview before copy-back. Only explicit owner approval may persist a generalized
rule in `skills/studio-tune-local/references/owner-approved-rules.md`.
Production Owner Gateway does not expose Tune routes.
