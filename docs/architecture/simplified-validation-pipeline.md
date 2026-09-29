# PTW Product Brief pipeline

## Boundary

PTW begins with an owner-created empty Project and one owner idea that creates one
strict Product Brief validation hypothesis. The Brief request atomically creates
the permanent Source and queued Brief inside that Project. Language is part of
the immutable request and idempotency contract. New reservations also freeze an owner-selected marketing policy (Benefit-led
by default or Identity-led). The model receives the idea, language, selected
policy and canonical Product Brief skill; validation rejects unsupported
proof.

An owner may delete a Project only after typing its exact name. Deletion uses one
request UUID, refuses active generation or publishing, and writes an immutable
tombstone rather than erasing graph/audit lineage. Deleted Projects disappear
from every private workspace, all project-scoped routes fail closed, and their
public Landing routes return 404. Content already published to an external
provider is outside this local deletion boundary.

A correction creates a complete immutable replacement with `supersedes`,
`derived_from`, `evaluates`, and `adjusts` lineage through HumanFeedback
and WeightUpdate UUID entities. Weight history is append-only.

## Approval handoff

Approval requires the owner to confirm that the promise and offer are
honorable and to select one live common Studio template. The approval and first
creative reservation are transactional and idempotent. The API returns HTTP 202
with the creative, the browser opens its project-scoped Post progress screen,
and Studio composition starts in the background.

The Brief remains immutable. Studio records an explicit `derived_from` edge
from creative to approved Brief. A corrected Brief starts a separate creative;
an additional creative from one Brief requires the current creative to have an
immutable approved version.

## Authority

PostgreSQL is the complete production authority for active and deleted Projects, Sources, Briefs,
corrections, approvals, Studio creatives, skills, and graph lineage. The only
schema baseline is `db/migrations/001_ptw_brief_v1.sql` plus the private Landing
extension `db/migrations/002_ptw_landing_studio_v1.sql`; no earlier Studio, Post,
or legacy Landing state is migrated.

Loopback uses append-only metadata below `.local/owner-briefs` and
per-creative renderer state below `.local/studio-workspace/creatives` with the
same public workflow contract.

## Marketing approaches

New requests produce ProductBriefV2 with a compact `positioning` object:
marketing_approach, desired_identity (may be empty), customer_tension,
category_frame and functional_value. Each copy field is at most 200 characters;
the complete object is at most 1024 UTF-8 bytes. It is hypothesis context, never
proof or permission to invent capabilities. The Identity-led policy includes
conditional examples from the owner-supplied marketing transcript.

Create/correct endpoints accept optional `marketing_approach` (`benefit_led` or
`identity_led`). Creation defaults to Benefit-led; correction inherits the base
policy when unchanged. Changing approach creates a fresh unapproved replacement
through the same HumanFeedback/WeightUpdate lineage. It never activates a global
rule. Selection participates in request identity; retries preserve their policy.

Migration 020 adds nullable immutable `generation_settings` with the selected
policy text, version/digest and output schema version. Null identifies a V1
reservation, including failed/queued historical work. No old document or digest
is rewritten. Local append-only metadata enforces the same settings boundary.
V1 and V2 remain readable. Deploy compatible backend/readers and the additive
migration before the selector; rollback must retain V2 readers for new records.

Post, Landing, Manual Agent and image contexts inherit positioning from their
exact source Brief. Their read-only approach label cannot change independently.
Canonical policy references are versioned separately from reviewed Analytics
skills; no new inference call is introduced.

The [private generation trial](marketing-approaches-trial.md) records paired
examples, reproducible checks and editorial limitations without performance claims.
