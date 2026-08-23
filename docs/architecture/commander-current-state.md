# Commander current state

Updated: 2026-08-23
Branch: `codex/web-only-commander` (one preserved commit ahead of its tracked
remote and zero commits behind after fetch)

## Last completed milestone

PTW v2 is implemented locally as Marketing Positioning, Landing, Ads, and a
compact Admin workspace. The implementation includes the clean PostgreSQL v1
baseline, isolated `marketing-positioning-api`, strict research and document
contracts, immutable revisions and evidence lineage, explicit approval gating,
three eight-block Natal templates, exact-snapshot publication, public leads and
direct existing-bot notification attempts, a truthful read-only Ads stub, the
four-workspace Owner UI, canonical skills, cutover scripts, and the clean Natal
placeholder.

The confirmation-gated reset drops only `ptw_commander.public`, clears only the
allowlisted generated Landing targets, verifies clean v2 counts, and proves that
the independent platform database counts are unchanged. It requires the exact
`RESET PTW PRODUCTION` phrase, a matching non-`latest` release tag, one serial
lock, and three preloaded Linux/amd64 images.

## Verification completed in this workspace

- Disposable PostgreSQL 16 baseline/reset/reapply passed with 26 v2 tables,
  immutable-history triggers, zero legacy tables, and unchanged platform
  fixture count.
- Repository integration: 3 passed, covering durable Positioning retry/cost
  reuse, approval supersession, graph/feedback lineage, all Landing templates,
  scoped edit and publication, lead validation/rate limiting, and notification
  attempts.
- Built-image suites: Commander/Natal 7, Marketing Positioning 10, Owner Gateway
  22; all passed in final Linux/amd64 images, including exact root/build-path
  publication parity and prior-build preservation.
- Web: Vitest 10, production TypeScript/Vite build, and 6 Playwright journeys
  passed on desktop Chromium, 360 px Chromium, and iPhone WebKit.
- The canonical skill/link verifier and skill-creator validator passed. Python
  compilation, Compose parsing, shell syntax, demo, and `git diff --check`
  passed.
- Final local release archives and checksums are under
  `.local/ptw-v2-release-final5/` with tag `v2-local-verify-final5`; application
  imports and integration tests also pass against the code baked into those
  images rather than relying on workspace module resolution.

## Next work

Production and Firebase have not been changed. The owner must explicitly supply
`RESET PTW PRODUCTION` before the irreversible serial cutover may run. The
independent platform bridge update is prepared in its own worktree and the
publisher now deploys its two prebuilt images under the same serial lock,
requiring fresh schema-bound canaries for all four retained/new modes before
reset. After cutover, complete exact-owner acceptance, the clearly labelled
direct bot canary, restart and resource checks, then the locked 24-hour 1 GB
follow-up audit.
