# Natal landing builder

Status: three-template draft preview workflow locally implemented; production remains on the prior iterative workflow
Updated: 2026-08-23

## Purpose

Natal is a fast, repeatable landing-page factory. Every page keeps the exact
Natal name, digest-pinned logo/icon assets, color and type tokens,
mobile/accessibility baseline, and one of three dependency-free layouts:

| Template | Source structure | Use |
| --- | --- | --- |
| `product` | `natal_landing` | Feature-led software and services |
| `community` | `sesh` | Events, groups, and participation |
| `waitlist` | `ofc_landing` | Early concepts and demand tests |

Recommendation is advisory. All three variants remain private and selectable
until the owner explicitly publishes one.

## Independent page model

`LandingPageContent` separates copy into `hero`, `problem`, `features`, `steps`,
`proof`, `faq`, and `final_cta`. The renderer consumes each block independently,
HTML-escapes its copy, and writes the exact model to private
`page_content.json`. Editing one block replaces only that block in code.

Template layout, Natal assets and UI kit, Idea run/thesis IDs, CTA destination,
and verified proof remain server-owned. Agent output cannot change them. The
canonical skill reads focused block, content, and reviewed-owner references
under `skills/natal-landing-builder/references/`.

## Draft workspace

The authenticated Landing tab resolves a completed Idea Laval case and calls
`POST /api/v1/landings/draft-sets`. One fresh, strict-schema
`natal_landing_revision` call uses `populate_set` to return all three complete
page models. The request ID is idempotent. The durable set moves through
`queued`, `populating`, `ready`, or `failed`; its variants and current snapshots
are polled from `GET /api/v1/landings/draft-sets/<id>` and recovered after
refresh or restart.

`GET /api/v1/landings/draft-snapshots/<id>/preview` returns authenticated,
private, no-store JSON containing a self-contained HTML document. Canonical
CSS and assets are inline. The Owner UI supplies it through sandboxed `srcdoc`
with scripts only, renders it at 360 px or desktop width, and makes preview CTAs
inert. A block-selection message is accepted only when its source is the exact
current iframe window and its template/block IDs are canonical.

`POST /api/v1/landings/draft-snapshots/<id>/edits` accepts a request UUID, one
block ID, and one bounded instruction. The comment, feedback graph entity,
zero-delta weight update, and reusable-lesson proposal commit before the agent
call. `edit_block` receives full-page context but returns only the selected
block. On success, the new snapshot supersedes its parent and derives from the
exact feedback. On failure, the attempt stays retryable and the prior snapshot
remains current. An edit against a superseded snapshot returns HTTP 409.

## Runtime memory and reviewed lessons

Every comment is append-only runtime memory scoped to its Idea, template,
snapshot, and block. PostgreSQL returns the latest bounded set in chronological
order. Feedback `evaluates` the exact snapshot and digest; a zero-delta
`WeightUpdate` `adjusts` the stable template/block component.

The agent also proposes a generalized lesson. The owner may edit, dismiss, or
promote it. Promotion starts the existing Plan/Execute workflow with a bounded
instruction that may change only
`skills/natal-landing-builder/references/owner-lessons.md` and must run skill
validation. Browser actions never write Git directly.

## Persistence and lineage

Migration 017 adds durable draft sets, append-only snapshots and edit attempts,
and skill proposals. It backfills existing feedback with a generic target
entity and adds template/block/snapshot scope to new feedback. Builds may store
an exact source draft snapshot and page-content digest while preserving the
legacy brief-based request and published response fields.

Graph lineage is explicit:

- the draft set derives from the stable Idea source;
- every snapshot is contained by and derives from its set;
- an edited snapshot supersedes its parent and derives from its feedback;
- feedback evaluates the exact snapshot digest;
- published Landings derive from both the selected snapshot and Idea source,
  and may supersede a selected published parent.

## Explicit publication

Preview work never contacts Firebase. `POST /api/v1/landings/builds` with
`draft_snapshot_id` validates that the snapshot is current and that its content
digest matches, then builds and publishes that exact model without another
agent rewrite. Only this action creates an increasing numbered Landing
revision. The legacy brief path remains for compatibility.

Firebase still uses a server-pinned service account and site. Releases contain
only allowlisted HTML, CSS, JavaScript, SVG, and PNG. `brief.json`,
`page_content.json`, and `build.json` remain private. Publication checks the
emergency stop immediately before the external release, and failures remain
durable and retryable.

## Production baseline

Production deployment is intentionally out of scope for this milestone. The
last verified production state remains release `natal-feedback-bbcaf90` at
commit `bbcaf90`, Owner Console Hosting `61a24c84ce884c0b`, and the prior
publish-first iterative workflow. Existing published revisions and URLs remain
immutable. No Firebase or VPS state was changed while implementing the private
draft workspace.

## Verification

Local acceptance uses a non-publishing fixture and disposable PostgreSQL:

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
python3 -m unittest discover -s tests/owner_gateway -p 'test_*landing*.py' -v
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
python3 scripts/verify_ptw_skills.py
git diff --check
```

Run the runtime-only Python tests in the built image as documented by
`AGENTS.md`. Repository tests use `LANDING_TEST_DATABASE_URL` pointed at a
disposable migrated database.
