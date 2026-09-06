# Commander current state

Updated: 2026-09-06
Branch: `main`
Deployment: one compatible production release across VPS services and Firebase Hosting

## Current milestone

PTW now has three owner destinations: **Brief / Бриф**, **Post / Допис**, and
**Landing / Лендінг**.
The Post destination is the project-scoped Studio creative workspace. There is
no separate Studio page and no automated Post subsystem.

An owner creates a Project and Product Brief, reviews the completed Brief, and
approves it only after choosing one common Studio template. Phone Metrics also
requires a saved creative direction: one style and one background treatment.
The owner may reset and replace that direction in the hero editor; existing
images remain untouched until another generation. Approval returns HTTP 202 with the
idempotently reserved creative, navigates to
`?page=posts&project=<project_id>&creative=<creative_id>`, and starts
`queued → composing → generating image → draft`. The image stage appears only
for `phone_metrics`.

Landing is a private responsive, fixed-section workspace created from a selected
immutable approved Post version and its approved Brief. It captures Post style
once, AI-populates Hero/three features/visual directions/three FAQs, leaves
owner evidence and contacts empty, then generates text-free Hero and visual-break
art. The rebuilt v4 renderer adds bundled typography, a balanced hero, benefit
cards, optional proof, bounded landscape art, an actionable contact panel, and
collapsed FAQs. The section inspector supports direct visual editing, all bounded
layout controls, crop focus, page language, and a selectable CTA destination.
One shared renderer powers 1280/768/360px and fullscreen previews. Save/Approve
shows Landing-only learning; approval requires essential copy, both visuals,
and one valid contact endpoint. Evidence is optional, complete when supplied,
and absent from Preview when empty. Approval validates before persisting state.
Every app keeps the canonical Natal logo/name. Landing adds three coordinated
page themes and bounded button, card, icon, and contact-panel styling. Each image
uses the same ten Post style presets and two background treatments; saved choices
feed automatic generation, manual generation, and exact enhancement with the
current page palette and slot-specific crop guidance.
The hero now demonstrates a Brief-grounded app task inside the same canonical
phone frame as Post Studio. Owners edit screen titles, descriptions, actions, and
three UI rows; Light/Dark/Glass themes and Overview/Booking/Checklist layouts are
independent of page and image styles. Screen choices and content save through the
existing bounded contract and immutable versions. New composition requires an app
feature screen, including for physical services. Preview selection stays local,
and the phone action uses the page CTA destination.
Landing has no public URL, lead handling, publishing, or Post-skill influence.

The lower owner navigation includes a compact Settings control next to language.
It opens a dedicated `?page=settings` destination rather than a dialog over the
Brief. Its ChatGPT Authorization card returns only an authorization status and, during
an owner-initiated device login, the official device URL/code. A private
root-owned `codex-auth` service updates the existing Codex CLI store and runs a
working test request before marking the status authorized. No access/refresh
token, auth-file content, or CLI output reaches the web API, frontend, or logs.

Every owner-visible API and persisted background failure uses one localized
four-part contract: outcome, plain-language explanation, the next safe action,
and bounded technical context. A successful list/detail read does not hide an
item whose stored state is `failed`. Raw provider and server output never reaches
the owner; failed Brief, Studio, phone-image, Landing, and Landing-learning work
remains explicitly retryable.

A replacement Brief creates a separate first creative. Another creative from
the same Brief is available only after the latest creative has an immutable
approved version. Cross-Project creative access fails closed.

## Studio authority

The common versioned template catalog contains:

- `universal_ad` at 1080×1080;
- `phone_metrics` at 1080×1350.

Both templates expose an independent bounded font-family and font-size control
for every editable semantic text role. The catalog provides Inter, Roboto
Condensed, Manrope, Montserrat, Source Sans 3, Oswald, Cormorant Garamond,
Cormorant Garamond Italic, Lora, and Lora Italic. Renderer-owned phone chrome,
the Natal identity, and system UI text remain fixed.

Each creative stores Project and approved-Brief lineage, ordinal, selected
template version/digest, current bounded state, generation provenance, assets,
checkpoints, and immutable versions. Templates remain common code; creatives do
not copy or modify template implementations.

PostgreSQL is the complete production authority. It stores project-scoped
creative metadata, digest-checked renderer files and PNG bytes, append-only
generation runs, immutable edit checkpoints, append-only learning runs,
learning proposals/decisions, and immutable global/Project skill snapshots.
Explicit graph edges connect Project, Brief, creative, asset, version,
checkpoint, run, and skill entities. The local authority provides the same
contract with append-only metadata below `.local/owner-briefs` and
per-creative renderer files below `.local/studio-workspace/creatives`.

This is a clean baseline plus Landing extension schema. Migrations
`001_ptw_brief_v1.sql` and `002_ptw_landing_studio_v1.sql` exist. Old singleton Studio rows,
assignment flows, schema adapters, bare mutation routes, and historical Post
tables are not accepted or migrated. `/api/v1/posts` and bare
`/api/v1/studio` remain absent.

## Studio agents and learning

Composition uses the approved Brief, selected live template catalog, canonical
`studio-creative-composer` skill, and the latest accepted global and Project
skill snapshots. Output is validated against the selected template's exact
configuration/content shape; the live catalog wins over learned instructions.

For `phone_metrics`, composition automatically starts a fresh, text-free hero
generation governed by `studio-phone-hero-generator`. The prompt includes the
saved creative direction, a Brief-derived subject description, and accepted
global and Project visual lessons. The direction remains available to a future
legend generator, which is not yet implemented.
A complete bounded prompt may contain up to 9,000 characters so the maximum
subject, selected style/background, enhancement rules, canonical skill, and
accepted lessons fit the same provider contract.
A failure keeps a deterministic editable draft and exposes a separate retry.
Manual generation can create a fresh image or enhance the exact selected raw
hero. The three newest raw hero images remain digest-checked and selectable.
Legacy Phone Metrics drafts retain their existing hero but must save a direction
before further generation, enhancement, or retry. The saved direction can be
reset from its edit icon and replaced without creating learning data.

Intermediate template, configuration, content, import, asset, generation,
enhancement, and selection edits accumulate without learning. **Save creative**
or **Approve creative** creates one immutable checkpoint only when state changed.
The `studio-edit-learner` produces an automatic Project lesson and a sanitized
global proposal. The owner chooses **Apply globally** or **Keep project-only**.
No-op saves are idempotent. Learning failure never rolls back the saved creative
or approved version and remains retryable.

The independent structured bridge advertises exactly four JSON modes:
`product_brief`, `product_brief_revision`,
`studio_creative_generation`, and `studio_edit_learning`. It also retains
one bounded `content_non_human_graphic_generation` media mode with at most one
validated PNG reference for image enhancement. Retired candidate/critic modes
are absent.

## Verification status

Landing phone verification is recorded in `.local/landing-phone`, with
before/after captures, three screen themes at 1280/768/360px, and iPhone WebKit.
The 58 web unit tests, 48 browser checks, production build, full 127-test
Validation suite, 10 Commander tests, 4 Owner Gateway tests, and 38 platform tests
pass. The Commander demo, schema idempotency, canonical skill verification,
Studio visual audit, Python compilation, and whitespace checks pass.

Production advertises the exact four structured JSON modes and one bounded media
mode. Real canaries passed for all modes, fresh image generation, exact-reference
enhancement, and Pexels. All six versioned services are healthy; ChatGPT/Codex
reports `authorized` only after its real working test passes. The public Hosting
audit confirms Brief/Post/Landing, Settings authorization, the current service
worker, App Check, CORS, authenticated rejection, and Gateway health.

The confirmation-gated production reset installed both migrations and left all
owned Brief, Studio, Landing, and graph business tables empty. Its before/after
snapshot confirmed that independent platform database counts did not change.
Both emergency stops are false, the 1 GB resource audit passed, and the scheduled
24-hour follow-up audit is active.

## Next work

Observe the scheduled 24-hour resource audit. The next owner action starts a new
Project and exercises the clean Brief → Post → Landing journey through the
deployed web console.
