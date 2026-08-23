---
name: ptw-vps-operations
description: Safely inspect, deploy, verify, and troubleshoot PTW v2 production across Commander, Marketing Positioning, Owner Gateway, Natal Hosting, the independent platform bridge, PostgreSQL, Caddy, and the existing Telegram bot boundary. Use for production releases, migrations, resets, service health, logs, restart recovery, or 1 GB resource audits.
---

# PTW v2 VPS Operations

Operate production as two unrelated systems: `/root/ptw` owns the
`ptw_commander` database and `/opt/ptw/platform` owns its independent database
and bridge. Never merge their histories, move credentials between them, or
modify platform data during a Commander reset.

## Start safely

1. Read `docs/architecture/commander-current-state.md` and the narrow operations
   route. Check `git status --short --branch` locally and on the VPS.
2. Use one locked serial SSH session. Record running containers, exact image
   tags, memory/swap, disk, previous/current boot OOM evidence, database
   readiness, and emergency-stop state before mutation.
3. Build Linux/amd64 images off-host. Load Commander, Marketing Positioning,
   and Owner Gateway one at a time. Require one matching, non-`latest` tag.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   supplies the exact phrase `RESET PTW PRODUCTION`. It may drop only
   `ptw_commander.public` and exact generated Landing output. It must snapshot
   and compare platform table counts and must not migrate, seed, truncate, or
   drop the platform database.

## Service and bridge contract

- Marketing Positioning is the independent `ptw-marketing-positioning` Compose
  project on local port 8093, sharing only the Commander database network and
  the established platform backend network.
- The active Positioning flow calls only `marketing_positioning_document` and
  `marketing_positioning_revision`; Landing retains
  `natal_landing_revision`. Retired Laval/Branding modes are absent, and the
  runtime must not call `marketing_positioning_research_plan`.
- Require a fresh schema-bound canary for every new mode before the reset. A
  canary may append a bridge job but must not create Positioning/Landing rows.
- Marketing Positioning uses the owner idea as its sole factual Source and
  marks unsupported market conclusions as assumptions. DataForSEO credentials,
  calls, and paid tasks are absent from the active flow.
- One global database guard serializes Positioning, Landing agent calls, and
  Codex Plan/Execute. Restart recovery marks interrupted attempts failed and
  releases only the owning service's orphaned guard.

## Telegram boundary

Reuse only the configured `@ptw_commander_bot` token and existing allowlisted
owner chat. Landing notifications use direct `sendMessage` after lead commit;
Positioning sends one direct terminal notification only after its generation
attempt is durably completed or failed. Do not create a bot, token, webhook,
poller, or worker. The established inbound
long poller exposes only `/help`, `/status`, and `/stop`; every other command
returns the web-console link and must not mutate state. Emergency stop allows
lead persistence but suppresses outbound notification until explicit retry.

## Cutover verification

After the clean baseline, require zero Positioning, Landing, and lead rows;
retired tables/routes/services absent; v2 graph tables present; Commander,
Positioning, and Owner Gateway database-backed readiness; restart persistence;
canonical skill mounts/links; active Natal placeholder; bumped Owner Console
service-worker cache; Auth/App Check/CORS/dependency audits; exact-owner browser
acceptance; and published-content parity. Send one clearly labelled direct bot
test without inserting a fake lead and without starting polling.

Run the 1 GB audit immediately and through one locked 24-hour follow-up. Fail on
new OOM evidence, unexpected processes/pollers, missing swap, unstable
readiness, or low memory boundaries documented by the current-state file.

Never print secrets, reset without the exact phrase, use `latest`, build on the
1 GB VPS, or claim a capability from health checks alone.
