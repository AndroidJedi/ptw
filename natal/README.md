# Natal landing factory — dormant Stage 3 source

This package is preserved source, not an active PTW Validation Phase 1 runtime.
The `product`, `community`, and `waitlist` templates, assets, tokens, layouts,
page/form contracts, and renderer remain on disk for the later simplified
Landing conversion checkpoint.

The dormant v2 page model contains eight independent blocks: `hero`, `problem`,
`features`, `steps`, `proof`, `faq`, `final_cta`, and `lead_form`. The agent may
choose `waitlist`, `contact_request`, or `community_interest` and tailor its
heading/body. Fields, validation, submit labels, success copy, and
notification behavior come only from `natal/forms.py`.

Do not invoke the historical builder, run Landing-specific suites, register its
API/coordinator/provider mode, publish Firebase Landing content, or accept leads
during the Stage 1–2 milestone.

The build contains public `index.html`, `styles.css`, `app.js`, and canonical
assets plus private `brief.json`, `page_content.json`, and `build.json`
manifests. Firebase publishes only the public allowlist. Private previews are
self-contained and inert. Publication consumes the exact selected snapshot,
enables its form, and performs no additional agent rewrite.

`skills/natal-landing-builder/` is the canonical dormant-source guard. Future
activation requires a separately approved Stage 3 contract sourced from one
approved Product Brief.
