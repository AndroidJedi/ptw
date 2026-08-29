---
name: studio-tune-local
description: Implement and iterate owner-requested Universal Ad Studio component, renderer, style, test, or Tune-wizard changes. Use for Studio tuning requests such as changing how the background looks or behaves. Apply updates to the local checkout by default; do not use for production incidents, deployment, publishing, or remote operations.
---

# Studio Tune Local

Apply requested Universal Ad Studio experiments through the local Tune workflow.
For a change request, implement and verify the update; do not stop at a proposal
or instructions for the owner to apply manually.

## Default target

- When the owner does not name a target, update only the current local checkout.
- Treat “tune,” “change,” “update,” “try,” and iteration feedback as local-only
  requests. Preserve unrelated tracked and untracked owner work.
- Do not commit, push, open a pull request, deploy, publish, contact production,
  mutate PostgreSQL, or enable remote Tune routes as part of the default local
  update.
- A remote, staging, or production target requires an explicit owner request for
  that specific operation. Follow the applicable incident or VPS operations
  skill before performing it; this standing local preference is not deployment
  authorization.

## Local update

Read `AGENTS.md`, `docs/README.md`, the current-state resume point, and the
Universal Ad Studio route before editing. Use the loopback Tune runner when the
request comes through its wizard; otherwise make the requested bounded change
directly in the local checkout. Keep the fixed semantic Studio structure and
generic renderer architecture, with Instagram-specific behavior behind its
adapter.

Before implementing a Tune request, read
[`references/owner-approved-rules.md`](references/owner-approved-rules.md).
Apply every relevant owner-approved rule unless the owner's latest explicit
instruction overrides it. When a rule describes observable behavior, preserve
or add focused regression coverage so later iterations cannot silently undo it.
Only the wizard's explicit owner approval action may add a rule; ordinary
feedback remains scoped to its iteration.

Tune only the Universal Studio renderer/configuration surface, focused tests,
styles, and Studio UI components needed by the request. The Tune runner,
launcher, authentication, production routes, Result adapter, database,
deployment, and publication boundaries remain fixed unless the owner separately
and explicitly expands the task.

## Apple-style sticker treatment

When the owner asks for an Apple/iOS-style sticker, derive the white die-cut
background from the isolated subject's final alpha silhouette. Size the solid
white contour at roughly 5–8% of the actual fitted visible subject width, not
the nominal image layer, and reserve transparent space so the contour and any
subtle outside shadow cannot clip into flat rectangular edges. Close only tiny
gaps needed for a cohesive silhouette and use narrow edge antialiasing; do not
pre-blur the mask into a white glow or soften the subject itself. The result
must contain no rectangular paper, frame, cloudy backing, or extra decoration.

Protect this behavior with a pixel-level test using an irregular transparent
subject that reaches its source bounds. Verify that the contour can extend
outside the source box while transparent corners remain transparent, then
inspect the representative Studio preview at full resolution.

Before applying a generated snapshot, reject out-of-scope writes, deletions,
symlinks, or concurrent source changes. Apply only after focused Studio tests,
the Owner Console build, and whitespace validation pass. Keep the UI functional
at 360 CSS pixels with keyboard and reduced-motion behavior.

Report the files changed and checks completed. State clearly that the result is
local and not deployed.
