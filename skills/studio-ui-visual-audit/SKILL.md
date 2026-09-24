---
name: studio-ui-visual-audit
description: Audit Post Studio renders and editor presentation for clipping, overlap, incorrect text alignment, overflow, unsafe bounds, or responsive preview regressions. Use for visual QA of Studio renderer, layout, typography, component, or CSS changes; do not use for deployment or non-Studio Owner Console incidents.
---

# Studio UI Visual Audit

Use exact rendered evidence to distinguish a creative-renderer defect from a
browser presentation defect. Pair this review with `studio-tune-local` when the
owner also asks for implementation. Keep the work local unless the owner names
a specific remote target.

## Evidence and diagnosis

- Reproduce the reported configuration, content, assets, viewport, and language.
- Treat `phone_metrics` as the protected built-in Post template. Global Templates
  authoring may register separate declarative definitions; audit them through
  the same primitive renderer at native Post and desktop/mobile Landing sizes.
- Inspect the authenticated raw template-native PNG at full 1080×1350 resolution. If the defect
  is present there or in its resolved node manifest, fix the renderer/template;
  if it appears only in the scaled preview, fix the Studio UI/CSS.
- For text, compare visible alpha bounds with the assigned box. Treat an ink
  edge touching a clipped box, `text_layout.overflow`, truncation, or an absent
  required block as a failure—not as an acceptable visual approximation.
- Compare adjacent semantic blocks by visible bounds, not only configured
  coordinates. Preserve ordering and a positive visual gap for title,
  supporting text, bullets, and CTA.
- Check relevant optional-element states and bounded typography/layout extremes.
- Inspect hero and gradient as one composition. Match supporting hues and light
  temperature to the actual image, keep the silhouette distinct and verify copy
  contrast across the gradient. Recheck each replacement with its real cutout;
  a stock blue background is not a universal palette. Preserve owner colors.
  For editor changes, also inspect desktop, 360 CSS pixels, keyboard behavior,
  and reduced-motion behavior.

## Regression gate

Run the deterministic Studio geometry and colour audit from the repository root:

```sh
.venv/bin/python skills/studio-ui-visual-audit/scripts/audit_post_studio.py
```

Add focused regression coverage for the actual failed invariant. Prefer
resolved visible geometry or pixel-level assertions over snapshot hashes alone;
a changed hash proves difference, not correctness. For the Phone & metrics
template, preserve the off-white texture, upper-left Natal lock-up, left copy
safe area, fused front-facing device, equal metric-button row with the cobalt
filled/white-text/rounded reference default, full cobalt CTA band when CTA copy is nonempty (empty copy must remove the
entire band without changing the upper canvas), a crisp
upright Natal app shell, and the versioned owner-directed hero-art contract. When
the post CTA changes, verify its saved visible and hidden states, label retention,
bounded font sizing, configured background/text colours, and absence from both
the resolved nodes and semantic roles when disabled. When
metric-button controls change, verify Filled and Outlined styles, text and
background/border colours, and Square, Rounded, and Pill shapes in actual pixels
while all three labels remain unclipped. Preserve the three in-phone action
defaults—filled blue, elevated white, and blue text-only—and verify independent
text, style, text colour, background/border colour, and shape controls. Confirm
their labels stay horizontal and unclipped, the hero artwork reaches both screen
edges without white gutters, extends continuously behind the fixed
header without a seam below the logo, and the screen does not leak past the
rounded hardware corners. Confirm the artwork and selected texture dissolve
together through a long eased transition into the lower white content area,
without a straight cutoff above the headline. Preserve the crisp status-bar network treatment with
four ascending cellular bars and a complete Wi-Fi glyph containing three
separated arcs and its dot. When hero-title or supporting-copy markup is present,
verify that delimiter characters are removed, bold and independently configured
accent spans reach the resolved layout, the requested font-size extremes remain
unclipped, and each accent colour exists in the authoritative PNG pixels. For optional texture
controls, cover the off state and every bounded preset on its intended surface;
verify that off removes the full-canvas and left-copy renderer nodes, that the
left-copy finish remains clipped to its rounded safe-area surface, and that
in-phone textures stay beneath crisp fixed UI. Inspect the representative PNG
after automated checks pass.

For Natal color controls, inspect the exact chosen RGB values in the authoritative
Post lock-up and in both Phone Metrics lock-ups. Verify the complete symbol,
including its inner stroke, uses the symbol color; the word uses only the name
color; alpha geometry and dimensions match the canonical asset; independent
visibility remains intact; and the editor has no horizontal overflow at desktop,
360 CSS pixels, or WebKit mobile size.

For renderer or Studio component changes, also run the focused Studio Python
tests, the Studio web unit tests when applicable, the Owner Console production
build when applicable, and `git diff --check`. Report the exact variants and
viewports inspected. Do not deploy, publish, or mutate production as part of
this audit.

For in-phone visual generation controls, verify that “Enhance current image” is
disabled without a mutable raw hero, enabled and checked by default when one
exists, keyboard-operable at desktop and 360 CSS pixels, and sends the
bounded boolean mode to the authenticated route when no uploaded reference is selected. Provider coverage must prove
that enhancement receives the exact raw current asset, never the composited
phone preview, and persists its reference SHA-256 while failure preserves the
previous asset.
Verify every main component-setting disclosure in the Post template starts
collapsed and remains keyboard-toggleable. For the Phone hero workflow, also
exercise repeated generation: the current digest-verified thumbnail must become
visible after bounded transient media failures; an exhausted load must expose a
manual retry; an owner-unchecked Enhance choice must remain unchecked across a
fresh generation; and Generate & apply must become actionable again after both
success and failure. While a generation is active, require an explicit progress
label rather than an unexplained permanently disabled control.
When raw-hero history changes, verify that only the three newest distinct images
and their digest-addressed files remain, the current item is explicit, and
selecting an older retained item neither reorders nor drops history. Thumbnail
reads must be authenticated, private/no-store, MIME- and SHA-checked, and
bounded to a retained digest. Confirm pending editor changes are saved before
selection, the selected raw bytes reach both the authoritative render and the
next Enhance call, failure preserves current/history, and the three-column
selector remains keyboard usable without horizontal overflow at desktop and
360 CSS pixels.

All manual image-generation prompts (Post and both Landing slots) reuse the
shared optional Image Reference upload/preview/remove control and API decoder.
Verify PNG/JPEG/WebP upload, keyboard removal, 360px filename wrapping, prompt
plus image forwarding, and mutual exclusion with current-image enhancement.
Selection must perform no upload or persistence; only Generate sends pixels.
Completion, failure, scope change, and unmount must clear temporary file state
and revoke preview URLs. Invalid inputs must fail before provider invocation;
failed generation preserves current/history. Gateway forwarding and real route
validation must accompany mocked UI coverage. The bridge must advertise ephemeral
reference support before receiving pixels, persist only handle/digest metadata,
and consume or expire its bounded memory input without storing bytes in jobs.

For Templates gallery changes, build the Landing preview bundle and inspect
the real React-rendered Landing PNG as well as native Phone Metrics. Run the
Templates Playwright suite with its disposable HTTP authority at desktop, 360px
and iPhone WebKit. Check full-resolution preview links, current-version digest
binding, stale request reconciliation, refresh/restart recovery, and gallery
filter controls separately from the main Post/Landing navigation.

Verify numeric Phone Metrics drafts show three digit-bearing values and editor
provenance (AI hypothesis / Brief / owner, unvalidated). Labels must stay bound to
the exact card copy after editing, Save, approval and reload. Generated image
suggestions retain their origin after selection; changing presets alone must not
promote the suggestion to an owner override.

For App Showcase, inspect all three raw screen images and the framed result.
Fit the full generated UI proportionally in the unpadded canonical aperture;
the portrait image itself reserves camera clearance. Legacy squares remain
fully visible. Check side and bottom gutters in hero and walkthrough phones.
Check decorative icon sizes and the full-width hero wave: shared `.lp-page img`
and `svg` rules can override a less-specific template selector. Test each screen
inspector, missing-image approval feedback, and desktop/tablet/360px/WebKit page
geometry. Native gallery, editor and public output must share the same renderer.

For a catalog-wide review, enumerate all registered versions and read accepted
authored records without mutating the authority. Inspect native Post PNGs and
360px display sizes with real English/Ukrainian copy, not just `Title`. Inspect
real cutouts for preserved white screens, hands and equipment; inference success
does not prove a complete interaction. Aim for 30–36px explanatory copy and
24px secondary labels at 1080px width. Report unreadable text instead of treating
absence of overflow as success. Complete devices, subjects, logos and badges
must fit proportionally. Gallery fixtures use coherent neutral UI and preview
labels; cache refresh must retain old bytes and exact historical versions.
Use `scripts/audit_template_quality.py` followed by
`apps/commander-web/scripts/audit-template-quality.mjs` for local evidence.

For shared Landing marketing sections, verify card/review/value grids by actual
child widths, not just page overflow. Do not reuse an inner grid class on its
section wrapper. CSS masks using Vite inline SVG URLs need quoted `url("…")`;
assert computed maskImage is not `none` and inspect icon silhouettes. Test all
three preview widths plus iPhone WebKit, gradient propagation, inherited single
logo color, optional motifs, carousel focus/hover/reduced-motion behavior,
per-item visibility and store fallback navigation. Private completion hints must
not reach public pages. Reference reviews keep visible source attribution.
