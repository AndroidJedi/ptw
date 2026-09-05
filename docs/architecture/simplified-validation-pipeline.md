# PTW Product Brief pipeline

## Boundary

PTW begins with one owner idea and creates one strict Product Brief validation
hypothesis. The initial request atomically creates a Project, permanent Source,
and queued Brief. Language is part of the immutable request and idempotency
contract. The model receives only the idea, language, and canonical Product
Brief skill; validation rejects unsupported proof.

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

PostgreSQL is the complete production authority for Projects, Sources, Briefs,
corrections, approvals, Studio creatives, skills, and graph lineage. The only
schema baseline is `db/migrations/001_ptw_brief_v1.sql` plus the private Landing
extension `db/migrations/002_ptw_landing_studio_v1.sql`; no earlier Studio, Post,
or legacy Landing state is migrated.

Loopback uses append-only metadata below `.local/owner-briefs` and
per-creative renderer state below `.local/studio-workspace/creatives` with the
same public workflow contract.
