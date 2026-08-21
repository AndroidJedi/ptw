# Branding v1

Status: implemented, production acceptance pending
Updated: 2026-08-21

Branding is the evidence-preserving stage between a completed Idea Laval case
and future visual-post generation. It is hosted by the Idea process and uses
the same serialized heavy-operation guard as Laval and Codex; there is no new
container and the retired creative worker remains disabled.

## Durable workflow

`branding_v1` has one fixed topology:

1. `CASE_SNAPSHOT`
2. `REFERENCE_PLAN`
3. `REFERENCE_COLLECTION`
4. `DESIGN_PRINCIPLES`
5. `BRAND_BRIEF`
6. `DIRECTION_SYNTHESIS`
7. `DIRECTION_EVALUATION`
8. `LOGO_GENERATION`
9. `OWNER_REVIEW`
10. `KIT_ASSEMBLY`

Creation snapshots the original idea, every assessed thesis with its verdict,
mechanisms, selected competitors, evidence, and permanent Commander UUIDs.
A completed live case remains selectable when no thesis survived; the owner UI
states that Branding will use the original idea, mechanisms, and evidence.
Validation and estimate state are not prerequisites. Stage input hashes, attempts,
provider/model, bounded errors, artifacts, provider tasks, action history, and
cost rows are durable PostgreSQL projections. Completed provider tasks cache
their structured response or immutable logo digest. A process restart reuses
completed work and never resubmits an unknown image request; an owner-authorized
pre-review rerun is required for an unknown result.

The runner automatically reaches `OWNER_REVIEW`. Exactly three independently
evaluated directions and three symbol logos are required. A non-empty comment
is a change request, not an approval: it immediately queues a durable revision
of that same logo, keeps the owner on that logo, and replaces the review target
only after the new immutable Creative is ready. An empty comment is the explicit
approval action. Kit assembly is blocked until all three current logo Creatives
have explicit approvals and the owner chooses one direction.

## Research boundary

Branding never calls DataForSEO or another SEO provider. It reuses the Idea
case's permanent Sources, then permits at most five selected competitor sites,
twelve official YouTube videos with twenty top-level comments each, ten owner
reference URLs, and five owner transcripts of at most 10,000 characters.
Transcripts are unverified owner Sources and are optional. Caption scraping is
forbidden.

The public-page collector accepts HTTPS on port 443 only, rejects credentials
and private/special DNS results, revalidates every redirect, streams bounded
content, and limits bytes and time. It extracts bounded DOM, CSS, metadata, and
public-image signals. Derived principles describe differentiation and reusable
mechanisms; competitor files and trade dress are never copied.

Hype and retention are represented only as truthful value moments, progress,
proof, anticipation, return cues, and social energy. Fake scarcity, urgency,
testimonials, and unsupported metrics fail validation. Naming performs a
bounded similarity screen against competitors and PTW names; every owner view
and kit warns that domain and trademark clearance remain undone.

## Directions, graph, and review

The language provider generates twelve internal name candidates and converges
to one exact, untranslated name for each direction. Code validates evidence
lineage, competitor distinctiveness, Ukrainian/Latin font coverage, light/dark
WCAG AA text contrast, truthful claims, and case fit independently. No
aggregate probability or success estimate is published.

Each direction becomes a generic `brand_direction` entity, derived from its
Idea hypotheses and permanent Sources. Reusable `creative_component` entities
and one logo `creative` are connected through `contains`; immutable artifact
files are connected through `generated`. Owner Gateway resolves the Creative
UUID and artifact digest from the selected direction, so the browser never
chooses graph identities. A change request appends text feedback and zero-delta
WeightUpdates without inventing a numeric rating, then creates a new Creative
that `supersedes` the previous Creative and is `derived_from` the exact feedback.
The replaced Creative and Artifact remain readable. Revision rows persist the
input hash, attempt, provider/model, source and result identities, bounded error,
and immutable asset path. Restart recovery reuses the same completed provider
task; a failed revision requires one explicit retry and a fresh attempt key.
Approval is a distinct append-only `owner_logo_approval` feedback entity on the
current Creative. The legacy annotated/rated contract remains readable and is
treated as a change request until its correction is regenerated and approved.

Approval creates an immutable `brand_kit` and an `adopted_as` edge. A later kit
for the same Idea supersedes the earlier kit without deletion. Material Idea
changes mark every associated kit stale. Retired Posts APIs remain HTTP 410;
the retained batch contract accepts only an active approved non-stale
`brand_kit_id`, while historical rows remain nullable and readable.

## Images and kit

The live provider reuses PTW's existing ChatGPT-authenticated Codex bridge for
all strict text stages and makes exactly one built-in `$imagegen` text-free
symbol call per direction. The bridge requires `gpt-image-2`, writes the raw
result immutably into the existing Commander asset volume, returns only bounded
digest/provenance metadata, and deletes its temporary session image directory.
Idea verifies and normalizes the symbol to 1024 px. Exact wordmarks, light/dark
variants, favicon, and app icon are deterministic Pillow renders using the
selected bundled font. Included Codex usage is recorded without inventing a USD
cost.

React source is emitted only from code-owned templates. The model supplies a
validated design manifest, never executable code. The ZIP contract is defined
in [`branding-kit-component-manifest.md`](branding-kit-component-manifest.md).
The pinned catalog vendors Inter, Manrope, Montserrat, IBM Plex Sans, IBM Plex
Serif, and IBM Plex Mono binaries plus their complete OFL license files at a
fixed upstream revision. Runtime and tests verify every checksum.
Catalog upgrades are reviewed against the upstream
[Inter metadata](https://github.com/google/fonts/blob/main/ofl/inter/METADATA.pb),
[Manrope font log](https://github.com/google/fonts/blob/main/ofl/manrope/FONTLOG.txt),
[Montserrat metadata](https://github.com/google/fonts/blob/main/ofl/montserrat/METADATA.pb),
and [IBM Plex repository](https://github.com/IBM/plex).

## Owner and API boundary

The five-item responsive navigation is Overview, Ideas, Branding, Jobs, and
More. `/api/v1/branding` provides readiness, eligible cases, run lifecycle,
stages, directions, review/history, approval, kit metadata, authenticated
assets, and ZIP download. Asset responses are private and `no-store`.
Candidate cards show readable case content and kit state; UUIDs stay internal.
Ukrainian is the default UI/sample language and the naming-clearance disclosure
is English as well. Review is a sequential one-logo wizard with one primary CTA
per state. Typing changes that CTA to **Переробити за коментарем**; leaving the
field empty makes it **Схвалити й далі**. Regeneration visibly stays on the same
logo and the new version appears automatically. It fetches only the active logo;
stage/provider/cost inspection, history, and deliberate rerun are collapsed
outside the primary path.

Production acceptance requires one real completed live Idea case, three current
logo approvals, an approved/downloaded kit, fixture compilation, graph-edge audit,
one-service restart persistence, and the established 1 GB memory audit.

Production does not require a second OpenAI API key. It uses the established
Codex ChatGPT authentication already mounted read-only into the independent
platform worker. `scripts/configure_brand_provider.sh` is now a non-mutating
compatibility audit: it verifies the exact Branding modes, image model, asset
transport, and selectable-case contract through
`PTW_REQUIRE_BRANDING_READY=1`.
