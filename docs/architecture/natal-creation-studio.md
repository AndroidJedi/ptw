# Natal Creation Studio

`?page=create` is the private standalone product page. It has one input for an
idea or pasted Brief, an optional public HTTPS reference and optional image,
then a choice of Brief, Post, Landing, a complete package, or reusable templates.
Input, Brief, previews, agent conversation and export are collapsible sections.
All editing is through `gpt-6-astra` with `xhigh`; there are no manual content or
design controls. Post/Landing viewport switches only change preview presentation.

## Authority and generation

`validation_pipeline/creation_studio.py` orchestrates durable stages:
reference observation → canonical Brief → template design → content binding →
artwork → native renders → visual review. It uses existing structured provider
modes; there is no arbitrary-code authoring or additional bridge protocol.
`skills/natal-creation-studio` is the bounded content/reference/review skill;
`template-creation-agent` supplies design and comparison; canonical Brief services
retain their own skill and strict ProductBriefV1 validation.

Local creation sessions use `.local/creation-studio.sqlite3`. Production uses
append-only `creation_studio_records` and digest-checked PNG bytes in
`creation_studio_media`, introduced by migration 019. These are a separate
namespace of the existing authoring store, with request UUID receipts, content
hashes and compare-and-swap revisions. Session and stage IDs remain visible in
the API and URL. One creation is admitted at a time. Startup marks unfinished
sessions interrupted; it does not silently replay model or image calls.

Design timeouts receive one automatic retry; ordinary saved segment boundaries
may continue twice within the existing total budget. Repeated failure exposes
localized recovery derived from the linked template failure/checkpoint, including
older saved sessions. Continuation preserves the exact Brief and design IDs.
Layout no-progress retries enter refinement with the recorded issues instead of
repeating an unchanged comparison. Cached visual-review failures, unsupported
capabilities and exhausted budgets do not offer a no-op Retry button.

Briefs are real Project Brief entities. Corrections use the existing immutable
revision path, HumanFeedback, WeightUpdate and graph relationships. Automatic
creation never manufactures approvals. The generated Post and Landing are
**concept drafts** referencing the exact Brief UUID/hash, not approved native
Project Post/Landing versions. Existing approval, contact, publication and
Instagram validation contracts are unchanged.

Definitions retain neutral placeholders. Actual copy and image bindings are
stored separately. Every design uses the canonical Natal brand. Website company
logos are excluded from the authoring catalog and rejected in new agent patches;
historical asset bytes remain readable. Whole subjects retain their proportions.
Source-copy claims and proof do not become another idea's evidence.

Saved template runs can supply an exact reusable design for new ideas. Edits to
accepted pairs create derivatives with new identities and an exact origin-run
hash; acceptance binds the new Landing to its new Post. Editing one surface
constrains the agent's validated patch set to that surface and preserves the
other surface's content and image bindings. Previously saved versions survive.
Reviewed legacy template runs can be opened here with `/imports` without
fabricating another provider invocation or acceptance.

Real bound text is checked by the native geometry audit. Up to two bounded copy
fit passes may run. Astra then inspects the actual Post and desktop/mobile
Landing PNGs. It can propose up to eight layout/framing patches per pass, limited
to boxes, font size, fit and focal points. At most two automatic layout passes
are applied as per-session overrides; source templates stay unchanged. Semantic
image problems, unsolved defects and exhausted passes become visible review
checkpoints. Completion is never inferred merely from changed bytes.

## References

`capture-website-reference.mjs` loads a public HTTPS page in an ephemeral browser
with site JavaScript and service workers disabled. Every browser resource goes
through a bounded HTTPS fetch that resolves public IPv4 addresses, pins the
connection to a validated address and rechecks redirects. Private/reserved
addresses, credentials in URLs, nonstandard ports, scripts and non-GET requests
are rejected. Requests, bytes, redirects and elapsed time have finite limits.

The trusted capture code activates deferred styles and visible lazy images,
including picture sources, then waits for fonts/image decoding. It captures
desktop and mobile screenshots. Uploaded images take priority within the two
reference-image budget. Raw screenshots are temporary; source URL, title, pixel
digests and bounded observations persist. Network-blocked or inaccessible sites
fail honestly and can be supplied as screenshots instead.

Photo reuse requires the explicit checkbox. Up to three downloaded candidates
are visually inspected; the agent excludes logos, screenshots, watermarks and
baked-in promotion banners. Selected normalized PNGs persist with source URL,
source-byte SHA-256 and normalized digest. This does not assert a public license.
Code-level asset registration still uses original files and the offline manifest
as described in `skills/template-from-website`.

## API and export

Owner Gateway allowlists `/api/v1/create/designs`, `/runs`, `/imports`,
`/references`, `/runs/{uuid}`, `/runs/{uuid}/{edit|retry|accept}`,
`/runs/{uuid}/export` and `/media/{sha256}`. The production bridge uses
`/internal/v1/create`. All routes require the existing owner identity and App
Check or internal gateway authentication. Request bodies are bounded and
responses are private/no-store. PNGs and ZIP exports carry integrity digests.

Downloads contain Brief JSON, reusable definitions, separate content bindings,
PNG previews, per-idea art/provenance and a responsive standalone HTML Landing.
The HTML embeds canonical fonts/assets, includes font licenses, escapes copy,
and contains no remote scripts or tracking. Its buttons are preview actions:
there is no implied publication, live lead collection, public sharing link,
Meta Ads deployment or TikTok reactivation. File downloads support owner sharing.

## Verification

`tests/validation_pipeline/test_creation_studio.py` covers real authority,
rendering, canonical Brief corrections, retry/idempotency, exact template reuse,
immutable derivatives, temporary references, auth, exports and protected surfaces
with scripted inference. `scripts/creation_browser_canary.py` drives the same
HTTP/storage/renderer implementation for desktop, 360px and iPhone WebKit tests
in `e2e/creation-studio.spec.ts`. Keep scripted and real-provider evidence distinct.
Exercise migration 019 only against disposable databases during development.
