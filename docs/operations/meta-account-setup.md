# Meta account setup for PTW

This runbook configures the Meta assets PTW needs for organic Instagram
publishing and PAUSED website-ad creation. It records the working Natal Service
configuration without storing access tokens.

## Production asset map

| Asset | Production value |
| --- | --- |
| Business portfolio | Natal Service |
| Meta app | PTW Local Ads |
| System user | `kiev.developers` |
| Facebook Page | Natal Service — `1337006432822527` |
| Instagram professional account | `natal_service` — `17841468586410037` |
| Primary Ad Account | `509909256695612` — UAH |
| Meta Pixel / dataset | Natal Service Website — `1056720310312959` |
| Legacy/test Ad Account | Crush Test — `3865462170368778` — do not use for production |

PTW requires relationships between these assets, not merely access for a human
administrator:

```text
Natal Service Page ──linked to──> natal_service Instagram
        │                              │
        └──────── assigned to ─────────┤
                                       v
                            Ad Account 509909256695612
                                       │
                                       └── owns/uses Pixel 1056720310312959

kiev.developers system user ──assigned to──> app + Page + Instagram + Ad Account
```

The Meta Business Settings **People** entry named
`UnclaimedBusinessUserFromPool @natal_service` is not the Instagram asset
connection required by the Marketing API. Do not use that entry to diagnose or
configure PTW.

## 1. Confirm the Facebook Page and Instagram link

1. Open [Meta Business Settings — Pages](https://business.facebook.com/settings/pages).
2. Select **Natal Service** and confirm that it belongs to the **Natal Service**
   business portfolio.
3. In Facebook Page settings, open **Linked accounts** and confirm that the
   professional Instagram account is `natal_service`.
4. Open [Meta Business Settings — Instagram accounts](https://business.facebook.com/settings/instagram-accounts).
5. Select `natal_service`. Its Instagram actor ID must be
   `17841468586410037`.

The Instagram account must be Business or Creator, not a private personal
account.

## 2. Connect Instagram to the production Ad Account

This is the relationship most often missed.

1. In [Instagram accounts](https://business.facebook.com/settings/instagram-accounts),
   select `natal_service`.
2. Open **Connected assets** and choose **Add assets**.
3. Choose **Ad accounts**.
4. Select only `509909256695612`.
5. Enable **Manage campaigns/ads** and save.

Do not perform this operation from **Users → People**. Assigning the Ad Account
to a person does not populate the Ad Account's `instagram_accounts` Graph API
edge.

## 3. Assign the Pixel to the production Ad Account

1. Open [Meta Business Settings — Pixels](https://business.facebook.com/settings/pixels).
2. Select **Natal Service Website** (`1056720310312959`).
3. Open **Connected assets** and add Ad Account `509909256695612`.
4. Grant the permission to use/manage the Pixel and save.

The Pixel is public browser configuration. It is deliberately not stored in the
six-key PTW secret file.

## 4. Assign assets to the PTW system user

1. Open [Meta Business Settings — System users](https://business.facebook.com/settings/system-users).
2. Select `kiev.developers`.
3. Choose **Add assets** and assign:

   - app **PTW Local Ads** with app-management access;
   - Facebook Page **Natal Service** with content, ads, insights, and Page
     management access;
   - Instagram account `natal_service` with content and ads access;
   - Ad Account `509909256695612` with **Manage ad accounts** or equivalent full
     advertising access;
   - Pixel **Natal Service Website** if Meta offers it in this assignment flow.

Do not select **Crush Test** for the production PTW configuration.

## 5. Configure app permissions

Open [Meta for Developers — Apps](https://developers.facebook.com/apps/), select
**PTW Local Ads**, and ensure its use cases expose the required permissions.

For paid ads:

- `ads_management`
- `ads_read`

For organic Instagram publishing:

- `pages_show_list`
- `instagram_basic`
- `instagram_content_publish`
- `pages_read_engagement`

PTW can also use the granted management permissions already present on the app,
including `business_management`, `pages_manage_ads`,
`instagram_manage_comments`, `instagram_manage_messages`, and
`instagram_manage_insights`. These do not replace the four organic publishing
permissions above. Analytics verifies `instagram_manage_insights` independently;
an account may be publishing-ready while insights remain unavailable.

## 6. Generate the system-user token last

Generate the token only after completing all asset assignments:

1. Return to [System users](https://business.facebook.com/settings/system-users).
2. Select `kiev.developers` and choose **Generate new token**.
3. Select **PTW Local Ads**.
4. Select the required permissions from the previous section.
5. Generate the token and copy it once into the hidden PTW prompt.

Never place the token in chat, source control, screenshots, shell arguments, or
command history. A token normally does not need replacement merely because an
asset assignment changed. Regenerate it when permissions were added after token
creation, it was revoked/expired, or Meta invalidated it.

## 7. Verify the Graph API relationships safely

The following check keeps the token out of shell history and prints only asset
metadata. It does not mutate Meta:

```bash
read -s "META_TOKEN?Paste token: "; echo

for path in \
  "me?fields=id,name" \
  "me/permissions" \
  "me/adaccounts?fields=id,name,currency,account_status&limit=100" \
  "me/accounts?fields=id,name,instagram_business_account{id,username}&limit=100" \
  "act_509909256695612/instagram_accounts?fields=id,username&limit=100" \
  "act_509909256695612/adspixels?fields=id,name&limit=100"
do
  printf '\nCHECK: %s\n' "$path"
  curl --globoff --silent --show-error --fail \
    -H "Authorization: Bearer $META_TOKEN" \
    "https://graph.facebook.com/v26.0/$path"
  printf '\n'
done

unset META_TOKEN
```

Required results:

- `/me/adaccounts` contains `act_509909256695612`;
- `/me/accounts` contains Page `1337006432822527`, whose
  `instagram_business_account.id` is `17841468586410037`;
- `/act_509909256695612/instagram_accounts` contains exactly one matching
  `natal_service` entry with ID `17841468586410037`;
- `/act_509909256695612/adspixels` contains `1056720310312959`;
- required token permissions have status `granted`.

## 8. Save the verified production configuration

Run the tracked helper from the Mac. Paste the token only when the hidden prompt
appears:

```bash
ssh -t -i "$HOME/.ssh/ptw_commander" -o IdentitiesOnly=yes \
  root@165.245.212.184 \
  'cd /root/ptw && scripts/configure_meta_ads.sh vps 509909256695612 1337006432822527 natal_service && docker restart ptw-validation-validation-api-1'
```

Success begins with:

```text
Selected Meta assets verified and the locked vps configuration was saved.
```

The additional output about organic permissions, media origin, and Pixel
assignment is informational. The displayed container name confirms the restart.

Production already supplies the non-secret public media origin through
Validation Compose. Do not add `META_INSTAGRAM_MEDIA_ORIGIN` or `META_PIXEL_ID`
to the strict secret file.

## 9. Verify PTW and create a PAUSED website campaign

1. Refresh the PTW Owner Console.
2. Open **Ads / Реклама**.
3. Confirm that the connection shows:

   - Ad Account `509909256695612`;
   - Page `1337006432822527`;
   - Instagram `natal_service` / `17841468586410037`;
   - Pixel `1056720310312959`;
   - configured and verified readiness.

4. Select an approved Post and the current published Landing.
5. Choose **Website** as the destination.
6. Review the frozen landing URL, audience, daily budget, creative, and copy.
7. Create the Meta structure.

PTW creates `OUTCOME_TRAFFIC` / `LANDING_PAGE_VIEWS` / `WEBSITE` with a native
**Learn more** button and Pixel tracking. Campaign, Ad Set, and Ad are all created
**PAUSED**. PTW never starts spend.

8. Open [Ads Manager for the production account](https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=509909256695612),
   review billing, schedule, audience, placements, identity, creative, URL, and
   tracking, then activate manually when ready.

## 10. Test Pixel events

Open [Meta Events Manager](https://business.facebook.com/events_manager2/list),
select **Natal Service Website**, then **Test events**. Enter the published URL,
for example `https://natal-service.com/la/natal-service`, and open it through the
test control.

On the Landing page, choose **Allow** in the analytics consent panel. PTW sends
no Pixel event before consent. Browser developer tools should then show requests
to `connect.facebook.net/.../fbevents.js` and
`facebook.com/tr/?id=1056720310312959&ev=PageView...`. Disable content blockers
for the test or use a clean browser profile if Events Manager remains empty.

## Troubleshooting map

| PTW/helper error | Meaning | Correct action |
| --- | --- | --- |
| `Configured Ad Account is not assigned to this system user` | The token cannot see the selected Ad Account. | Assign `509909256695612` to `kiev.developers` with ad-management access. |
| `Configured Facebook Page is not assigned to this system user` | `/me/accounts` does not contain Page `1337006432822527`. | Assign the Page to the system user and retain `pages_show_list`. |
| `The requested Instagram account is not uniquely available to this Ad Account` | The Ad Account's `instagram_accounts` edge has zero or multiple matching usernames. | Connect the `natal_service` Instagram asset directly to Ad Account `509909256695612`, then run the read-only Graph check. |
| `The requested professional Instagram account is not linked to this Page` | The Page-linked Instagram actor differs from the Ad Account actor. | Reconnect `natal_service` under the Natal Service Page and confirm actor ID `17841468586410037` on both edges. |
| `Configured Meta Pixel is not available to this Ad Account` | The Pixel is not assigned to the selected Ad Account. | Connect Pixel `1056720310312959` to `509909256695612`. |
| HTTP `403` for the Ad Account | Token scopes may be granted, but the system user lacks that specific asset. | Fix the asset assignment; do not switch to Crush Test merely because it is visible. |
| HTTP `400` during Page verification | Meta can allow Page discovery while rejecting a direct Page lookup, or curl may expand braces. | Use the tracked helper, which verifies through `/me/accounts` and disables curl URL globbing. |
| Pixel network request appears but Test Events is empty | Consent, browser blocking, Meta filtering, or UI delay can hide the event. | Allow analytics, disable blockers, verify the exact Pixel ID in the network request, and retry in a clean browser. |

## Security and operating boundaries

- Use only the hidden token prompt in `scripts/configure_meta_ads.sh`.
- Never print or inspect `/opt/ptw/secrets/meta-ads/config.env`.
- Keep the strict production secret file at six keys.
- Do not place tokens in browser code; the Pixel ID is public, the token is not.
- Do not use the unrelated **Crush Test** Ad Account for Natal production.
- Creating a PTW ad structure does not launch it: every new Meta object remains
  PAUSED until the owner activates it in Ads Manager.
