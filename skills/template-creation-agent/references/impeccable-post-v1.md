# Impeccable Post polish v1

PTW adaptation of Paul Bakaus's Impeccable focused-refinement guidance:
https://impeccable.style/docs/improve-design/
https://github.com/pbakaus/impeccable
Reviewed 2026-10-11. Upstream copyright 2025 Paul Bakaus; Apache-2.0
(see impeccable-LICENSE.txt). This is a rewritten, reduced Post-only profile,
not the upstream browser workflow. PTW's structured contract takes precedence.

Inspect the baseline before choosing a small improvement. Strengthen the
reading order with restrained type sizes and weights. Make spacing and
alignment consistent, keep related elements together, and give the image and
headline adequate room. Check the rendered result for clipping and crowding.
If the baseline already works, return no edits instead of manufacturing change.

Only adjust existing component box/mobile_box, font_size, font_weight,
align, or text-group gap/bullet_indent. Native Daddy
may adjust existing position, dimensions, text sizes, gap, padding and alignment.
Keep positions within 100/1000 canvas units (10 native percentage points),
dimensions and numeric typography within 40% of the baseline. Box dimensions
must also remain at least 65% of their original size. Preserve overall placement.
Never add/remove/reorder components or change copy, image assets, colors,
gradients, font families, roles, visibility, canvas, device pose or branding.
Compare against the saved original and the polish request. Do not reopen old
reference differences. No redesign, image generation, automatic acceptance or
marketing-performance claims.
