# PTW Product Brief pipeline

## Boundary

PTW begins with an owner-created empty Project and one owner idea that creates one
strict Product Brief validation hypothesis. The Brief request atomically creates
the permanent Source and queued Brief inside that Project. Language is part of
the immutable request and idempotency contract. New reservations also freeze an owner-selected marketing policy (Benefit-led
by default or Identity-led). The model receives the idea, language, selected
policy and canonical Product Brief skill; validation rejects unsupported
proof.

The console waits for an explicit Project selection (or a valid Project deep
link); it does not automatically select the first list item. Generation controls
belong to the selected Project. Selecting an approach alone does not generate or
replace a Brief.

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
honorable and to select one accepted Post template version from the gallery.
The first creative starts on that exact version; no Phone Metrics draft or
subsequent template switch is required. The approval and first
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

New requests produce ProductBriefV3, retaining V2’s compact `positioning` object:
marketing_approach, desired_identity (may be empty), customer_tension,
category_frame and functional_value. Each copy field is at most 200 characters;
the complete object is at most 1024 UTF-8 bytes. It is hypothesis context, never
proof or permission to invent capabilities. The Identity-led policy includes
conditional examples from the owner-supplied marketing transcript.

Identity-led copy must express a specific human occasion or aspiration in the
main promise, audience and offer, rather than restating the category in the
positioning box. Editorial policy revision 6 connects four moves: a meaningful
category reframe, a grounded convention or tradeoff, the buyer's valued identity,
and a supplied functional reason for the emotional reward. The tension may be a
positioning hypothesis for sparse ideas, never a fabricated market fact. Specific
or elevated wording is optional; plain precise language is valid. A short (aim
3–5 words) headline leaves explanation to supporting copy. Post and Landing
share the identity through recognizable product action and factual benefits,
without forcing all four moves into each short field. The reviewed mentoring-call lesson no longer prescribes
a consultation across product categories. V2 accepts a natural first action as
the offer without promotion keywords; V1 retains its historical validator.
The existing immutable policy digest distinguishes revisions without rewriting
prior settings. This instruction change is owner-directed, not a performance
learning promotion.

Local real-inference check: `.venv/bin/python scripts/try_identity_brief.py
--idea 'car sharing'`. The default is Ukrainian/Identity-led. Use `--language en`
or `--approach benefit_led` and a different `--output-dir .local/<trial-name>`
for a new comparison. Completed receipts are reused, not regenerated silently.
Run `scripts/run_local_studio.sh` to test the complete UI at
`http://127.0.0.1:5173/?e2e=1`; select/create a Project and generate a new Brief
or explicitly correct an existing one. Existing immutable copy stays intact.

Create/correct endpoints accept optional `marketing_approach` (`benefit_led` or
`identity_led`). Creation defaults to Benefit-led; correction inherits the base
approach when unchanged. V3 corrections also inherit their policy snapshot;
new corrections of V1/V2 upgrade to V3 using the current policy for that approach.
Changing approach creates a fresh unapproved replacement
through the same HumanFeedback/WeightUpdate lineage. It never activates a global
rule. Selection participates in request identity; retries preserve their policy.

Migration 020 adds nullable immutable `generation_settings` with the selected
policy text, version/digest and output schema version. Null identifies a V1
reservation, including failed/queued historical work. No old document or digest
is rewritten. Local append-only metadata enforces the same settings boundary.
V1, V2 and V3 remain readable. Migration 021 permits V3 settings without rewriting
rows or weakening immutability. Deploy compatible readers and migrations before
enabling new generation; rollback must retain readers for all stored versions.

V3 adds a visible **Brand identity / Ідентичність бренду** section in Project
Briefs and Natal Create. Its bounded `brand_identity` object names belief,
identity signal, values, cultural tension, category reframe, emotional reward,
competence cue, practical proof anchor, voice, visual world and optional ritual.
These are one brand hypothesis and instructions for content/imagery, not evidence,
a new company identity, an invented service or a replacement for Natal branding.
Each field is <=260 characters; the entire object is <=3072 UTF-8 bytes, alongside
the unchanged <=1024-byte positioning object. Current Identity-led policy asks
for a grounded cultural tension; ritual stays optional. The V3 schema still
accepts an empty tension for frozen historical policy snapshots.

Post, Landing, Manual Agent and image contexts inherit positioning and brand identity from their
exact source Brief. Their read-only approach label cannot change independently.
Canonical policy references are versioned separately from reviewed Analytics
skills; no new inference call is introduced.

Local verification: `scripts/try_identity_brief.py` exercises real generation;
`.venv/bin/python scripts/verify_brief_brand_migration.py` creates and removes its
own disposable PostgreSQL container to check historical V1/V2, V3 corrections,
duplicate requests, restart reads and immutable settings. No existing DB is used.
The [car-sharing review](car-sharing-identity-review.md) records real V3 examples.

The [private generation trial](marketing-approaches-trial.md) records paired
examples, reproducible checks and editorial limitations without performance claims.
