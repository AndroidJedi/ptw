---
name: natal-landing-builder
description: Build fast, dependency-free Natal landing pages from a structured brief or completed PTW Idea Laval evaluation. Use for selecting among the Natal product, community, and waitlist templates, preparing landing copy, generating a previewable static build, or updating an existing Natal landing. Do not use for unrelated brands or automatic publishing.
---

# Natal Landing Builder

Create a truthful, previewable Natal site while keeping the brand identity and
template system canonical under `natal/`.

## Build contract

1. Read `natal/README.md`, `natal/brand/style-guide.md`, and the manifest for
   the selected template. Do not rename Natal, edit canonical logo/icon files,
   or introduce a second visual system.
2. When the source is a completed Idea Laval evaluation, retain its Laval run
   and thesis IDs in `brief.source`. Use evaluated target user, problem, value
   moment, mechanisms, and loop steps. Do not turn assumptions into proof.
3. Select `product` for software/service and feature-led conversion,
   `community` for events or group participation, and `waitlist` for an early
   concept or lean demand test. When Commander supplied a template, respect it.
4. Follow `natal/brief.schema.json` and populate the version-1 brief fields:
   `business_idea`, `target_audience`,
   `pain`, `promise`, one to six `key_features`, two to five `steps`, optional
   verified `proof_points`, optional `faq`, `cta`, `language`, and `source`.
5. Never invent testimonials, customer counts, conversion metrics, prices,
   deadlines, scarcity, launch availability, or integrations. If proof is not
   supplied, keep the builder's explicit no-proof state.
6. Generate only within the output path named by the approved task. A normal
   build is local static output, not authorization to deploy, publish, spend,
   contact users, or change another app.

## Generate and verify

Store the brief as JSON outside the canonical `natal/` kit, then run:

```sh
python3 -m natal.builder \
  --template <product|community|waitlist> \
  --brief <brief.json> \
  --output <approved-output-directory>
```

The builder validates copy bounds and CTA schemes, checks canonical asset
digests, emits source IDs in `brief.json` and `build.json`, and refuses to
overwrite a non-empty directory. Use `--overwrite` only when the approved task
explicitly identifies that existing generated directory.

Preview the generated `index.html` at 360 px and desktop widths. Confirm the
Natal name/logo, CTA destination, no horizontal overflow, no unfilled template
tokens, and no unsupported claims. Run:

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
git diff --check
```
