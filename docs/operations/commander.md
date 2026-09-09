# PTW service operations

Build matching Linux/amd64 Commander, Validation, Owner Gateway, platform API,
and platform worker images off-host with one non-`latest` release tag.
Production starts them serially with `--no-build`.

The unrelated bridge under `/opt/ptw/platform` must advertise exactly
`product_brief`, `product_brief_revision`,
`studio_creative_generation`, and `studio_edit_learning` JSON modes plus the
bounded `content_non_human_graphic_generation` media mode. Enhancement accepts
at most one digest-checked PNG reference. Run real canaries for all JSON modes,
fresh image generation, enhancement, and Pexels before either authorized
maintenance path.

`scripts/publish_ptw_release_serial.sh` remains the destructive reset publisher
and accepts only `RESET PTW PRODUCTION`. Data-preserving releases enter through
`scripts/publish_ptw_in_place_serial.sh` and require exactly
`DEPLOY PTW IN PLACE`. The in-place path acquires the same maintenance lock,
requires matched versioned images and exact PTW/platform revisions, deploys and
audits the public Firebase shell first, stops Commander-database writers,
creates a root-only checksummed PostgreSQL custom-format backup, fingerprints
every pre-existing business row, applies pending additive migrations through 005, proves all
fingerprints unchanged, and cuts Commander, Validation, then Owner Gateway over
serially. Failure restores prior service images without reversing the additive
migration. Dependency/resource canaries and the persistent 24-hour audit remain
mandatory.

Firebase Hosting uses the named `owner-console` and `public-landings` targets.
The public target is `natal-landings-86123`; `/` is the English Natal umbrella
and `/ai|la|wa/<slug>` are SPA deep links using the exact private renderer in
non-editing mode. The shell is noindex/disallow-all and its visual 404 is HTTP
200, while its backing API returns 404. Before custom-domain transfer, run
`scripts/archive_natal_dashboard.sh` to preserve the old site assets,
screenshots, Firebase metadata, and SHA-256 manifest. DNS/custom-domain transfer
and later old-site disablement remain manual, separately authorized operations.

After cutover verify Brief approval-to-creative navigation, project isolation,
composition, automatic phone image, edit/save learning, global decision,
creative approval, graph persistence, immutable assets/versions/skills,
failure/retry paths, restart recovery, the PWA cache, schema/skill checks, and
dependency/resource audits. Never log prompts, credentials, image bytes, or
Telegram tokens. Never deploy or reset without the owner’s separate explicit
instruction and exact confirmation.

Deployment uses the existing bot canary in `--read-only` mode. It verifies bot
identity without sending an unsolicited owner-chat message.
