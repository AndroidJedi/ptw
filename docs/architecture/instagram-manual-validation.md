# Instagram-first manual validation

PTW's primary job is a fast, convenient test of a business idea. The active
flow is deliberately narrow:

1. create and approve Post creatives;
2. create, approve, and publish one Landing;
3. publish an organic Instagram Post directly or export it for manual upload;
4. prepare 2–6 paid variants, reproduce one fixed campaign manually in Meta Ads
   Manager, and import its CSV results;
5. combine paid delivery with automatically collected first-party Landing
   events per exact Post/Ad arm.

This boundary avoids an Ads API/app-review dependency. Meta Ads API automation
and TikTok routes/jobs/UI are inactive. Their historical tables and modules are
preserved; recovery requires an explicit owner request and
`skills/legacy-social-automation-recovery/SKILL.md`.

## Exact Post attribution

Every direct Instagram publication, manual Post package, and paid test arm gets
its own opaque `ptw_attribution` token and HTTPS Landing URL. The URL is appended
to the exact copy delivered or copied for that source. A token is registered to
the immutable approved Post version and either publication, manual package, or
test-arm entity. The Landing shell records cookieless `landing_view`,
`primary_cta_click`, and `contact_click` events against that source.

Studio markers `**` and `==` are renderer syntax and are removed from copied
plain text. Manual **Copy all texts** returns headline + supporting text + offer
with the unique tracked URL as the final paragraph. The owner can mark the
package Published or Abandoned; both are append-only events.

Instagram Feed caption URLs are generally not clickable. Exact organic click
attribution therefore requires placing the package URL in the profile bio or a
Story link associated with that Post. Paid-test arms use their exact URL in the
Ads Manager **Website URL** field, where it is clickable.

## Fast creative variants

An owner may clone any selected approved Post version into a new same-template
draft. The clone receives a new creative identity and no approved versions. It
inherits the approved configuration, content, and digest-verified raw asset
snapshot without an AI call, then follows the ordinary edit, preview, Save, and
Approve flow. A request UUID makes cloning idempotent and graph lineage records
`derived_from` the approved source version.

Only the background is mandatory in both active Post templates. Every
foreground group is optional. Repeated Post items, Phone Metrics cards,
and in-phone action buttons have individual visibility switches. Hidden content
is retained for later restoration, omitted from the render/semantic projection,
and remaining elements reflow deterministically.

## Manual paid-test contract

One prepared test freezes one currently published Landing and 2–6 distinct
approved Post versions. It creates deterministic Campaign, Ad Set, and Ad names,
one tracked URL per arm, total budget, ISO currency, duration, and derived daily
budget. PTW stores no audience.

The downloadable ZIP contains a manifest, Ukrainian setup instructions, each
approved PNG, and separate Headline/Primary text including that arm's exact URL.
The owner reproduces this fixed setup:

- one Campaign using campaign budget;
- one Ad Set containing every competing Ad;
- Objective `Traffic`, destination `Website`, optimization `Landing Page Views`;
- placement `Instagram Feed` only and CTA `Learn More`;
- Dynamic Creative and Standard Enhancements off.

Instagram mobile **Boost post / Просувати допис** is not equivalent. It promotes
an existing organic post through a simplified setup with fewer controls. The
manual Ads Manager flow creates separate Ads, preserves a different URL per Ad,
and lets 2–6 approved creatives compete for one campaign budget.

## Results and lifecycle

First-party Landing events appear automatically. Paid delivery is imported from
a Meta Ads Manager CSV. PTW detects common Ad name, spend, impressions, link
click, and Landing-page-view headers, shows the mapping and matched/ignored rows,
and requires confirmation before import when rows are ignored. CSV snapshots are
immutable and idempotent by file digest.

The primary comparison is cost per first-party primary CTA click. Contact clicks
are supplemental. The lowest observed cost may be labelled **Current leader**,
but PTW never declares an automatic statistical winner.

Lifecycle is `prepared → active → completed` or `prepared → abandoned`. Only one
test may be active per Project. While active, publishing, replacing, or
unpublishing its Landing is blocked. Completion requires explicit confirmation
that both Campaign and Ad Set are stopped in Meta.

## Active API surface

Owner routes are under `/api/v1/instagram-tests` and Validation mirrors them
under `/internal/v1/instagram-tests`:

- Project workspace and manual-package list/create/action;
- test create and lifecycle action;
- CSV preview and confirmed import;
- digest-labelled launch-kit download.

Organic Instagram routes remain under `/api/v1/instagram`; the public temporary
JPEG route remains GET/HEAD-only. `/api/v1/ads`, `/api/v1/tiktok`, and public
TikTok media routes are not mounted and return 404.
