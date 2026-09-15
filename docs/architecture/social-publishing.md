# Instagram publishing

The active social surface is Instagram only. PTW consumes one exact immutable
approved Post version and either publishes it through the existing professional
account API or creates a manual Post package for owner upload. TikTok modules,
tables, migrations, and tests are preserved as historical recovery material,
but no TikTok route, OAuth callback, media path, runtime job, or Owner UI is
mounted.

## Organic direct publication

`SocialPublishingEngine` verifies the approved Post render digest, creates a
unique tracked Landing URL when a Landing is published, appends that URL to the
reviewed Instagram caption, and reserves the immutable publication before any
provider mutation. The adapter creates a media container, persists irreversible
mutation markers, publishes once, and reconciles status/permalink without
replaying an uncertain publish call.

The temporary media capability is an unguessable 43-character JPEG route. It is
GET/HEAD-only, no-store/noindex, digest-bound, and expires after one hour or
terminal completion. Publishing permissions are independent of advertising and
analytics permissions.

Active owner routes are `/api/v1/instagram`; Validation mirrors them under
`/internal/v1/instagram`. The public byte route is
`GET|HEAD /api/v1/public/instagram-media/{token}.jpg`.

## Manual publication

Manual export requires no verified provider connection. **Copy all texts**
creates an immutable package tied to the exact approved Post version, removes
Studio inline markers, appends a unique tracked Landing URL, and copies the
complete caption. The owner downloads the same approved PNG, uploads it in
Instagram, and may record Published or Abandoned. Landing visits and CTA events
are then attributed to that package automatically.

Paid validation and the difference from Instagram **Boost post** are defined in
[`instagram-manual-validation.md`](instagram-manual-validation.md).

## Preserved inactive providers

Meta Ads API and TikTok implementations must not be remounted by ordinary
feature or incident work. Their old authority rows remain readable history. An
explicit recovery uses `skills/legacy-social-automation-recovery/SKILL.md` and
must restore the complete security, idempotency, route, UI, job, and provider
readiness boundary—not only import a module.
