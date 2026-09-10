# PTW service operations

Normal non-migration releases use the component planner and selective publisher:

```sh
scripts/release_ptw_fast.sh --release-tag RELEASE \
  --confirm 'DEPLOY PTW PRESERVING'
```

The command reads the deployed PTW and platform revisions, computes the exact
committed path delta, builds affected Linux/amd64 images in parallel, streams
only those checksumed archives, and restarts only affected services. Commander,
Validation, Owner Gateway, and hosted GOD persist independent image references;
unchanged services retain their current image. Hosted GOD has a small dedicated
image rather than carrying the complete Validation/Pillow/PostgreSQL runtime.
Unknown runtime paths conservatively select every PTW image and both Hosting
targets. The VPS recomputes the streamed plan and requires its base and target
to match the deployed and requested revisions.

The unrelated bridge under `/opt/ptw/platform` must advertise exactly
`product_brief`, `product_brief_revision`,
`studio_creative_generation`, and `studio_edit_learning` JSON modes plus the
bounded `content_non_human_graphic_generation` media mode. Enhancement accepts
at most one digest-checked PNG reference. When Validation or the platform
changes, run real canaries for all JSON modes, fresh image generation,
enhancement, and Pexels before accepting that release.

`scripts/publish_ptw_release_serial.sh` remains the destructive reset publisher
and accepts only `RESET PTW PRODUCTION`. Migration-bearing releases enter through
`scripts/publish_ptw_in_place_serial.sh` and require exactly
`DEPLOY PTW IN PLACE`. That path acquires the same maintenance lock,
requires matched versioned images and exact PTW/platform revisions, deploys and
audits the public Firebase shell first, stops Commander-database writers,
creates a root-only checksummed PostgreSQL custom-format backup, fingerprints
every pre-existing business row, applies pending additive migrations through 005, proves all
fingerprints unchanged, and cuts Commander, Validation, then Owner Gateway over
serially. Failure restores prior service images without reversing the additive
migration. Dependency/resource canaries and the persistent 24-hour audit remain
mandatory.

The normal selective path refuses unapplied migrations. It retains the mutable
work gate, complete authority snapshots, health/resource/dependency checks,
automatic component rollback, and approved-Post verification when Validation
changes. Provider and Pexels executions run when Validation or the platform
changes. Other releases use the quick dependency audit, which still checks all
service health, mounts, credential handoff digests, networks, routes, and skills
without spending up to 300 seconds on an unchanged Codex execution.

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
