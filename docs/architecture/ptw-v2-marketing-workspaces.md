# PTW v2 marketing workspaces

Status: deployed; owner-input-only Positioning correction in progress
Updated: 2026-08-23

## Product flow

Marketing Positioning accepts raw idea, country, market language, output
language (`uk`/`en`), and request UUID. It performs strict owner-input-only
synthesis, then waits for owner approval. Country and market language are
context, not evidence; unsupported market conclusions are explicit assumptions.
Landing and Ads can read only the active approved revision. Landing creates
three private Natal variants and publishes exactly one selected snapshot. Ads
exposes the two document concepts without generation or publishing endpoints.

Admin contains Jobs, Docs/System, and break-glass Terminal. Retired UI queries
redirect to Positioning; retired APIs are not registered and return 404.

## Clean baseline

`db/migrations/001_ptw_marketing_v1.sql` is the clean reset baseline;
`002_positioning_notifications.sql` adds the post-cutover terminal-notification
table to existing deployments. They define generic graph/source/feedback/weights/audit and
Plan/Execute tables, the singleton global heavy-operation guard, Positioning
projects/revisions/attempts/provider history/approvals/lessons/terminal
notification attempts,
Landing draft sets/snapshots/edits/builds/publications/lessons, and Landing
leads/notification attempts.

UUIDv7 identifies every domain/graph record. Requests are UUID-idempotent.
Documents, snapshots, and artifacts have deterministic SHA-256 digests.
Revisions/snapshots are append-only; failures remain durable. There are no ad,
post, campaign, image, or publishing tables for Ads.

## Lineage

- The owner idea is the permanent factual `Source` for active Positioning.
- A Positioning revision `derived_from` that exact owner idea. Unsupported
  market conclusions carry no Source UUID and are marked as assumptions.
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

The active Positioning bridge modes are:

- `marketing_positioning_document`
- `marketing_positioning_revision`

Landing retains `natal_landing_revision`. The active Positioning runtime does
not call the legacy research-plan mode or any external research provider.
Deployment requires fresh strict-schema canaries for the active document,
revision, and Landing modes. One database guard serializes Positioning, Landing
agent calls, and Codex Plan/Execute.

## Public APIs

Positioning exposes create/list/detail, complete correction revision, retry,
approval, Markdown export, and bounded lesson proposals. Landing exposes draft
creation/detail/retry, authenticated previews, scoped edit/retry, exact-snapshot
publish, builds, feedback, leads, notification retry, and lesson proposals.
Public `POST /api/v1/public/landings/{build_id}/leads` is the only unauthenticated
domain mutation. Ads has one authenticated GET endpoint.
