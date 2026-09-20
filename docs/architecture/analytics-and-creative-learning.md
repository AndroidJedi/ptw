# Analytics and reviewed Creative Skills

Analytics is a project-aware Owner Console workspace that joins immutable social
outcomes, cookieless Landing funnel events, reviewed Meta CSV snapshots, exact creative
versions, and reviewed Creative Skill snapshots. It does not publish content,
change an ad, spend money, or activate a performance-generated rule.

## Scope and owner workflow

The Analytics destination supports one selected Project or **All Projects**, with
7, 30, 90, and all-time windows. It shows provider readiness and freshness,
organic and paid results, the Landing funnel, a post leaderboard, the learning
curve grouped by the exact Creative Skill snapshot IDs used at generation, and
the complete active/tombstoned rule history in the latest snapshot.

**Run learning** is the only performance-learning trigger. It freezes the
selected scope, surface, complete eligible creatives, normalized outcomes,
attribution totals, active skills, and a canonical dataset digest. A Project run
may propose `ui`, `copy`, `image`, or `domain` rules. An All Projects run may
propose only abstract `spirit` principles. Candidate rules stay inactive until
the owner selects and optionally edits individual rules, then chooses
**Activate**. **Reject** records a terminal decision without a skill change.

Direct owner rule edits immediately append a new immutable active skill
snapshot. Delete appends a tombstone; no skill, run, decision, snapshot, or
aggregate history is physically removed. Reused request UUIDs are idempotent
only when their canonical inputs match.

Save and Approve remain normal Post/Landing persistence boundaries. A changed
Save creates only its lightweight immutable edit checkpoint; Approve also writes
the immutable approved version. Neither action calls a learner, displays a
learning dialog, retries learning, or blocks deployment/recovery on learning.
Historical Save-era learning rows remain readable PostgreSQL history but are not
consumed by generation or exposed as an active workflow.

## Provider collection and readiness

Publishing readiness and analytics readiness are independent.

- Instagram publishing checks remain separate from
  `instagram_manage_insights`. Analytics reads media insights only when that
  separate capability is authorized.
- Paid Instagram-test rows use immutable, owner-reviewed Meta Ads Manager CSV
  imports. First-party Landing events update independently and automatically.
  Analytics never stages, activates, pauses, or edits an ad.
- Historical TikTok and Meta Ads API snapshots remain authority records but
  their collectors are inactive and are not readiness claims.

For direct Instagram publications, the scheduler records immutable snapshots at 24h,
72h, 7d, 14d, and 30d after publication. `capture_key` makes each scheduled
milestone unique. The 15-minute scheduler accepts a bounded six-hour milestone
window; after that it cannot truthfully reconstruct the missed total. Manual
refresh adds a new timestamped snapshot. The labelled
one-time backfill adds at most one `backfill` snapshot per older PTW publication;
it does not fabricate missed milestones. Provider errors are shown per item and
do not change publication state.

## Landing events and attribution

Every public Landing sends these first-party events without consent because the
contract is cookieless and contains no persistent visitor identity:

- `landing_view`: `surface=page`, `target=page`;
- `primary_cta_click`: `surface=hero|phone`, with the exact configured bounded
  target (`contacts`, `telegram`, `instagram`, `email`, or `phone`);
- `contact_click`: `surface=telegram|instagram|email|phone` and the same target.

The public `POST /api/v1/public/landing-analytics/events` body contains exactly:

```json
{
  "event_id": "uuid",
  "visit_id": "ephemeral uuid",
  "route": "/ai/example",
  "landing_version_sha256": "64 lowercase hex characters",
  "event_type": "landing_view",
  "surface": "page",
  "target": "page",
  "attribution_token": null,
  "viewport_class": "mobile"
}
```

The Gateway accepts only JSON up to 4 KiB from the configured public Landing
origin. Validation resolves the active Project, publication, event, Landing
version ID, and version digest server-side and rejects a stale digest, invalid
event semantics, or an attribution token belonging to another publication.
An exact `event_id` replay returns the original acceptance without consuming
rate budget; reuse with changed input is rejected. A visit UUID is
created in memory on page load and is neither a cookie nor local storage. The
single-process ingestion boundary permits at most 60 events per ephemeral visit
and 600 per resolved Landing route per minute; the buckets are memory-only and
are evaluated only after the active publication and attribution are validated.
The bounded route is used for that resolution and the memory-only rate bucket,
then discarded; raw event storage contains the resolved immutable IDs instead.

PTW does not accept or store contact values, raw URLs, referrers, IP addresses,
user agents, device fingerprints, or a durable visitor profile. Raw events are
immutable while retained and deleted after 90 days. Each accepted event also
appends an immutable cumulative daily aggregate; aggregates and learning
manifests are retained indefinitely.
Meta Pixel remains a separate browser integration that loads and sends
`PageView` only after explicit consent. First-party events never imply Meta
consent.

Each future organic publication or manual Post package receives one opaque
43-character attribution token and tracked Landing URL. Copy/export surfaces put
that URL at the end of the caption and also expose it separately. Each manual
paid-test arm receives its own tracked Website URL for Meta Ads Manager. Tokens
identify a Post/Ad arm, not a visitor, and resolve only on the server.

## Metrics

Platforms are never pooled inside a Post comparison. Learning compares complete
creatives in the same platform and age band, using the exact approved version,
configuration, content, PNG digest, visual descriptor, and generation skill
snapshot provenance. Eligible Post bands are 72h, 7d, 14d, and 30d. Landing
comparisons use the same age bands and bind the exact approved
version/configuration/content/assets and generation provenance. Before freezing a Landing dataset, contact endpoint
values are replaced with channel-presence labels; headings and supporting copy
remain available for comparison. At least two comparable items aged 72 hours are required;
one item returns `insufficient_data`. Two to four items are clearly labelled
`exploratory`; five or more are `directional`, never causal proof.

Priority is fixed: attributable outbound-contact rate, primary CTA rate,
high-intent engagement, general interaction rate, then reach/view velocity.

| Metric | Numerator | Denominator | Source and freshness | Limitations |
| --- | --- | --- | --- | --- |
| Outbound-contact rate | Attributed `contact_click` count | Provider reach/views | Immutable Landing daily aggregate plus latest provider snapshot; display includes snapshot time | Conversion proxy only; not a lead, appointment, or sale. Cross-device and untracked visits are absent. |
| Primary CTA rate | Attributed `primary_cta_click` count | Provider reach/views | Landing aggregate plus latest provider snapshot | Measures a click toward contact, not completed contact. Hero and phone clicks can occur in one visit. |
| High-intent rate | Comments + shares + saves | Instagram reach/views | Latest immutable Instagram snapshot | Engagement does not prove purchase intent. |
| Interaction rate | Likes + comments + shares + saves | Provider reach/views | Latest provider snapshot | Platform-specific interaction definitions are not merged for learning. |
| Reach/view velocity | Provider reach/views | Age in days, minimum one day | Publication timestamp plus latest provider snapshot | A coarse age normalization; it does not model distribution decay or paid spillover. |
| Landing primary CTA rate | `primary_cta_click` | `landing_view` | Immutable first-party daily aggregates; near-real-time after accepted events | Cookieless event ratio, not unique visitors. |
| Landing outbound-contact rate | `contact_click` | `landing_view` | Immutable first-party daily aggregates; near-real-time after accepted events | Conversion proxy, not leads or sales; one visit may click multiple contacts. |
| Paid Meta result | Spend, impressions, clicks, and Landing-page views from the latest matched import | Matching imported delivery totals | Immutable owner-reviewed Meta Ads Manager CSV plus automatic first-party Landing events | Meta controls delivery/reporting definitions; PTW does not call the Ads API. |

An unavailable provider produces an explicit readiness state, not zeros. A
missing snapshot produces a missing/stale value, not inferred performance.

## Visual descriptors

Each unique approved Post PNG may be sent once through the bounded
`creative_visual_analysis` bridge mode. The request contains one digest-bound
PNG, at most 8 MiB. The result contains only safe tags: subject, detail,
composition, density, palette, contrast, and human presence. PTW verifies the
approved bytes against the immutable digest before analysis and stores only the
digest, safe descriptor, descriptor digest, provider invocation metadata, and
Project/version lineage. It does not store another image copy, perform OCR,
infer identity or sensitive attributes, or assign a speculative pre-publish
performance score.

## Typed Creative Skills

Runtime rules use one schema:

```json
{
  "rule_id": "uuid",
  "scope": "project",
  "project_id": "uuid",
  "surface": "post",
  "family": "ui",
  "instruction": "Prefer the compact spacing proven by comparable posts.",
  "target": {
    "template_id": "phone_metrics",
    "component_id": "phone_metrics.offer",
    "setting_id": "configuration.offer.enabled",
    "operation": "set",
    "value": false
  },
  "evidence": {
    "metric": "interaction_rate",
    "summary": "The compact variant led its age-matched comparison.",
    "winning_item_indexes": [0]
  },
  "confidence": {"level": "exploratory", "sample_size": 2, "project_count": 1},
  "active": true,
  "tombstone": false
}
```

`scope` is `project|global`; `surface` is `post|landing|both`; `family` is
`ui|copy|image|domain|spirit`. UI targets must name an exact live template,
component, setting, operation, and catalog-valid typed value or numeric range.
Post uses its established catalogs; Landing exposes the stable v2 component and
setting catalog. Because these targets are surface-specific, UI, copy, and image
rules name either `post` or `landing`; `both` remains valid for Project domain
rules and global spirit principles. Copy targets semantic roles. Image targets
exact asset slots and bounded visual guidance. Domain rules are Project-only and
subordinate to the approved Brief. Global rules are `spirit` only: general principles may be
abstracted from any source family, including one standout Project, but evidence
must retain sample/Project counts and activation always requires review.

Rules with invalid catalog targets/types, global non-spirit families, Project
spirit, or conflicting active UI targets are rejected. Generation precedence is:

1. fixed catalog, brand, and approved Brief constraints;
2. explicit owner direction for the current generation;
3. active Project rules;
4. active global spirit principles;
5. template defaults.

Every new Post and Landing generation freezes the exact Project/global skill
snapshot IDs and SHA-256 digests, including explicit `null` when no snapshot
exists. Runtime skill data stays in PostgreSQL and never rewrites repository
skills. Explicit owner GOD-mode development remains the authority for canonical
system instructions.

## Persistence, APIs, and failure behavior

Migration `008_analytics_creative_learning_v1.sql` is additive. It stores
attribution sources, provider snapshots, raw Landing events, immutable daily
rollups, visual descriptors, frozen learning runs, decisions, and immutable
skill snapshots. Commander entities and `contains` / `derived_from` edges retain
explicit Project, version, artifact, source, and decision lineage. A learning
run may advance to a terminal state, but its request and dataset cannot change
or be deleted.

Owner routes are under `/api/v1/analytics/{project_uuid|global}`:

- `GET /workspace?window=7|30|90|0`;
- `POST /refresh` with `provider=all|instagram` and a labelled
  `backfill` boolean;
- `POST /learning-runs` for `post|landing`;
- `POST /learning-runs/{run_id}/decision`;
- `POST /skills/revisions` and `POST /skills/{rule_id}/delete`.

All owner routes retain Firebase/App Check and Gateway bridge boundaries.
Provider failure leaves prior snapshots readable. Visual failure is reported
separately from insight collection. Learning provider failure records a failed
run and never changes active skills. Stale/unavailable/empty/insufficient states
are first-class UI states.

## Verification and rollout

Required release evidence includes additive migration rehearsal, event
idempotency and CTA semantics, independent Meta consent, provider permissions
and errors, scheduled deduplication, platform/age normalization, visual digest
binding, low-sample behavior, rule validation/tombstones, scope isolation,
generation provenance, responsive desktop/360px/WebKit UI, production builds,
the Commander suite/demo, Studio visual audit, skill verification, and
whitespace checks.

Rollout order is fixed: companion bridge capabilities and canaries; PostgreSQL
migration and Validation API; Owner Gateway; public Landing shell; Owner
Console; provider reauthorization; then read-only live acceptance. Acceptance
must prove one real Landing event reaches Analytics and existing provider rows
refresh without creating a post, mutating an ad, or spending money. Manual paid
acceptance additionally verifies exact per-arm URLs and reviewed CSV mapping.
