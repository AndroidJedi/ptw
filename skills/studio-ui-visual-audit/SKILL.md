---
name: studio-ui-visual-audit
description: Audit Universal Ad Studio renders and editor presentation for clipping, overlap, incorrect text alignment, overflow, unsafe bounds, or responsive preview regressions. Use for visual QA of Studio renderer, layout, typography, component, or CSS changes; do not use for deployment or non-Studio Owner Console incidents.
---

# Studio UI Visual Audit

Use exact rendered evidence to distinguish a creative-renderer defect from a
browser presentation defect. Pair this review with `studio-tune-local` when the
owner also asks for implementation. Keep the work local unless the owner names
a specific remote target.

## Evidence and diagnosis

- Reproduce the reported configuration, content, assets, viewport, and language.
- Inspect the authenticated raw template-native PNG at full resolution (1080×1080
  for `universal_ad`, 1080×1350 for `phone_metrics`). If the defect
  is present there or in its resolved node manifest, fix the renderer/template;
  if it appears only in the scaled preview, fix the Studio UI/CSS.
- For text, compare visible alpha bounds with the assigned box. Treat an ink
  edge touching a clipped box, `text_layout.overflow`, truncation, or an absent
  required block as a failure—not as an acceptable visual approximation.
- Compare adjacent semantic blocks by visible bounds, not only configured
  coordinates. Preserve ordering and a positive visual gap for title,
  supporting text, bullets, and CTA.
- Check relevant optional-element states and bounded typography/layout extremes.
  For editor changes, also inspect desktop, 360 CSS pixels, keyboard behavior,
  and reduced-motion behavior.

## Regression gate

Run the deterministic Studio geometry and colour audit from the repository root:

```sh
.venv/bin/python skills/studio-ui-visual-audit/scripts/audit_universal_studio.py
```

Add focused regression coverage for the actual failed invariant. Prefer
resolved visible geometry or pixel-level assertions over snapshot hashes alone;
a changed hash proves difference, not correctness. For the Phone & metrics
template, preserve the off-white texture, upper-left Natal lock-up, left copy
safe area, fused angled right-rail device, equal cobalt metric row, full cobalt
CTA band, and a text-free generated screen-art contract. Inspect the
representative PNG after automated checks pass.

For renderer or Studio component changes, also run the focused Studio Python
tests, the Studio web unit tests when applicable, the Owner Console production
build when applicable, and `git diff --check`. Report the exact variants and
viewports inspected. Do not deploy, publish, or mutate production as part of
this audit.
