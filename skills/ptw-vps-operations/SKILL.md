---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW Result production across Commander, Validation, Owner Gateway, the independent platform bridge, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency boundary.
---

# PTW Result VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. The structured bridge is their only application integration. Never
move credentials between them or mutate platform data during a Commander reset.

## Start safely

1. Read the current-state and operations documents. Inspect both worktrees,
   exact image tags, containers, memory/swap, disk, OOM evidence, database
   readiness, and emergency stop without printing environment values.
2. Use one locked serial SSH session. Build matching Linux/amd64 Commander,
   Validation, Owner Gateway, platform API, and platform worker images off-host
   with one versioned, non-`latest` tag.
   Render the production Compose configuration before deployment and inspect
   every `tmpfs` entry. A mount containing comma-separated options must be one
   quoted YAML list item (for example `"/tmp:size=64m,mode=1777"`); a flow-style
   list can split `mode=1777` into an invalid mount path.
3. Keep `PEXELS_API_KEY`, Firebase credentials, bridge tokens, and the existing
   Telegram bot token root-owned. Never print, rotate, or copy them into Git.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   provides exactly `RESET PTW PRODUCTION`. It may drop only
   `ptw_commander.public` and the obsolete explicit `ptw_owner-control` volume.
   It must snapshot and compare all independent platform table counts.
   When deleting the obsolete `ptw_owner-control` volume, remove only the exact
   stopped `ptw-owner-gateway-1` legacy container first; stopping a container
   does not release its Docker volume reference.

## Result service contract

- Validation is the separate `ptw-validation` Compose project on local port
  8093 and shares only the Commander database network and platform backend.
- JSON modes are exactly `product_brief`, `product_brief_revision`,
  `content_candidate_generation`, and `content_result_critic`. Media mode is
  exactly `content_non_human_graphic_generation`.
- Run strict-schema canaries for Product Brief, one isolated candidate, and one
  multimodal critic call. The critic accepts one to five explicitly mapped,
  digest-checked JPEGs, at most 1.5 MB each and 8 MB total, and cannot generate
  images. Its application-side canary mapping must match persisted previews
  exactly, including `mime_type`; use the real critic schema and domain
  validator rather than a generic marker response.
- JSON-only candidate and critic calls may receive one fresh retry within the
  original deadline. A non-human graphic call is single-shot and must never be
  retried after an ambiguous result.
- Run a non-persisting Pexels search/download/image-policy canary before reset.
  Require approved Project assets or Pexels real photography; synthetic people
  and faces remain forbidden.
- Production concurrency is at most two generator JSON calls and one critic
  multimodal call. A run permits five initial calls, four improvements, exactly
  three critic passes, one optional non-human graphic, and 45 minutes total.
- Bridge canaries append independent-platform job, session, and event rows. For
  an in-place application release, run the pre-cutover canary first, then
  snapshot Commander and platform table counts. Compare those snapshots after
  the application container cutover and restart but before the post-cutover
  canary. Never compare platform counts across canary rounds and misclassify
  expected canary bookkeeping as application data mutation. A failed
  preservation check must restore the prior matching application image tag.

## Clean reset acceptance

After reset require:

- exactly the single `001_ptw_result_v1.sql` migration;
- zero Projects, Briefs, sources, assets, brand kits, recipes, renders, runs,
  candidates, elements, critic passes, actions, Results, outcomes, feedback,
  weights, attempts, invocations, and graph rows;
- no Ads, batch, Landing, Positioning, idea, publication, campaign, job-control,
  or SQLite owner-control tables/volumes/containers;
- independent platform table counts unchanged;
- database-backed readiness for Commander and Validation plus Gateway health;
- canonical skills, exact Result-only route table, restarted services, current
  service-worker cache, authenticated Result image digest/ETag, and retired
  public/API paths returning 404.

Deploy the enforcing platform worker before the platform API, run bridge and
Pexels canaries before the irreversible reset, then deploy/reset Commander,
Validation, and Owner Gateway serially. Run the 1 GB audit immediately and
schedule its locked 24-hour follow-up. Fail on new OOM evidence, missing swap,
unexpected pollers/containers, unstable readiness, or less than 250 MiB idle
available memory.

Never reset without the exact phrase, use `latest`, build on the 1 GB VPS,
clear `/opt/ptw/platform` data, touch unrelated databases, or claim readiness
from health checks alone.
