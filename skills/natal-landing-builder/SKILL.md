---
name: natal-landing-builder
description: Build and iteratively revise fast, dependency-free Natal landing pages from a structured brief or completed PTW Idea Laval evaluation. Use for populating or switching among the Natal product, community, and waitlist templates, editing one canonical content block, generating private previews, preparing landing copy, publishing an explicitly selected draft snapshot, updating an existing Natal landing, or running the authenticated PTW landing workflow. Do not use for unrelated brands or arbitrary publishing targets.
---

# Natal Landing Builder

Create truthful Natal landing drafts, revise them block by block, and keep
preview work separate from explicit publication.

## Required references

Before populating or editing a page, read:

- `references/block-contract.md` for the canonical page model and protected
  boundaries.
- `references/content-guidelines.md` for copy, friction, proof, and mobile
  review heuristics.
- `references/owner-lessons.md` for generalized lessons the owner has already
  reviewed and promoted.

Also read `natal/README.md`, `natal/brand/style-guide.md`, and the manifest for
the target template when changing the renderer, templates, or static build.

## Source and brand contract

1. Keep the Natal name, canonical logo/icon assets, UI kit, template layout,
   and asset digests fixed. Do not introduce another visual system.
2. Retain the Idea Laval run and thesis IDs from the completed evaluation.
   Use evaluated audience, problem, value moment, mechanisms, and steps as
   source truth. Never turn an assumption or owner instruction into evidence.
3. Keep the CTA destination server-owned. Content work may improve CTA labels,
   but may not change where the action leads.
4. Never invent testimonials, customer counts, conversion results, prices,
   deadlines, scarcity, availability, integrations, credentials, or proof. If
   verified proof is absent, preserve the explicit honest no-proof state.
5. Use `product` for feature-led software or services, `community` for group
   participation or events, and `waitlist` for an early concept or demand test.
   Show the recommendation, but never treat it as a selection lock.

## Draft-first workflow

1. `populate_set` is one fresh, strict-schema `natal_landing_revision` agent
   turn. Return complete `LandingPageContent` models for `product`,
   `community`, and `waitlist` in the same response. Tailor copy to each fixed
   template; do not rewrite template structure.
2. Persist the draft set before the agent call. Persist all three initial
   snapshots, their content and preview digests, invocation provenance, and
   Idea lineage before reporting the set ready.
3. Render private previews as authenticated, no-store, self-contained `srcdoc`
   documents. Inline canonical CSS and assets, sandbox the iframe, make preview
   CTA links inert, and accept block-selection messages only from that exact
   iframe window.
4. `edit_block` receives the full current page for context but returns only the
   selected block. Revalidate the result, reapply protected source truth, and
   combine it with the untouched six blocks in code. Reject an edit against a
   superseded snapshot with a stale-snapshot conflict.
5. Persist every instruction immediately as append-only memory scoped to its
   Idea, template, snapshot, and block. Feedback evaluates the exact snapshot
   digest. Its zero-delta WeightUpdate adjusts the stable template/block
   component. An agent or render failure must not replace the current snapshot.
6. Keep failed population and edit attempts durable and retryable. Draft sets,
   snapshots, edit history, and unselected variants must survive refreshes and
   service restarts. Never contact Firebase while populating or editing drafts.
7. Publish only after the owner explicitly selects “Publish this version.” The
   build consumes the exact current draft snapshot and content digest without
   another agent rewrite. Only explicit publication creates a numbered,
   immutable Landing revision and its Firebase release.
8. Preserve the legacy brief-based build interface for compatibility, while
   using the draft-snapshot path for the normal owner workbench.

## Skill learning

Every block instruction creates an editable reusable-lesson proposal in
addition to scoped runtime memory. Do not write browser comments directly into
Git. Dismissal changes only proposal state. Promotion must start the bounded
owner Plan/Execute flow, may update only
`references/owner-lessons.md`, and must run the skill validator,
`scripts/verify_ptw_skills.py`, and `git diff --check`. Remove Idea-specific
facts and unsupported claims before promoting a lesson.

## Local static build

For a deliberate standalone local build, store the brief outside `natal/` and
run:

```sh
python3 -m natal.builder \
  --template <product|community|waitlist> \
  --brief <brief.json> \
  --output <approved-output-directory>
```

The builder emits `index.html`, public static assets, and private
`brief.json`, `page_content.json`, and `build.json` manifests. It refuses to
overwrite a non-empty directory unless the approved task explicitly authorizes
that exact generated directory. A local build never authorizes deployment,
publication, spend, outreach, or changes to another app.

## Verification

At minimum, verify all three templates, independent block rendering, escaping,
protected proof and CTA destination, self-contained inert previews, 360 px and
desktop layouts, and no horizontal overflow. For the authenticated workflow,
also verify population idempotency, selected-block-only edits, chronological
memory, strict schema rejection, stale conflicts, restart persistence, graph
lineage, proposal Plan bounds, retryable failures, and preview/published content
parity. Confirm `brief.json`, `page_content.json`, and `build.json` are excluded
from Firebase public files.

Run the repository gates named by `AGENTS.md`, plus:

```sh
python3 -m unittest discover -s tests/owner_gateway -p 'test_*landing*.py' -v
python3 scripts/verify_ptw_skills.py
git diff --check
```
