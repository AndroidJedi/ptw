# TikTok `@natal_cast` setup

TikTok is shipped disabled. No access token or account ID needs to be copied into
PTW manually: the owner OAuth flow returns the `open_id`, access token, and refresh
token; PTW pins the identity and encrypts both tokens server-side.

## Owner inputs

1. Make the target TikTok username exactly `natal_cast`. The screenshot currently
   shows `serhii_ozhen` in both profile-name positions. In TikTok choose
   **Profile → Edit profile → Username** and change the Username field (the unique
   account handle), not only the display name. TikTok may limit how often a
   username can change.
2. Create or select a TikTok for Developers web app owned for Natal.
3. Add Login Kit and Content Posting API, request `user.info.basic` and
   `video.publish`, and enable Direct Post. Request `video.list` separately for
   Analytics; publishing readiness does not imply analytics readiness.
4. Register this exact callback:
   `https://commander.proove-them-wrong.com/api/v1/tiktok/oauth/callback`.
5. Verify ownership of the media URL prefix/domain used by
   `https://commander.proove-them-wrong.com/api/v1/public/tiktok-media/`.
6. Provide the app's **Client key** and **Client secret** through the hidden-prompt
   configurator. Do not paste them into chat, Git, browser settings, or a ticket.

On the production host, an authorized operator runs:

```sh
sudo /opt/ptw/commander-main/scripts/configure_tiktok.sh
```

The script stores only the client credentials and a generated 32-byte encryption
key in `/opt/ptw/secrets/tiktok/config.env` as `root:10001` with mode `0440`.
After Validation is
restarted and migration 007 is installed, open an approved Post in Studio, select
**Publish to TikTok**, choose **Connect @natal_cast**, and authorize that exact
account. PTW rejects every other username and any different `open_id` after the
first successful connection.

The Studio panel must show fresh creator options. Privacy has no default; comments,
music, commercial disclosure, and TikTok's music-usage consent must be selected
explicitly. Until TikTok approves the app audit, leave
`TIKTOK_DIRECT_POST_AUDITED=false`; PTW exposes only `SELF_ONLY`. After documented
audit approval, set it to `true` through the runtime environment and restart
Validation. A configured connection is not production acceptance: one
owner-selected approved Post must reach `@natal_cast` and reconcile successfully.

Do not claim TikTok photo analytics support from an OAuth connection or a test
fixture. After the app is audited, publish one real public photo, verify its ID
is returned by the official v2 video query with view/like/comment/share counts,
and record the canary before enabling
`TIKTOK_PHOTO_ANALYTICS_AUDITED=true`. Keep that analytics flag false during the
public publish canary; it is intentionally independent from
`TIKTOK_DIRECT_POST_AUDITED`. PTW must never scrape the public TikTok page.
Manual Analytics refresh and the labelled one-time backfill are read-only and
must not create another post.

Disconnect revokes the current TikTok access token before clearing encrypted
tokens locally. It retains the pinned `open_id`, so a different account cannot be
substituted later.
