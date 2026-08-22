# Natal landing builder

Status: local implementation complete; production deployment not requested
Updated: 2026-08-22

## Purpose

Natal is a fast, repeatable landing-page factory. Every generated app keeps the
exact Natal name, canonical logo, icon set, color tokens, typography, and
mobile/accessibility baseline. Only evaluated product content changes.

The canonical kit is `natal/`. Its PNG and SVG assets are copied from
`natal_business` and pinned by SHA-256 in `natal/brand/brand.json`. Three
dependency-free static structures distill the supplied reference projects:

| Template | Source structure | Use |
| --- | --- | --- |
| `product` | `natal_landing` | SaaS, software, B2B, or feature-led services |
| `community` | `sesh` | Events, offline participation, groups, or communities |
| `waitlist` | `ofc_landing` | Early concepts and lean demand validation |

The templates share one stylesheet and runtime. The builder accepts a bounded
version-1 JSON brief, validates copy and CTA URL schemes, HTML-escapes supplied
text, verifies brand asset digests, and emits a static site plus normalized
`brief.json` and provenance-bearing `build.json`. It refuses to overwrite a
non-empty output directory unless explicitly told to do so.

## Commander handoff

The Owner Console `Лендинги` tab reads completed live Idea Laval cases through
the authenticated Owner Gateway. The gateway resolves the preferred thesis and
maps its target user, problem, value moment, mechanisms, and loop into an
editable brief while retaining the Laval run and thesis IDs. Browser overrides
cannot change those source IDs or the Natal brand.

Template recommendation is deterministic: community/event semantics choose
`community`, product/system semantics choose `product`, and other early
concepts choose `waitlist`. The owner may explicitly override the structure.

Submitting the brief creates a normal Commander Plan command containing an
explicit `$natal-landing-builder` invocation and a unique
`output/landings/<run>-<template>-<build>` target. Plan approval remains the
existing one-shot execution gate. The skill writes a temporary input brief and
runs `python3 -m natal.builder`; it may generate and preview the local static
site but may not deploy, publish, contact people, spend money, or invent proof.

This first integration deliberately reuses durable command-session and platform
job history. Generated pages are test artifacts; a future publishing milestone
must add its own PostgreSQL landing entity/artifact lineage and explicit deploy
contract before presenting published state as authoritative.

## Verification

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
python3 -m unittest discover -s tests/owner_gateway -p 'test_landing_builder_proxy.py' -v
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
python3 scripts/verify_ptw_skills.py
git diff --check
```
