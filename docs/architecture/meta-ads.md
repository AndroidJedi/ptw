# Instagram publishing and project-scoped Meta Ads

Post keeps its promotional CTA artwork and editor controls. Approved Post versions
have separate **Publish to Instagram** and **Create Instagram ad** actions.
An organic image's drawn CTA is not a native clickable website button. The
website ad configures a separate Meta **Learn more** button.

## Public Landing measurement

`natal-service.com` uses one Ad Account-owned Meta Pixel from the shared public
Landing shell, so the apex and every published `ai|la|wa` route have the same
measurement boundary. The Pixel ID is public configuration, never part of the
system-user token secret. Meta's browser library and `PageView` event are loaded
only after the visitor explicitly allows analytics; rejection is persisted
locally and sends no request to Meta. Keep Firebase Hosting CSP, production
bundle verification, and desktop/mobile browser tests synchronized with this
boundary. Individual Landing records and immutable versions must not acquire
analytics fields.

## Approved sources and export

Both workflows consume exact immutable approved Post versions, with the selected
version and digest-verified PNG preview visible before submission. Draft edits
require the normal approval checkpoint; publishing never approves implicitly,
rerenders historical PNGs, or teaches Post/Brief/Landing lessons.

Post opens Ads using project, `ad_creative`, `ad_version`, and `destination=WEBSITE`
query parameters. The receiving workspace resolves only that Project's approved
source; an unavailable explicit version does not silently select another.
Workspace reads load sources, history, and the current landing without Meta calls.
Separate connection checks verify each capability, so unavailable or slow Meta
permissions do not block image download, copy, or landing-link export.

Export downloads the approved PNG and offers Copy caption/ad text, Copy landing
URL, Open Instagram, and Open in Ads Manager. These external links do not populate
Meta forms. **Exported**, **Created in Meta**, and **Published** are distinct;
manual export never creates a successful Meta publication record.

## Organic Instagram publishing

The owner reviews one image, an editable caption up to 2,200 characters, and the
configured professional Instagram account, then selects **Publish now**. Optional
link-in-bio guidance is editable. Profile changes, Facebook organic posts,
Stories, Reels, scheduling, and native organic website CTA buttons are absent.

Publishing uses the Facebook-linked Instagram API and independently verifies
`pages_show_list`, `instagram_basic`, `instagram_content_publish`, and `pages_read_engagement`,
the Page/account binding, and the publishing quota. Advertising permissions and
an Ad Account are not prerequisites for organic publishing.

The approved PNG is converted deterministically to RGB JPEG (quality 95, no
subsampling, no metadata, white under transparency), retaining source and delivery
digests. Only that approved derivative is exposed through an unguessable
43-character temporary media capability. Public reads expose bytes only, are
GET/HEAD-only, no-store/noindex, and expire after one hour or terminal completion.
The professional account API requires externally reachable JPEG media; loopback
alone is insufficient. See [Meta's publishing collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).

The server reserves an immutable request before creating a media container.
It persists container ID, waits for readiness, persists `publish_started` **before**
calling `media_publish`, and stores the returned media ID before retrieving its
permalink. Per-publication process/database locks serialize execution. Requests
retain UUIDs across browser transport failures; changed input with the same UUID
is rejected. Restart recovery resumes incomplete work using the saved identity.
A lost publish response becomes **Outcome uncertain**; Sync reads the same
container and never repeats publication. If Meta reports PUBLISHED but its media
ID was lost, **Published · link pending** remains explicit. PTW does not guess a
permalink by caption matching. A saved media ID allows later permalink recovery.

## Paid ads

Ads supports **Instagram Direct** and **Website**. Direct retains engagement,
conversations, and SEND_MESSAGE. Website uses OUTCOME_TRAFFIC,
LANDING_PAGE_VIEWS, WEBSITE, and LEARN_MORE with the current Project landing's
canonical HTTPS URL. Each Website Ad carries an offsite-conversion tracking
spec for the configured Ad Account Pixel and omits welcome-message and messaging
promoted-object fields. Both use
Instagram Feed, impressions billing, lowest-cost bidding, and opted-out standard
creative enhancements. The current [Meta SDK story specification](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adcreativeobjectstoryspec.py)
uses `instagram_user_id`; PTW retains its existing `META_INSTAGRAM_ACTOR_ID`
configuration name.

Website requests name the reviewed `landing_event_id`; the server resolves its
publication/version/URL, saves that lineage in the immutable specification, and
rechecks the event before execution. An unpublished or replaced event rejects
new execution with a refresh/review path. Completed request reconciliation still
returns its original record. Republish retains the permanent public URL.

Campaign identity is `(Project, objective, special-ad categories)`. Audience
identity remains `(Campaign, preset digest)`. Old Direct requests/specifications
and Meta IDs remain readable. Existing audience preset versions retain their
original country or verified city-radius semantics. City targets contain no
country-wide fallback. Meta names include campaign/deployment identity markers.

New Campaign, Ad Set, and Ad objects are PAUSED. Reconciliation verifies
campaign objective/categories, audience/destination/budget, creative image/copy,
and Ad associations. Existing externally activated parent campaigns/ad sets are
read without changing their status; new child ads stay paused. IDs are saved
immediately after each successful creation. Project execution locks prevent
concurrent workers from racing Meta creation. Sync appends current statuses and
issues. The owner opens Ads Manager to review, set schedules, launch, or pause
paid delivery; PTW exposes no ACTIVE mutation, spend execution, insights,
conversion tracking, or batch launch.

## Persistence and APIs

Migration `005_instagram_publication_v1.sql` adds the immutable campaign objective,
replaces the one-campaign-per-Project constraint, and adds `instagram_publications`
and append-only `instagram_publication_attempts`. PostgreSQL retains approved
source foreign keys, JPEG bytes, frozen specification, mutable execution state,
and explicit Project/Post/Landing graph lineage. Local authority provides the
same digest-chained records. Media capabilities never enter owner API responses.

Owner-authenticated organic routes are under `/api/v1/instagram`:

- `GET /connection` and `GET /projects/{project_id}`;
- `GET|POST /projects/{project_id}/publications`;
- `GET /projects/{project_id}/publications/{publication_id}`;
- `POST .../{publication_id}/retry` and `POST .../{publication_id}/sync`.

The public delivery route is `GET|HEAD /api/v1/public/instagram-media/{token}.jpg`.
Production Validation mirrors routes under `/internal/v1` and requires the
Gateway bridge token even for media; only the Gateway exposes public byte reads.

Existing Ads connection/preset/location/workspace/deployment/retry/sync routes
remain. Website deployment adds `destination_type=WEBSITE` and `landing_event_id`
and omits `welcome_message`. Direct v1 requests remain supported. Workspace
responses add `landing`; deployment cards include their own campaign ID and
Ads Manager URL. Permission checks and publication reservation use a bounded
120-second browser/Gateway deadline; waiting for media happens in background.

## Configuration and verification

Local credentials load from mode-600/400 `.local/local-studio.env`. Production
retains the six-key root-owned mode-440 `/opt/ptw/secrets/meta-ads/config.env`
mounted read-only only into Validation. Tokens are sent only in server-side
Authorization headers, never browser responses or provider-error bodies.

Use `scripts/configure_meta_ads.sh local|vps AD_ACCOUNT_ID PAGE_ID INSTAGRAM_USERNAME`
with its hidden token prompt. Pass `-` for AD_ACCOUNT_ID for an organic-only setup;
that path resolves the assigned Page and linked professional account through
`/me/accounts` without a direct Page read or
advertising calls. Advertising requires `ads_management` and
`ads_read`; grant the organic permissions above for publishing too. The helper
verifies the selected assets; the separate in-app publishing check verifies
organic capability. No token belongs in chat, Git, shell history, or arguments.

`META_PIXEL_ID` is the non-secret Ad Account-owned browser Pixel used for Website
ad readiness and tracking. Production Compose defaults to the Natal Service
Website Pixel; it is deliberately outside the strict secret file so rollback
images can ignore it. Runtime readiness lists the Ad Account's Pixels and requires
an exact configured match before Website staging.

`META_INSTAGRAM_MEDIA_ORIGIN` is a non-secret, public HTTPS Gateway origin with
no path. Production Compose defaults to `https://commander.proove-them-wrong.com`;
it stays outside the strict six-key secret file so old images can still read
that file during rollback. For local publishing, supply a deliberately configured
public Gateway origin; blank keeps organic API publication unavailable while
export and paid staging remain usable. Do not expose the complete loopback Owner
API through a tunnel merely to serve images.

Run focused backend/Gateway tests, UI unit/build and desktop/360px/WebKit checks,
`scripts/verify_ptw_brief_schema.sh`, and
`.venv/bin/python scripts/verify_instagram_schema.py`. The latter always creates
and destroys its own PostgreSQL container and verifies preservation, both campaign
identities, publication/JPEG persistence, immutable guards, graph edges, and replay.

Real readiness additionally requires an owner-selected organic post with a
verified permalink and a website ad verified PAUSED in Meta. Mocked browser/API
checks do not establish provider readiness. Production deployment and real
approved-source/PNG/Landing access checks pass; Meta credentials are absent, so
real Meta publication/ad acceptance remains outstanding. Migration-bearing
production release uses the confirmation-gated in-place preserving procedure;
it does not run a production reset.
