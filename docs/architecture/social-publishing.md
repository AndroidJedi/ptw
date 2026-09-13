# Modular social publishing

PTW publishes one exact immutable approved Post image through a provider-neutral
engine. Public owner routes are `/api/v1/instagram` and `/api/v1/tiktok`; module
and folder names do not affect those URLs.

`SocialPublishingEngine` owns reservation, approved-source/digest verification,
locking, durable mutation markers, execution, retry, sync, recovery, public-media
capabilities, append-only attempts, and safe response projection. Provider
adapters own API payloads and status interpretation. Publication authorities
own provider-specific persistence. Engine code must not branch on a provider
name.

Both route families expose connection, Project workspace, publication list,
create/detail/retry/sync, and a one-hour capability media URL. Creation uses:

```json
{
  "request_id": "uuid",
  "source": {"creative_id": "uuid", "version": 1},
  "content": {"title": "", "description": ""},
  "settings": {},
  "creator_snapshot_sha256": null,
  "consent": {}
}
```

Instagram still accepts its legacy flat `creative_id`, `version`, and `caption`
body and retains its existing tables, fields, status aliases, IDs, graph lineage,
and media route. Its adapter creates a media container, waits for readiness, then
commits with `media_publish`.

TikTok has separate connection, OAuth-state, publication, and attempt tables from
migration `007_tiktok_publication_v1.sql`. OAuth tokens are AES-256-GCM encrypted;
the exact first `open_id` is sticky, and only username `natal_cast` can connect.
The adapter queries creator info for the panel and again immediately before
reservation. The owner manually selects privacy, comments, optional automatic
music, commercial disclosures, and posting consent. AIGC is derived from the
approved version's stored asset provenance and is never accepted from the client.

TikTok photo Direct Post starts with `content/init`, so `transfer_started` and
`commit_started` are durably true before that call. A lost response becomes
`uncertain` and is never submitted again. A returned `publish_id` becomes
`external.transfer_id`; reconciliation only polls TikTok status. Capability media
remains available until its original one-hour expiry so TikTok can finish a
`PULL_FROM_URL` download. Public privacy options remain filtered to `SELF_ONLY`
until `TIKTOK_DIRECT_POST_AUDITED=true` is explicitly configured after audit.

Common phases are `queued`, `preparing`, `publishing`, `published`,
`published_unresolved`, `uncertain`, and `failed`. Common responses expose
provider/publication/Project/request/source/content/settings/account, external
identity and mutation flags, retry/sync safety, error, and creation time. Provider
credentials and raw provider bodies never enter those responses or attempts.

## Analytics projection

Future Instagram and TikTok reservations receive an opaque tracked Landing URL
when the Project has an active published Landing. The URL is stored separately
under the frozen analytics specification and is exposed with analytics
readiness, freshness, and attribution fields. It is never appended to or used
to rewrite the organic caption.

Analytics authorization is independent from publishing. Instagram separately
checks `instagram_manage_insights`. TikTok separately checks `video.list` and
queries the official v2 video endpoint for view, like, comment, and share
counts. A publishing-ready account may therefore show Analytics unavailable.
TikTok photo insight support is not claimed until the real public-photo canary
has been audited; provider pages are never scraped.

Immutable provider snapshots are scheduled for 24h, 72h, 7d, 14d, and 30d.
Manual refresh is read-only. The one-time older-publication backfill is visibly
labelled and never synthesizes historical milestone values. Complete semantics,
normalization, and failure behavior are defined in
[Analytics and reviewed Creative Skills](analytics-and-creative-learning.md).

Official provider contracts: [TikTok photo posting](https://developers.tiktok.com/docs/en/content-posting-api-reference-photo-post),
[creator information](https://developers.tiktok.com/docs/en/content-posting-api-reference-query-creator-info),
[post status](https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status),
[video query](https://developers.tiktok.com/doc/tiktok-api-v2-video-query/),
and [OAuth token lifecycle](https://developers.tiktok.com/docs/en/oauth-user-access-token-management).
