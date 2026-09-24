---
name: studio-tune-local
description: Implement and iterate owner-requested Post Studio component, renderer, style, test, or Tune-wizard changes. Use for Studio tuning requests. Apply updates to the local checkout by default; do not use for production incidents, deployment, publishing, or remote operations.
---

# Studio Tune Local

Apply requested Post Studio experiments through the local Tune workflow.
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
Post Studio route before editing. Use the loopback Tune runner when the
request comes through its wizard; otherwise make the requested bounded change
directly in the local checkout. Keep the fixed semantic Studio structure and
generic renderer architecture, with Instagram-specific behavior behind its
adapter.

Keep main Post component-setting panels expandable/collapsible and collapsed by
default in both templates. Opening one panel must remain an explicit owner action;
do not reintroduce a template-specific initially-open exception.
Every owner-editable color uses the shared native swatch plus an editable,
copy/pasteable `#RRGGBB` field; do not expose its value as read-only decoration.
Responsive subforms must follow the inspector container width, not only the page
viewport, because a desktop two-column workspace can still produce a phone-width
control rail. Verify that repeated action/metric controls stack before labels or
values collide.

Before implementing a Tune request, read
[`references/owner-approved-rules.md`](references/owner-approved-rules.md).
Apply every relevant owner-approved rule unless the owner's latest explicit
instruction overrides it. When a rule describes observable behavior, preserve
or add focused regression coverage so later iterations cannot silently undo it.
Only the wizard's explicit owner approval action may add a rule; ordinary
feedback remains scoped to its iteration.

Tune only the Post Studio renderer/configuration surface, focused tests,
styles, and Studio UI components needed by the request. The Tune runner,
launcher, authentication, production routes, database,
deployment, and publication boundaries remain fixed unless the owner separately
and explicitly expands the task.

## Local runtime refresh

For explicitly requested Landing editor changes, keep **Change template** and
**Save** as the main actions, with History and Approve/Publish behind More.
Trying a template must not require saving or approving the current Landing.
Send its exact catalog reference and one stable request UUID, retain that UUID
through uncertain responses/restarts, and open the returned Landing directly.
Preserve previous pages and tab-local pending edits with their original stale
digest. Verify an incomplete draft, lost-response retry, history restoration,
project isolation and mobile/WebKit before claiming this flow works.

Public Landing addresses use one direct permanent path, `/<slug>`. The editor
must ask only for the slug and display `https://natal-service.com/<slug>`; owner,
Gateway, public-read, asset and Analytics contracts must not expose a lane or
path-prefix choice. Retired two-segment public paths return the branded 404.

- Vite hot-module reload updates the browser bundle only. After changing a
  Python renderer, template builder, workspace/API module, font, or bundled
  renderer asset, restart the active local Studio API before asking the owner
  to inspect the result. Use `scripts/run_local_studio.sh` so the existing
  workspace and bounded local environment are preserved.
- Stop only the exact PTW loopback processes verified on port 8088 and the
  configured `PTW_LOCAL_WEB_PORT` (5173 by default);
  do not disturb unrelated development servers. After restart, verify `/healthz`,
  make an authenticated Studio detail request, and fetch a fresh authoritative
  preview PNG from the running API. Confirm the response uses the expected
  template version or changed pixels before claiming the update is visible.
- If the API process predates the renderer files and was launched without
  reload mode, treat an unchanged browser preview as a stale-runtime failure,
  not as evidence that the renderer change had no effect.

## Explicit Post previews

Studio visual references may be PNG, JPEG, WebP, or SVG. Rasterize SVG in the
browser after rejecting active/external content; send only bounded PNG to the
existing image API. Template edits accept two ordered visual references and
use registered immutable assets for final rendering.
When a fixed store-badge asset already contains its black button and border,
render it with `badge_surface: asset_only`; never paint a second slot pill behind
it. Match visible asset bounds and aspect ratio in the final PNG. Keep the
legacy `slot_pill` default for accepted templates made before this setting.

Both Post editors batch field/control edits until **Update preview**. Do not
restore debounce-driven render requests or validate incomplete fields while the
owner types. Keep the last successful image visible on pending edits and render
failure, label stale previews explicitly, and allow a fresh manual retry.
Track the exact requested draft so edits made during an in-flight render remain
stale. Preview must not create Save/Approve checkpoints or learning. Phone
Metrics CTA copy is optional: empty/whitespace copy removes its whole band,
including through Save, Approve, and reload; retain the 60-character upper bound.

For Phone hero generation, treat the checked Enhance default as initialization,
not as a value forced after every request. Once the owner explicitly turns it
off, preserve that choice across successful fresh generations and failed
retries. Keep generation pending state separate from other editor mutations,
show the active operation, and prove that success, rejection, and timeout all
restore an actionable Generate & apply control. Do not silently leave a failed
current thumbnail as an empty placeholder: retry bounded transient authenticated
media failures, expose a keyboard-operable manual retry after exhaustion, and
retain digest/MIME verification on every attempt.

Natal logo tuning may expose only the shared symbol color and `NATAL` name color.
Keep canonical alpha, dimensions, spacing, type, and placement geometry fixed;
the symbol color covers the full mark including its inner stroke. Apply the same
pair to every lock-up in one Post. Preview/configuration calls must not update
Project authority; only a Save/Approve checkpoint with a real color change may
append the Project default. New Posts/template replacements inherit and lock it,
while existing drafts and approved clones retain their own saved colors. Keep
these brand defaults outside Creative Skill learning and Landing.

## Applying a Project Post template

Use the Post editor's compact Change template chooser for accepted Post versions.
Resolve the exact surface, ID, version and digest through the authoring registry;
never admit a pending proposal or a Landing definition. Carry pending editor copy
and the current raw hero through the switch, preserve approved artifacts and
image history, and reconcile response loss with the same request UUID. The old
reset-to-preset operation is not a content-preserving template switch.

Verify the full apply/edit/preview/save/approve/restart path against real local
HTTP and disposable PostgreSQL. Clone and Landing-source reads must resolve the
approved record's template, never infer it from the creative's current layout.
Keep initial Brief generation on its supported composer definitions. Authored
layouts expose their own text fields and use the shared image workflow; do not
show unrelated Phone Metrics controls or allow the Phone-only Manual Agent to
edit them. Keep old approved PNGs byte-identical.

## Visual layout guard

For typography, positioning, spacing, component-layout, preview, or Studio CSS
changes, also read `../studio-ui-visual-audit/SKILL.md` and run its deterministic
geometry audit. Inspect the exact representative PNG at full resolution and
compare visible alpha bounds—not only nominal boxes—so font bearings, clipping,
overflow, truncation, and adjacent-block collisions cannot pass as a successful
iteration. Preserve the demonstrated invariant with a focused geometry or pixel
regression test.

Before applying a generated snapshot, reject out-of-scope writes, deletions,
symlinks, or concurrent source changes. Apply only after focused Studio tests,
the Owner Console build, and whitespace validation pass. Keep the UI functional
at 360 CSS pixels with keyboard and reduced-motion behavior.

Report the files changed and checks completed. State clearly that the result is
local and not deployed.
