---
name: natal-landing-builder
description: Populate, inspect, and revise the three fixed Natal landing templates from one explicitly approved PTW Marketing Positioning revision. Use for private product, community, and waitlist drafts, eight-block edits, exact-snapshot publication, or Landing lesson proposals. Do not use for unapproved positioning, unrelated brands, arbitrary publishing targets, or ad generation.
---

# Natal Landing Builder

Create truthful Natal landing drafts, revise one block at a time, and keep
private preview work separate from explicit publication.

## Required references

Before populating or editing, read:

- `references/block-contract.md` for the eight-block model and protected data.
- `references/content-guidelines.md` for copy, evidence, trust, and mobile
  review heuristics.
- `references/owner-lessons.md` for explicitly promoted lessons.

Read `natal/README.md`, `natal/brand/style-guide.md`, and the selected template
manifest before changing code, templates, or static assets.

## Source and brand contract

1. Accept only the active approved `positioning_project_id` and
   `positioning_revision_id`. Never substitute a newer, older, or pending
   revision.
2. Keep Natal name, canonical assets/digests, visual tokens, and three layouts
   fixed. Do not create another visual identity.
3. Preserve source facts, verified proof, honest limitation, HTTPS privacy URL,
   form catalog/fields, CTA destination, publication target, and graph IDs.
4. Never invent testimonials, metrics, customer results, prices, deadlines,
   scarcity, integrations, credentials, or proof. An owner instruction is not
   evidence.
5. Use `product` for feature-led offers, `community` for participation, and
   `waitlist` for an early demand test. A recommendation never locks selection.

## Draft and publication workflow

1. Persist the draft set before one fresh, strict-schema
   `natal_landing_revision` turn. Return complete v2 pages for `product`,
   `community`, and `waitlist` together.
2. Each page contains exactly eight blocks. The agent may choose one code-owned
   form ID and tailor only its heading/body. The server owns fields, validation,
   submit/success text, consent, privacy link, and notification behavior.
3. Persist all three initial snapshots, exact positioning lineage, content and
   preview digests, and invocation provenance before reporting completion.
4. Render authenticated, no-store, self-contained private previews. Forms and
   CTAs stay inert and Firebase is never contacted during population or edits.
5. `edit_block` receives the whole page but returns only the selected block.
   Revalidate, reapply protected values, and replace only that key. Reject stale
   snapshot edits.
6. Persist feedback, zero-delta WeightUpdate, scoped history, failures, and
   retries append-only. A failed agent or render attempt never replaces the
   current snapshot.
7. Publish only the explicit current snapshot. Do not call an agent or rewrite
   copy during publication. Only the published build activates its exact form.

## Skill learning

Every correction creates an editable generalized lesson proposal. Browser
feedback never writes Git directly. Promotion must use bounded Plan/Execute,
may update only `references/owner-lessons.md`, and must run the skill validator,
`scripts/verify_ptw_skills.py`, and `git diff --check`.

## Verification

Verify three templates, eight-block isolation, protected evidence/privacy/form
data, inert preview, exact-snapshot publication, public/private file parity,
360 px and desktop layouts, no horizontal overflow, idempotency, stale edit
conflicts, retries, restart recovery, graph lineage, and lesson-plan bounds.

Run:

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
python3 -m unittest discover -s tests/owner_gateway -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
