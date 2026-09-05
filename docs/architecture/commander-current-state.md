# Commander current state

Updated: 2026-09-05
Branch: `codex/web-only-commander`
Deployment: local change; not deployed

## Current milestone

PTW now has two owner destinations: **Product Briefs** and **Post / Допис**.
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

This is a clean first-version schema. Only
`db/migrations/001_ptw_brief_v1.sql` exists. Old singleton Studio rows,
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

The clean baseline schema and idempotent application passed against disposable
PostgreSQL. The final local matrix passes 111 validation tests, four Owner
Gateway tests, 46 web unit tests, the production web build, 18 browser tests,
the complete Studio visual audit, canonical skill verification, Commander host
tests/demo, whitespace checks, and 28 independent platform-bridge tests. The
Commander host run skips its two FastAPI-only Telegram checks; both passed in
the built image. A final disposable-database rerun could not start after Docker
Desktop stopped, but no schema change followed its successful baseline run.

## Next work

Deploy only after a separate explicit owner instruction and production
confirmation. No production reset or deployment is part of this local
implementation.
