---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW production across Commander, Product Brief Validation, Owner Gateway, project-scoped Studio, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency boundary.
---

# PTW VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. Their authenticated structured/media bridge is the only generation
integration. Never move credentials between them or mutate platform data during
a Commander reset.

For ChatGPT/Codex authorization diagnosis, auth-only recovery, and promotion
into a complete compatible release, read
[references/codex-auth-production.md](references/codex-auth-production.md).

## Start safely

1. Read current state and the applicable operations route. Inspect both
   worktrees, exact image tags, containers, memory/swap, disk, database,
   bridge, Firebase, Pexels, and emergency-stop readiness without printing
   secrets.
2. Use one locked serial SSH session. Build matching Linux/amd64 Commander,
   Validation, Owner Gateway, platform API, and platform worker images off-host
   with one versioned non-`latest` tag. Render Compose before deployment.
   Compare the image of every running public service before and after cutover;
   never update the Gateway independently of its Validation and platform API/
   worker release, because an otherwise healthy proxy can forward into a
   retired route contract.
3. Keep Pexels, Firebase, bridge, and Telegram credentials root-owned. Never
   print, rotate, copy, or replace them.
   Keep `codex-auth` private on the backend network but also attach it to the
   outbound-capable edge network; device authorization and its required working
   test both need egress.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   separately authorizes deployment and provides exactly
   `RESET PTW PRODUCTION`.
5. Treat `__pycache__`, `.pyc`, and `.pyo` below the mounted skill tree as
   generated runtime artifacts, not canonical skill content. Skill verification
   ignores them; run skill-hosted Python with `PYTHONDONTWRITEBYTECODE=1` where
   practical so a read-only audit does not create permission-noisy artifacts.

## Production contract

- Bridge JSON modes are exactly `product_brief`,
  `product_brief_revision`, `studio_creative_generation`, and
  `studio_edit_learning`.
- Media mode is exactly `content_non_human_graphic_generation`; enhancement
  accepts zero or one validated square PNG reference and records its digest.
- PostgreSQL owns Projects, Sources, Briefs, corrections, approvals,
  project-scoped Studio creatives/files/assets/versions, append-only
  generation and learning runs, immutable edit checkpoints and skill snapshots,
  proposals/decisions, audit, graph lineage, and emergency control.
- Brief approval transactionally reserves the first creative. Restart recovery
  resumes queued composition, phone-image, and learning stages idempotently.
- Bare Studio mutation routes, `/api/v1/posts`, candidate/critic modes,
  historical schema adapters, and singleton assignment flows are absent.
- Telegram accepts only `/help`, `/status`, and `/stop`.

## Canaries and reset acceptance

Before rollout, run real canaries for all four JSON modes, fresh image
generation, one-image enhancement, and Pexels. After an authorized clean reset
require zero Projects, Briefs, creatives, assets, versions, checkpoints,
generation/learning runs, proposals, decisions, skill snapshots, graph rows,
and every Landing workspace/file/asset/run/version/checkpoint/skill/proposal row.
Require `001_ptw_brief_v1.sql` and `002_ptw_landing_studio_v1.sql`, no retired Result/Post or legacy Landing tables/routes,
unchanged independent platform data, database-backed readiness, and the current
PWA cache.

After cutover exercise create Project/Brief → approve with template → automatic
creative composition/phone image → edit → Save learning → global decision →
Approve creative, then restart services and verify the same IDs/digests plus
empty recovery queues. Never claim readiness from health checks alone.
