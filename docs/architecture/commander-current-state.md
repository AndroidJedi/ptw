# Commander current state

Updated: 2026-09-02
Branch: `codex/web-only-commander`
Deployment: not authorized; local checkout only

## Current milestone

The first streamlined Post step is implemented for the loopback local app. One
completed, owner-approved Product Brief creates at most one mutable post draft.
The draft uses the exact Universal Studio v5 configuration, v2 semantic
content, stable component setting IDs, Pexels provenance, primitive template,
and 1080×1080 renderer in a separate per-post workspace below
`.local/post-workspace`.

The comment field directly below the preview is translated by one structured
local agent into strict Studio setting/content commands and, when requested,
one semantic Pexels asset query. Natural visual intent such as "pick image
with thinking human face" becomes a concrete photographic face query. Applied
commands remain ID-explicit in the UI and append-only local history.

Sticker comments resolve to the real optional Studio Sticker component. Adding
or replacing one sources a screened Pexels photograph of a physical object,
requires provider metadata to match the requested subject, applies the bounded
isolation transform, retains provenance, and enables the exact
`configuration.sticker.enabled` setting. For an add/replace comment, the
structured output contract permits only a `sticker_object` image request; an
unrelated background request or a stale stored Sticker cannot satisfy it. A
generic request carries two agent-selected fallback objects so an unusable
Pexels result can fail closed without making the command silently do nothing.
An owner-named object is never substituted. Validation also rejects the former
emoji-in-copy regression, retained scenes, and partial objects whose isolated
alpha still touches the source frame.

Generation and tuning never create an asset. Explicit approval captures the
exact PNG, Brief and Project IDs, state and template digests, configuration,
content, component settings, and source provenance as one immutable local
asset. Approved posts cannot be tuned again.

The retired Social posts/Result subsystem remains absent. No production
database, Owner Gateway route, structured bridge mode, provider, Telegram
delivery, Firebase release, or deployment was changed. Production navigation
continues to contain Product Briefs and Universal Studio only; the Post step is
shown only by the local app launcher.

## Verification status

The local Simple Post milestone is verified:

- Validation, post workflow, and standalone Studio: 70 tests passed in the
  repository virtual environment.
- Owner Console: 34 unit tests, the TypeScript/Vite production build, and 21
  desktop/360px-mobile/WebKit Playwright tests passed.
- The deterministic Universal Studio geometry audit passed all six variants.
  The exact 1080×1080 default PNG was inspected at full resolution with no
  clipped or overlapping visible text or unsafe bounds.
- The semantic tuning regression proves that "Pick image with thinking human
  face" reaches the agent and resolves to exact setting IDs plus a thoughtful
  visible-face Pexels query.
- The literal live comment `add sticker` replaced the rejected smartphone
  cutout with a screened light-bulb photograph, enabled the Sticker setting,
  preserved the original background, and produced an inspected 1080×1080
  preview with the Sticker visible, bounded, and clear of the title and CTA.
- Standalone Studio was also tested from an empty Sticker slot: with Pexels
  configured, clicking the previously disabled toggle sourced the screened
  light-bulb object and enabled the component in the live preview.
- Commander: all 8 tests passed in the built runtime image, and the
  deterministic Brief lineage demo passed. Skill validation and whitespace
  validation also passed.

No production state was touched.

## Next work

Keep the Post milestone local until the owner explicitly requests production
integration. That separate milestone must define PostgreSQL entity/edge and
PNG authority, add authenticated Owner Gateway/internal routes, extend the
structured bridge capability contract, verify restart/idempotency behavior,
and preserve the rule that only explicit approval creates an asset. Do not
reuse the retired Result schema, routes, or local data.
