# PTW Product Brief pipeline

## Boundary

PTW starts with one owner idea and creates one Product Brief validation
hypothesis. It does not perform research, SEO, evidence synthesis, Landing
generation, publishing, campaigns, traffic, UTMs, analytics, or optimization.

The initial Brief atomically creates a Project and permanent owner-idea Source.
The model receives only that idea and the Product Brief skill snapshot. The
server validates language, first customer, pain, promise, benefits, trust
strategy, exact offer, and exact CTA before immutable persistence.

A correction or retry creates a complete new Brief UUID with explicit
`supersedes` and `derived_from` edges. Approval is an append-only record and
requires the owner to confirm that the offer and promise can be honored.
Approval does not automatically generate content; it opens the one-click
Instagram post action.

## Result handoff

A Result run may read only:

- the selected approved Product Brief;
- one fixed server-owned Instagram task persisted as a permanent Project Source;
- the automatically provisioned canonical Natal brand-kit revision;
- explicitly approved Project assets and stock-photo source metadata;
- versioned templates, bounded writing references, tool contracts, and skill
  digests.

Raw idea text, research, previous outputs, owner history, and performance data
are excluded. The exact Brief offer and CTA are protected values throughout
generation, recomposition, rendering, and final selection.

## Authority and API

PostgreSQL entities and relationships are complete authority. Owner Gateway
exposes authenticated Project and Product Brief create/list/detail/correct/
retry/approve operations and proxies one-click Instagram creation after
approval. It does not expose task/profile, Project-asset, or brand-kit setup
surfaces. Empty production state is valid; no samples or fake proof are seeded.

The only schema baseline is `db/migrations/001_ptw_result_v1.sql`. There are no
batch, Ad Creative, Landing, Positioning, idea, publication, campaign, lead,
job-control, or compatibility tables.
