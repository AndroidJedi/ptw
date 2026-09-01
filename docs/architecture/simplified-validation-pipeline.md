# PTW Product Brief pipeline

## Boundary

PTW starts with one owner idea and creates one Product Brief validation
hypothesis. It does not perform research, SEO, evidence synthesis, Landing
generation, publishing, campaigns, traffic, UTMs, analytics, or optimization.

The initial Brief atomically creates a Project and permanent owner-idea Source.
The create request must include the active Owner Console language, `uk` or
`en`; that choice is stored in Source metadata and participates in the
idempotency identity. Reusing a request ID with another language conflicts.
The stored choice, not the script used in the raw idea or a later UI toggle,
controls the Product Brief and all later Results. Corrections and retries
inherit it. Legacy Sources without the metadata use their completed base Brief
language, then raw-idea inference only while an initial Brief is still queued.
The model receives only that idea, the authoritative required language, and the
Product Brief skill snapshot. The server validates every Brief field, first
customer, pain, promise, benefits, trust strategy, exact offer, and exact CTA
before immutable persistence.

A correction or retry creates a complete new Brief UUID with explicit
`supersedes` and `derived_from` edges. Approval is an append-only record and
requires the owner to confirm that the offer and promise can be honored.
Approval does not automatically generate content; it opens the one-click
Social post action.

## Result handoff

A Result run may read only:

- the selected approved Product Brief;
- one fixed server-owned Instagram or TikTok task persisted as a permanent Project Source;
- the automatically provisioned canonical Natal brand-kit revision;
- explicitly approved Project assets and stock-photo source metadata;
- versioned templates, bounded writing references, tool contracts, and skill
  digests.

Instagram and TikTok candidate prompts additionally contain the complete
versioned `post-copy-style` reference. Its Git-pinned Natal, Sesh,
OpenForCoffee, and SoberWins excerpts teach structure and rhythm only; they
cannot supply Project facts, claims, metrics, brand, offer, CTA, or source
authority. The reference maps observable hooks, mechanism headlines,
supporting reassurance, and friction-to-action captions. Alt text remains a
factual description of the resolved render.

Raw idea text, research, unsupplied previous outputs, and performance data are
excluded. Result generation may consume only the immutable active Project
learning snapshot created by explicit owner review. The exact Brief offer and
CTA are protected throughout generation and rendering.
The approved Brief language is passed explicitly to every candidate call.
Before persistence, the server requires the combined hook, headline, body,
offer, CTA, caption, and alt text to be dominant in that language; Latin brand
names remain valid. Wrong-language output fails before Creative persistence.

## Authority and API

PostgreSQL entities and relationships are complete authority. Owner Gateway
exposes authenticated Project and Product Brief create/list/detail/correct/
retry/approve operations and proxies bounded Instagram/TikTok photo-post creation after
approval. It does not expose task/profile, Project-asset, or brand-kit setup
surfaces. Empty production state is valid; no samples or fake proof are seeded.

The only schema baseline is `db/migrations/001_ptw_result_v1.sql`. There are no
batch, Ad Creative, Landing, Positioning, idea, publication, campaign, lead,
job-control, or compatibility tables.

The loopback app is an explicit local exception to the production persistence
boundary. Its mutable Product Brief and Instagram-square owner-review workflow
uses the digest-verified append-only authority under
`.local/owner-experiments`, while `.local/studio-workspace` remains the saved
Universal Studio authority. Local run creation accepts only request ID,
approved Brief ID, fixed `instagram`, and the saved Studio state digest; the
server resolves the task, five strategies, approved Project assets, skill
contexts, and active owner-approved lesson snapshot. These files never become
production evidence automatically, and the local workflow performs no
publishing, traffic, analytics, or market-performance ingestion.
