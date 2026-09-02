---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW production across Commander, Product Brief Validation, Owner Gateway, Universal Studio, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency boundary.
---

# PTW VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. The structured bridge is their only generation integration. Never
move credentials between them or mutate platform data during a Commander reset.

## Start safely

1. Read current state and the applicable operations route. Inspect both
   worktrees, exact image tags, containers, memory/swap, disk, database
   readiness, bridge readiness, and emergency stop without printing secrets.
2. Use one locked serial SSH session. Build matching Linux/amd64 Commander,
   Validation, Owner Gateway, platform API, and platform worker images off-host
   with one versioned non-`latest` tag. Render Compose before deployment.
3. Keep Pexels, Firebase, bridge, and existing Telegram credentials root-owned.
   Never print, rotate, copy, or replace them.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   provides exactly `RESET PTW PRODUCTION`, against its exact allowlist, while
   preserving independent-platform table counts.

## Production contract

- Bridge JSON modes are exactly `product_brief` and
  `product_brief_revision`; media generation modes are absent.
- PostgreSQL owns Projects, Sources, Product Briefs, correction feedback and
  weights, attempts, invocations, audit, graph lineage, and emergency control.
- Universal Studio has its own bounded workspace and deterministic renderer;
  it does not create PostgreSQL content-run, Creative, recipe, render, review,
  learning, export, or notification entities.
- Telegram accepts only `/help`, `/status`, and `/stop`. Normal work remains in
  the web console.

## Canaries and reset acceptance

Before rollout, update the unrelated platform bridge to the two-mode contract,
then run real Product Brief and revision canaries plus a non-persisting Pexels
Studio canary. After an authorized clean reset require zero Projects, Briefs,
Sources, feedback, weights, attempts, invocations, and graph rows; require the
single `001_ptw_brief_v1.sql` migration, no retired Result tables or routes,
independent platform counts unchanged, database-backed readiness, and the
current PWA cache.

Never reset without the exact phrase, use `latest`, build on the 1 GB VPS,
clear `/opt/ptw/platform`, add Telegram work commands, or claim readiness from
health checks alone.
