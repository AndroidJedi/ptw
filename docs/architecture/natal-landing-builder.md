# Natal landing builder

Status: one-click Firebase publication implementation complete; production verification pending
Updated: 2026-08-22

## Purpose

Natal is a fast, repeatable landing-page factory. Every generated app keeps the
exact Natal name, canonical logo, icon set, color tokens, typography, and
mobile/accessibility baseline. Only evaluated product content changes.

The canonical kit is `natal/`. Its PNG and SVG assets are copied from
`natal_business` and pinned by SHA-256 in `natal/brand/brand.json`. Three
dependency-free static structures distill the supplied reference projects:

| Template | Source structure | Use |
| --- | --- | --- |
| `product` | `natal_landing` | SaaS, software, B2B, or feature-led services |
| `community` | `sesh` | Events, offline participation, groups, or communities |
| `waitlist` | `ofc_landing` | Early concepts and lean demand validation |

The templates share one stylesheet and runtime. The builder accepts a bounded
version-1 JSON brief, validates copy and CTA URL schemes, HTML-escapes supplied
text, verifies brand asset digests, and emits a static site plus normalized
`brief.json` and provenance-bearing `build.json`. It refuses to overwrite a
non-empty output directory unless explicitly told to do so.

## Commander handoff

The Owner Console `Лендинги` tab reads completed live Idea Laval cases through
the authenticated Owner Gateway. The gateway resolves the preferred thesis and
maps its target user, problem, value moment, mechanisms, and loop into an
editable brief while retaining the Laval run and thesis IDs. Browser overrides
cannot change those source IDs or the Natal brand.

Template recommendation is deterministic: community/event semantics choose
`community`, product/system semantics choose `product`, and other early
concepts choose `waitlist`. The owner may explicitly override the structure.

Submitting the brief calls `POST /api/v1/landings/builds` with a browser-created
idempotency UUID. Under the shared heavy-operation lock, Owner Gateway resolves
the completed case again, ignores browser-provided brand/source IDs, creates a
PostgreSQL `landing` entity plus `derived_from` edge to the stable Idea Laval
source alias, and commits the `queued` build before starting it. The deterministic
builder then moves through `building` and `publishing` without a Commander plan
or a Codex login dependency. The Landing tab polls that build directly and shows
its Firebase URL or a retryable failure; it never redirects to unrelated Jobs.

Publication uses the Firebase Hosting REST deployment flow with a dedicated
service account and the server-pinned `natal-landings-86123` site. Each complete
release preserves recent published builds under `/builds/<build-id>/` and makes
the newest build the site root. The publisher accepts only HTML, CSS,
JavaScript, SVG, and PNG files, rejects symlinks and unexpected files, and does
not stage the normalized `brief.json` or provenance-bearing `build.json`. The
emergency stop is checked again immediately before the external release.

The old `/api/v1/landings/builder-jobs` route remains as a rollout compatibility
alias, but it starts the same real build and publish lifecycle. Existing failed
Commander plans remain immutable audit history and are not rewritten as
successful landing builds.

## Verification

```sh
python3 -m unittest discover -s tests/commander -p 'test_natal_builder.py' -v
python3 -m unittest discover -s tests/owner_gateway -p 'test_*landing*.py' -v
python3 -m unittest discover -s tests/owner_gateway -p 'test_firebase_hosting.py' -v
npm --prefix apps/commander-web run check
npm --prefix apps/commander-web run test:e2e
python3 scripts/verify_ptw_skills.py
git diff --check
```
