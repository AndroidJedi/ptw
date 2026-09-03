# Commander current state

Updated: 2026-09-03
Branch: `codex/web-only-commander`
Deployment: not authorized; local checkout only

## Current milestone

Universal Studio now has two bounded server-owned templates: existing
`universal_ad` at 1080×1080 and `phone_metrics` at 1080×1350. Applying either
template replaces all mutable configuration, owner copy, and mutable assets;
immutable versions remain byte-for-byte historical records. Missing selection
metadata retains the legacy Universal Studio behavior.

`phone_metrics` is the owner-approved 4:5 Natal composition: off-white texture,
canonical Natal lock-up upper-left, dark left-safe copy, an owner-supplied
black perspective iPhone with visible right rail, three equal cobalt statistic
cards, and a cobalt bottom CTA band. Its sole static frame is checked in with a
source/license/SHA-256 manifest and is never fetched at runtime; the redundant
upright frame was removed. The fixed frame, its aperture, and text-free screen
art are one precomposited layer, so the supplied pose cannot drift apart.

Natal is the only visible identity in new Studio and local Post drafts. The
canonical lock-up is always enabled. Owner logo upload/toggle/brand substitution
is absent from the new template controls; immutable legacy versions remain
readable.

The local Post start screen exposes both template choices before the draft is
created and locks the choice afterward. Phone drafts collect bounded copy and
exactly three owner metrics, then generate a server-side OpenAI text-free
screen visual under an explicit no-text/no-logo/no-UI contract. They have no
after-start Tune action. Universal drafts retain the existing bounded Pexels
and comment-tuning flow. No production Owner Gateway, Brief handoff, Telegram,
database, Firebase, or deployment behavior changed.

Mutable local Post v1 drafts created before template selection and the fixed
Natal lock-up are recovered once, append-only, when their Studio state digest
is stale: they become an explicit `universal_ad` v2 draft with the current
Studio preview digest. Any v2 draft, phone draft, or immutable approval still
fails closed on a digest mismatch.

## Verification status

- Validation pipeline: 79 tests passed in the repository virtual environment.
- Focused Post/Studio/phone regressions: 39 tests passed, including static
  frame digest/no-runtime-fetch, grouped device composition, Natal-only
  identity, template replacement, legacy-version preservation and recovery,
  three-metric validation, and 1080×1350 rendering.
- Owner Console: 35 Vitest tests and the production TypeScript/Vite build
  passed.
- Extended Studio visual audit passed six universal variants plus the exact
  full-resolution `phone_metrics` 1080×1350 composition. It checks texture,
  Natal placement, left-safe copy, upper-right right-rail phone, metric cards,
  CTA, bounds/collisions, and text-free phone artwork. The creative render was
  visually inspected without social-app chrome.
- Commander: host suite passed 6 tests with 2 FastAPI-dependent skips; the
  built runtime image passed all 8 tests. The deterministic Commander demo
  completed.
- Canonical skill synchronization and skill verification passed.

No production state was touched.

## Next work

Keep both Studio templates and the Post milestone local until the owner
explicitly requests production integration. That future work must define
PostgreSQL entity/edge and PNG authority, add authenticated Owner
Gateway/internal routes, verify restart/idempotency, and preserve the rule that
only explicit approval creates an asset. Do not reuse the retired Result
schema, routes, or local data.
