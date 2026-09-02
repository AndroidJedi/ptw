# PTW Product Brief pipeline

## Boundary

PTW starts with one owner idea and creates one Product Brief validation
hypothesis. It does not perform research, post generation, publishing,
campaigns, traffic, analytics, or optimization.

The initial request atomically creates a Project and permanent owner-idea
Source. It includes `uk` or `en`; the stored choice controls every Brief field
and participates in idempotency. The model receives only the idea, required
language, and canonical Product Brief skill snapshot. Server validation rejects
unsupported proof and requires one coherent hypothesis and honest offer.

A correction creates a complete immutable replacement with `supersedes`,
`derived_from`, `evaluates`, and `adjusts` lineage through HumanFeedback and
WeightUpdate UUID entities. Approval is append-only and requires the owner to
confirm that the promise and offer can be honored. It has no automatic handoff.

## Authority

PostgreSQL is complete production authority. Owner Gateway exposes authenticated
Project and Brief create/list/detail/correct/retry/approve operations. The only
schema baseline is `db/migrations/001_ptw_brief_v1.sql`.

Loopback uses the digest-verified append-only authority under
`.local/owner-briefs`. These records never become production evidence
automatically. Universal Studio is separate and persists below
`.local/studio-workspace`.
