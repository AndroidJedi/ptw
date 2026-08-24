---
name: ptw-vps-operations
description: Safely inspect, deploy, verify, and troubleshoot PTW Validation production across Commander, the Validation API, Owner Gateway, the independent platform bridge, PostgreSQL, Caddy, Pexels, and the existing Telegram emergency boundary. Use for releases, migrations, resets, service health, logs, restart recovery, or 1 GB resource audits.
---

# PTW Validation VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. The platform bridge is the one explicit integration. Never move
credentials between them or mutate platform data during a Commander reset.

## Start safely

1. Read the current-state document and narrow operations route. Check both
   worktrees, exact image tags, containers, memory/swap, disk, OOM evidence,
   database readiness, and emergency stop.
2. Use one locked serial SSH session. Build matching Linux/amd64 Commander,
   Validation, Owner Gateway, platform API, and platform worker images off-host
   with one non-`latest` tag.
3. Provision `PEXELS_API_KEY` only in the root-owned runtime environment. Never
   print, copy to Git, rotate casually, or embed it in an image.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run only after the owner gives
   the exact phrase `RESET PTW PRODUCTION`. It may drop only
   `ptw_commander.public`; it must snapshot and compare independent platform
   table counts.

## Service contract

- Validation is the independent `ptw-validation` Compose project on local port
  8093, sharing the Commander DB network and platform backend network.
- Active bridge modes are exactly `product_brief`, `product_brief_revision`,
  and `ad_creative_batch`. Require a fresh strict-schema canary for all three.
- Run a non-persisting Pexels search/download/render canary before reset.
- No SEO, DataForSEO, YouTube, market-research, Landing, publishing, traffic,
  campaign, UTM, analytics, or AI-image provider is active.
- One database guard serializes Brief, creative-batch, and Codex Plan/Execute
  work. Restart recovery releases only the owning operation.

## Cutover verification

After the clean baseline require zero Product Brief, batch, creative, asset,
feedback, and relationship rows; legacy Positioning/Landing tables and
containers absent; platform counts unchanged; database-backed readiness;
restart persistence; canonical skill links; Landing placeholder; service-worker
cache bump; exact-owner Stage 1–2 browser acceptance; Pexels attribution and
ETags; and retired APIs returning 404.

Run the 1 GB audit immediately and through one locked 24-hour follow-up. Fail
on new OOM evidence, unexpected processes/pollers, missing swap, unstable
readiness, or documented low-memory boundaries.

Never print secrets, reset without the exact phrase, use `latest`, build on the
1 GB VPS, or claim a capability from health checks alone.
