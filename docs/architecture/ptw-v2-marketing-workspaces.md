# PTW v2 marketing workspaces

Status: implemented locally; production reset/cutover awaiting exact owner confirmation
Updated: 2026-08-23

## Product flow

Marketing Positioning accepts raw idea, country, research language, output
language (`uk`/`en`), and request UUID. It performs bounded live research and
strict synthesis, then waits for owner approval. Landing and Ads can read only
the active approved revision. Landing creates three private Natal variants and
publishes exactly one selected snapshot. Ads exposes the two document concepts
without generation or publishing endpoints.

Admin contains Jobs, Docs/System, and break-glass Terminal. Retired UI queries
redirect to Positioning; retired APIs are not registered and return 404.

## Clean baseline

`db/migrations/001_ptw_marketing_v1.sql` is the only domain migration after the
cutover reset. It defines generic graph/source/feedback/weights/audit and
Plan/Execute tables, the singleton global heavy-operation guard, Positioning
projects/revisions/attempts/provider invocations/costs/approvals/lessons,
Landing draft sets/snapshots/edits/builds/publications/lessons, and Landing
leads/notification attempts.

UUIDv7 identifies every domain/graph record. Requests are UUID-idempotent.
Documents, snapshots, and artifacts have deterministic SHA-256 digests.
Revisions/snapshots are append-only; failures remain durable. There are no ad,
post, campaign, image, or publishing tables for Ads.

## Lineage

- Owner idea and every selected research finding are permanent `Source`
  entities.
- A Positioning revision `derived_from` all allowed cited sources.
- Feedback `evaluates` its exact base; a replacement `supersedes` the base and
  `derived_from` feedback. Zero-delta WeightUpdate `adjusts` that feedback.
- A Landing draft set derives from the exact approved Positioning revision;
  snapshots are contained and supersede their parent history.
- A published Landing derives from its exact snapshot and Positioning revision.
- A lead `submitted_to` the exact published build.

## Services and bridge

Marketing Positioning is a separate `ptw-marketing-positioning` Compose
project, exposed on loopback port 8093 for continuity. It joins the Commander
database network and independent platform backend only. Owner Gateway proxies
owner-authenticated public endpoints.

The PTW bridge allowlist is exactly:

- `marketing_positioning_research_plan`
- `marketing_positioning_document`
- `marketing_positioning_revision`
- retained `natal_landing_revision`

The first three appear under `marketing_positioning_modes`; the last is the
only `landing_modes` value. Deployment requires a fresh strict-schema canary
for each. One database guard serializes Positioning, Landing agent calls, and
Codex Plan/Execute.

## Public APIs

Positioning exposes create/list/detail, complete correction revision, retry,
approval, Markdown export, and bounded lesson proposals. Landing exposes draft
creation/detail/retry, authenticated previews, scoped edit/retry, exact-snapshot
publish, builds, feedback, leads, notification retry, and lesson proposals.
Public `POST /api/v1/public/landings/{build_id}/leads` is the only unauthenticated
domain mutation. Ads has one authenticated GET endpoint.
