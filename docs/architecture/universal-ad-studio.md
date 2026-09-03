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
`phone_metrics` is a fixed 4:5 composition: off-white mineral texture,
canonical Natal lock-up in the upper-left, dark left-safe-area copy, a
near-front black phone at upper-right, three equal cobalt metric cards, and a
full-width cobalt CTA band. It accepts eyebrow, headline, supporting text,
CTA, exactly three owner statistics, and an optional renderer-owned in-phone
title. Unknown fields, an absent statistic, or a fourth statistic fail closed.

The internal primitive tree is built server-side. API callers cannot import
templates or mutate arbitrary nodes. The shared `StudioRenderer` produces the
authoritative PNG and resolved-node diagnostics.

## Natal and assets

Natal is the sole visible identity in all new Studio and local Post drafts. Its
canonical lock-up is always enabled. Owner logo uploads, logo toggles, and
brand-name substitution are absent from the control catalog; retained legacy
configuration fields exist only so historical immutable versions remain
readable.

The active `phone_metrics` frame is the owner-supplied angled mockup selected
on 2026-09-03. Its adjacent manifest records the one-time black-hardware and
matte/aperture preparation plus its SHA-256. The redundant upright source frame
was removed. Runtime code reads only this local digest-checked asset and never
fetches a device frame. The frame, visible right rail, and masked screen are
fused into one image layer, with the reference pose baked into that asset, so
they cannot drift apart.

`universal_ad` retains bounded background and Pexels-screened sticker assets.
`phone_metrics` has no owner-uploadable screen artwork: standalone Studio uses
a deterministic text-free preview visual. The local Post flow obtains final
phone art server-side through the OpenAI Image API, validates it as PNG,
records non-secret provenance, and fuses it with the fixed device. Its image
prompt and provider contract prohibit visible text, numbers, logos, UI,
buttons, charts, and metrics in generated screen art. The browser never
receives the image credential.

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
the representative universal variants and the exact 1080×1350 phone template.
The phone checks read full-resolution pixels and resolved bounds for the
off-white texture, upper-left Natal, dark left copy, upper-right angled device,
equal cobalt metric cards, CTA band, no clipping/overlap/unsafe bounds, and the
text-free screen-art fixture. A passed audit is followed by a full-resolution
visual inspection of the creative area only; social-app chrome and reference
brand wording are not part of the Studio output.

`STUDIO_TUNE_MODE=1` enables the loopback Tune wizard. It captures one requested
Studio implementation, runs Codex in an isolated worktree, enforces a
Studio-only allowlist, verifies focused tests/build checks, and presents a
preview before copy-back. Only explicit owner approval may persist a generalized
rule in `skills/studio-tune-local/references/owner-approved-rules.md`.
Production Owner Gateway does not expose Tune routes.
