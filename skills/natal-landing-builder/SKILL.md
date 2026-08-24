---
name: natal-landing-builder
description: Preserve or inspect the dormant three-template Natal Landing source while PTW Stage 3 is inactive. Use only for source-integrity review, template inventory, or planning the later simplified Landing rebuild. Do not populate, revise, preview, publish, deploy, accept leads, generate landing copy, or register Landing APIs in the current Phase 1 runtime.
---

# Natal Landing Builder — Dormant Stage 3

The three Natal templates, assets, manifests, style guide, and dormant builder
source remain on disk for the later simplified Landing rebuild. They are not an
active product capability in PTW Validation Phase 1.

## Current rule

- The Owner Console may show only a truthful `Stage 3 pending` placeholder.
- Do not register a Landing route, public lead endpoint, preview endpoint,
  publisher, background coordinator, Firebase publisher, or Landing provider
  mode.
- Do not run or repair Landing-specific tests in the Stage 1–2 milestone.
- Do not derive Landing copy from the Product Brief yet.
- Do not delete or silently rewrite the three template families or their brand
  assets while simplifying active runtime code.

## Allowed work

Inspect `natal/README.md`, the template manifests, static assets, and reference
contracts only when preserving source integrity or planning Stage 3. A future
activation requires a new approved milestone, new Product Brief input mapping,
minimal conversion-action contract, and current tests.

Run only the general skill validator after dormant metadata changes:

```sh
python3 scripts/verify_ptw_skills.py
git diff --check
```
