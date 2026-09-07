# Project-scoped Meta Ads staging

Ads / Реклама is a separate Project workspace. It stages an immutable approved
Post Studio render as `Campaign → Ad Set → Ad Creative → Ad` through Meta
Marketing API `v26.0`. It does not change the Studio renderer or its learning
architecture.

## Safety boundary

- Campaign, Ad Set, and Ad are server-owned `PAUSED`; no request can select
  `ACTIVE`.
- Delivery is fixed to Instagram Feed, `OUTCOME_ENGAGEMENT`, Instagram Direct,
  `CONVERSATIONS`, `IMPRESSIONS`, and lowest cost without a bid cap.
- Creative standard enhancements are opted out. The uploaded PNG is read from
  the approved Studio version and must match its saved SHA-256.
- v1 has no activation, spend execution, organic publishing, insights,
  stop-rules, or batch launch.
- PTW does not create a Facebook Page or Ad Account. Create those manually,
  assign them to the Business Portfolio/system user, connect a professional
  Instagram account, and then configure their IDs.

The official references for the supported object creation and onboarding
boundaries are the [Meta Marketing API collection](https://www.postman.com/meta/facebook-marketing-api/documentation/0zr4mes/facebook-marketing-api-mapi),
[Marketing API onboarding](https://www.postman.com/meta/facebook-marketing-api/documentation/9jo4f5y/mapi-onboarding),
and [Pages API collection](https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api).

## Local and VPS configuration

Store only these values in `.local/local-studio.env`, with file mode `600` or
`400`:

```dotenv
META_SYSTEM_USER_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=...
META_PAGE_ID=...
META_INSTAGRAM_ACTOR_ID=...
META_GRAPH_API_VERSION=v26.0
META_ADS_NAME_PREFIX=[PTW LOCAL]
```

The token is sent to Meta only in the server-side Authorization header. It is
never persisted, returned by an API, sent to the browser, or included in an
error/log payload. Missing credentials or assets that fail verification disable
staging and leave the rest of the local owner app usable. The system user needs
`ads_management` and `ads_read` for its assigned assets.

On the VPS, store the same six literal assignments in
`/opt/ptw/secrets/meta-ads/config.env`, owned by `root:10001` with mode `440`.
The Validation container receives only that read-only file at
`/run/ptw-meta-ads/config.env`; the token is not placed in Compose interpolation,
container environment metadata, PostgreSQL, or the Owner Gateway. Use a distinct
production prefix such as `[PTW VPS]`. A missing file leaves Ads safely disabled.
The checked-in `deploy/meta-ads/config.env.example` is a value-name template
only and must never receive a real token.

Start the loopback app with `scripts/run_local_studio.sh`. The Ads connection
card lists the system user's available ad accounts and the Page/Instagram assets
assigned to the selected account. It identifies the configured selection without
exposing credentials.

To avoid putting a token in chat, shell history, or process arguments, configure
and verify the currently selected assets through the hidden prompt:

```sh
scripts/configure_meta_ads.sh local AD_ACCOUNT_ID PAGE_ID INSTAGRAM_USERNAME
```

Run the same script as root with `vps` on the server to create the isolated VPS
file. The helper makes only read-only discovery calls; it never creates ads.

## Immutable input and naming

The source list contains only approved Studio versions. Headline defaults to
`hero_title`; primary text defaults to `supporting_text` followed by `offer`;
CTA is fixed to `SEND_MESSAGE`; the welcome message defaults to localized
“Вітаю! Хочу дізнатися більше.” The owner may edit the three text fields before
staging. The normalized final specification is then immutable.

Presets are append-only versions containing name, countries, age range, gender,
and daily budget in the ad account's minor currency units. One Project owns one
Meta experiment/campaign. One unique preset specification SHA-256 within that
experiment owns one Ad Set. Every deployment owns one Creative and one Ad.
Changing targeting or budget creates another immutable preset snapshot and Ad
Set; it never rewrites the prior Ad Set.

Meta object names include the `[PTW LOCAL]` prefix and deterministic PTW UUID or
digest markers. A deployment request has a UUID `request_id`. Replaying the same
ID and normalized payload returns the existing deployment; changing the payload
for the same ID is rejected.

## Recovery, persistence, and API

The adapter saves each returned Meta ID immediately. After a timeout it first
searches the relevant Meta edge for the exact saved PTW marker and resumes at the
first missing step. Re-uploading identical approved bytes resolves to the same
account image hash. Interrupted local and PostgreSQL deployments are recovered
on service restart. Failed runs remain explicit and retryable.

Migration `003_ptw_meta_ads_v1.sql` adds preset versions, one Project workspace,
audience snapshots, deployments, append-only stage runs, and append-only status
snapshots. Graph lineage is explicit: Project `contains` experiment; experiment
`contains` audiences/deployments/runs; deployment `derived_from` the exact
approved Studio version. `.local/owner-briefs` retains the equivalent digest-
chained append-only records.

Owner routes are:

- `GET /api/v1/ads/connection`;
- `GET|POST /api/v1/ads/presets`;
- `GET /api/v1/ads/projects/{project_id}`;
- `POST /api/v1/ads/projects/{project_id}/deployments`;
- `POST /api/v1/ads/projects/{project_id}/deployments/{deployment_id}/retry`;
- `POST /api/v1/ads/projects/{project_id}/deployments/{deployment_id}/sync`.

All are owner-authenticated. Project/deployment/source IDs fail closed across
Projects. Sync reads Campaign, Ad Set, and Ad status/issues and appends a local
snapshot; it never activates an object.

## Real local canary

After the owner manually creates the Meta App/system user and saves the four
credentials, create one `[PTW LOCAL]` deployment from Ads. Open its Ads Manager
link, use Sync, and verify Campaign, Ad Set, and Ad each report `PAUSED`. Do not
turn any object on as part of this canary.
