---
name: legacy-social-automation-recovery
description: Recover PTW's preserved but inactive Meta Ads API or TikTok publishing implementation only after an explicit owner request, without losing historical graph data or weakening the current manual Instagram validation boundary.
---

# Legacy Social Automation Recovery

Use this skill only when the owner explicitly asks to restore Meta Ads API
automation or TikTok publishing. The normal PTW product is Instagram-only:
organic Instagram may publish directly, paid tests are launched manually in
Meta Ads Manager, and paid metrics enter through reviewed CSV import.

Read [references/preserved-surfaces.md](references/preserved-surfaces.md) before
changing code. Treat preserved modules and database tables as recovery material,
not feature flags.

## Recovery boundary

- Start from the active manual Instagram validation contract and state exactly
  which provider, routes, UI, jobs, credentials, and app-review obligations the
  owner requested to restore.
- Do not restore both Meta Ads and TikTok when only one was requested.
- Never drop, rewrite, or backfill historical provider rows merely to make a
  current API response convenient. PostgreSQL entities and lineage edges remain
  authoritative and append-only where their tables require it.
- Do not expose or copy tokens. Inspect secret files only by owner-authorized,
  token-safe metadata and use the existing hidden-prompt configurators.
- Do not deploy or touch a remote runtime unless the owner separately authorizes
  that target and action.

## Required implementation sequence

1. Read the current social publishing, manual Instagram validation, analytics,
   migration, and gateway route documentation. Inspect Git history for the last
   verified implementation; do not assume the preserved module is still
   compatible with current schemas.
2. Restore the smallest provider-specific dependency graph. Keep export/source
   reads independent from remote provider readiness.
3. Reintroduce private Validation routes, authenticated Owner Gateway parity,
   bounded UI, runtime recovery, and provider jobs together. A partially exposed
   route or UI is not a recovered feature.
4. Preserve exact approved Post and published Landing lineage, idempotency,
   pre-side-effect mutation markers, uncertain-outcome handling, and explicit
   owner confirmation for external changes.
5. Keep the current manual Instagram test path available unless the owner
   explicitly replaces it. Never silently migrate its active or completed tests
   into provider-managed campaigns.
6. Add contract tests proving inactive providers remain absent when recovery is
   disabled and the requested provider is complete when enabled.

## Acceptance

For Meta Ads, require app-review/readiness evidence, exact PAUSED object
readback, per-Ad tracked Landing URLs, one Campaign → one Ad Set → reviewed Ads,
and no automatic activation or winner declaration.

For TikTok, require OAuth/account pinning, current creator-option review,
visibility and commercial-content consent, durable commit-start markers, bounded
media delivery, restart reconciliation, and an explicit user-facing failure
path. A health check alone is never acceptance.

Run the narrow provider tests, Owner Gateway route parity/security tests, web
tests and production build, the full Commander suite required by `AGENTS.md`,
`python3 scripts/verify_ptw_skills.py`, and `git diff --check`. Update
`docs/architecture/commander-current-state.md` with the exact recovered scope
and verification evidence.
