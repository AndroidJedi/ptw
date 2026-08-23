---
name: ptw-owner-console-incident
description: Diagnose, fix, deploy, and prevent PTW v2 Owner Console incidents across Firebase Auth/App Check/Hosting/PWA caching, Marketing Positioning, Landing drafts/publication/leads, Ads stub, Admin, Commander, the platform bridge, and the existing Telegram bot. Use when a workspace fails, stale UI is served, readiness regresses, a lead notification fails, or an old route reappears.
---

# PTW v2 Owner Console Incident

Start from the public symptom, then trace browser → Hosting/Caddy → Owner
Gateway → exact dependency → PostgreSQL. A healthy gateway does not prove that
Marketing Positioning, the structured bridge, Firebase publication, or
Telegram delivery is ready.

## Public boundary

Verify the active document, hashed entry/App bundles, bumped service-worker
cache, Auth helper bypass, Firebase Auth persistence, App Check header/site key,
CORS from the exact Owner and Landing origins, and unauthenticated rejection.
The primary navigation must be Marketing Positioning, Landing, Ads, Admin. Old
page queries redirect to Positioning; old domain APIs return 404.

## Workspace checks

- Positioning: verify port 8093, shared Commander DB, verified DataForSEO,
  authenticated bridge capabilities, all three exact Positioning modes,
  source UUID evidence, durable attempts/costs, and global guard state.
- Landing: verify active-approved revision gating, all three snapshots, eight
  blocks, protected proof/privacy/form data, inert private previews, exact
  snapshot/digest publication, and no agent call during publish.
- Leads: inspect exact published build/form allowlist, HMAC IP rate limit,
  dedupe, committed lead row and `submitted_to` edge before notification, then
  append-only sent/failed/ambiguous/suppressed attempts. Never retain raw IPs.
- Ads: it may only show an approved revision and its two concepts with the
  explicit unimplemented message. Any generation/publish mutation is a defect.
- Admin: Jobs, Docs/System, and break-glass terminal remain owner-authenticated;
  destructive actions retain their exact confirmation gates.

## Telegram and failure handling

Use only the existing bot and allowlisted chat. There is one direct
`sendMessage` notification path and no new webhook/poller/worker. Escape all
visitor text. A Telegram failure must not reject or erase a lead. Ambiguous
timeouts remain ambiguous; do not auto-retry. Emergency stop records a
suppressed attempt, and only an explicit owner action retries it. Inbound bot
commands remain `/help`, `/status`, and `/stop` only.

## Release acceptance

Before streaming release images, render the Commander Compose configuration
with the platform, Commander, and Owner Gateway env files in that order. Resolve
`LANDING_TRUSTED_PROXY_NETWORKS` from the exact live Caddy-to-Owner Docker
network subnet; never use a broad private-network range. A missing interpolation
value must fail before bridge replacement or reset.

Check lifecycle flags against the production Compose CLI before cutover.
Production `docker compose run` does not accept `--no-build`; rely on the
code-owned `pull_policy: never` plus preloaded exact image tags for one-off
canary and migration containers. Keep `--no-build` on supported `up` commands.

Before reset, require a persistent random `LANDING_LEAD_HMAC_SECRET` of at
least 32 bytes in the root-owned Owner Gateway env. Generate it once without
printing it; never use the example placeholder or rotate it during routine
deployments, because stable HMACs are required for bounded IP rate limiting.

Retired-container audits must use anchored full Compose container names. Never
match the bare substring `commander-worker`: the independent, required platform
bridge worker legitimately contains that substring.

Run `scripts/audit_vps_owner_dependencies.sh` on the VPS and
`scripts/audit_live_owner_console.py` against public Hosting. Then perform the
authenticated exact-owner journey: empty state, Positioning creation/source
review/correction/approval, three Landing variants and one block edit,
publication fixture and real form, lead history, Ads stub, and Admin. Check
desktop, 360 px Chromium, and iPhone WebKit. Verify restart persistence,
retired-route absence, skill links, dependency/module audit, and no OOM.

Do not resolve an incident by bypassing evidence validation, approval gating,
App Check, fixed forms, source lineage, exact-snapshot publication, the global
guard, or the existing-bot/no-poller boundary.
