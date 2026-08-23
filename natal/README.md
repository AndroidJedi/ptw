# Natal landing factory

This package turns exactly one active, approved Marketing Positioning revision
into three dependency-free, mobile-first Natal landing drafts. Natal name,
assets, tokens, layouts, evidence, privacy URL, form behavior, publication
target, and graph IDs remain server-owned.

The v2 page model contains eight independent blocks: `hero`, `problem`,
`features`, `steps`, `proof`, `faq`, `final_cta`, and `lead_form`. The agent may
choose `waitlist`, `contact_request`, or `community_interest` and tailor its
heading/body. Fields, validation, consent, submit labels, success copy, and
notification behavior come only from `natal/forms.py`.

```sh
python3 -m natal.builder --list-templates
python3 -m natal.builder \
  --template product \
  --brief path/to/approved-positioning-brief.json \
  --output output/landings/example
```

The build contains public `index.html`, `styles.css`, `app.js`, and canonical
assets plus private `brief.json`, `page_content.json`, and `build.json`
manifests. Firebase publishes only the public allowlist. Private previews are
self-contained and inert. Publication consumes the exact selected snapshot,
enables its form, and performs no additional agent rewrite.

`skills/natal-landing-builder/` is the canonical agent contract. Owner feedback
edits one block at a time and produces append-only feedback, a zero-delta weight
update, a superseding snapshot, and an editable lesson proposal.
