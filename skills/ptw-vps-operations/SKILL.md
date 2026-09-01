---
name: ptw-vps-operations
description: Safely inspect, deploy, reset, verify, and troubleshoot PTW Result production across Commander, Validation, Owner Gateway, the independent platform bridge, PostgreSQL, Caddy, Pexels, Firebase Hosting, and the existing Telegram emergency and notification boundary.
---

# PTW Result VPS Operations

Operate `/root/ptw` and `/opt/ptw/platform` as unrelated histories and
databases. The structured bridge is their only generation integration. Never
move credentials between them or mutate platform data during a Commander reset.

## Start safely

1. Read the current-state and applicable operations documents. Inspect both
   worktrees, exact image tags, containers, memory/swap, disk, OOM evidence,
   database readiness, review-notification relay readiness, and emergency stop
   without printing environment values.
2. Use one locked serial SSH session. Build matching Linux/amd64 Commander,
   Validation, Owner Gateway, platform API, and platform worker images off-host
   with one versioned, non-`latest` tag. Render Compose before deployment and
   inspect every `tmpfs` mount.
3. Keep Pexels, Firebase, bridge, internal relay, and existing Telegram
   credentials root-owned. Never print, rotate, copy, or replace them.
4. Treat `scripts/reset_ptw.sh` as irreversible. Run it only after the owner
   provides exactly `RESET PTW PRODUCTION`, against its exact allowlist, while
   preserving independent-platform table counts.

## Owner-reviewed Result contract

- JSON modes are exactly `product_brief`, `product_brief_revision`, and
  `content_candidate_generation`. The optional non-human graphic mode is a
  separate media call. No evaluation, scoring, comparison, or selection mode
  exists.
- Initial and Regenerate-all runs perform exactly five isolated CandidateV2
  calls. Tune performs one call, replaces the selected slot, and carries the
  other four immutable Creative UUIDs unchanged.
- Server code validates schema, protected offer/CTA, language, claims, media
  authority, Studio recipe/render integrity, layout safety, and five distinct
  renders before any review notification. These checks are deterministic and
  never produce subjective scores or ranks.
- A successful run becomes `awaiting_review` with exactly five review Creative
  UUIDs. It does not create a final Result. The owner uses the authenticated web
  console to Approve, Regenerate all, or Tune one selected Creative with a
  3–2000 character comment.
- Parent review sets remain actionable until a child successfully reaches
  `awaiting_review`. A failed child action becomes failed and releases the
  parent for a new idempotent request. Stale or concurrent actions must be 409.
- Approval appends accepted HumanFeedback, WeightUpdate, outcome, Project rules,
  snapshot lineage, and unlocks only the approved Creative export. Regenerate
  all records five rejections and excludes Creative/document/render/media/
  provider identities. Tune records exact instruction and positive direction
  preference.
- Telegram sends one notification through Commander after persistence. It
  contains Project, platform, “five posts ready,” and an authenticated web deep
  link. Telegram accepts no review action; inbound commands remain only
  `/help`, `/status`, and `/stop`.
- Persist a delivery receipt before sending. Retry definite failures boundedly;
  never auto-repeat an ambiguous send. Delivery failure never hides or invalidates
  the web review set. Manual retry is authenticated and idempotent.

## Canaries and reset acceptance

Before a future rollout, update the unrelated platform bridge so it advertises
only the three JSON modes, then run real Product Brief/revision/CandidateV2
canaries and a non-persisting Pexels policy canary. Use an injected notifier for
tests. Do not claim live Telegram notification readiness until authorization,
help/routing, provider delivery, receipt persistence, restart recovery, and
definite/ambiguous failure paths pass end to end.

After an authorized clean reset require zero Projects, Briefs, sources, assets,
brand kits, recipes, renders, runs, Creatives, review actions, learning rules,
snapshots, receipts, outcomes, feedback, weights, attempts, invocations, and
graph rows. Require no retired evaluator tables or interfaces, independent
platform counts unchanged, database-backed readiness, current PWA cache, five
authenticated Creative assets, approved export integrity, and old paths 404.

Never reset without the exact phrase, use `latest`, build on the 1 GB VPS,
clear `/opt/ptw/platform`, add Telegram review commands, or claim readiness from
health checks alone.
