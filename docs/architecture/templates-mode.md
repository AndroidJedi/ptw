# Private Templates mode

Status: source implementation; not deployed.

Templates is a global owner destination at `?page=templates`, with no Project
selector. Post and Landing filters include their protected built-ins and owner-
accepted designs. Cards read the current immutable version and its digest-bound
preview. Detail includes full-resolution preview links, historical versions,
component roles and the exact optional Post reference. It never creates Project,
Brief, contact, evidence or publication records to populate a card.

## Registry and rendering

`template_registry.py` remains the surface-neutral identity/lookup contract.
Registries support multiple immutable versions and an exact-reference loader;
`TemplateAuthoringService.registry(surface)` combines the existing surface's
built-ins with accepted declarative definitions. Existing Project renderers,
controls, generation, saves, approvals and lineage keep their original paths.
A built-in edit creates a derivative ID. Other edits append a version of the same
ID, with optimistic checks against the version that was edited.

New definitions compile the reusable typed vocabulary in
`template_components.py` into the existing `StudioRenderer` primitive engine.
Text, images, buttons, cards, overlays, decorations, the existing iPhone
compositor and canonical Natal identity have finite styling,
geometry, typography and crop controls, separate mobile geometry, and at most
16 instances. Runtime `definition.render(configuration, content, assets, mobile)`
uses the same compiler and renderer as preview; ordinary bounded content and
registered image slots can be bound without rewriting template source. Template
configuration stores only neutral placeholders, never reference pixels or domain
content. New definitions do not change existing Projects automatically. The Post editor's
Change template action explicitly applies one accepted version to an existing
Post, preserving copy, raw image and approved history. The Post still requires
its own approval before publication.

Phone Metrics previews use a disposable workspace and the real Phone renderer.
The built-in Landing preview runs the shared `LandingPage` React renderer in
network-isolated Chromium with bundled fonts and neutral fixtures. Build its
bundle with `npm --prefix apps/commander-web run build:template-preview`; the
local launcher and Validation image build do this automatically. No separate
mock gallery artwork exists. Browser failure yields an explicit preview retry.
Accepted historical PNGs remain immutable even after renderer code changes.

## Durable creation and review

The authenticated `/api/v1/templates` API offers gallery/filter reads, exact
version reads, version history, temporary reference uploads/discard, start,
progress/history, resume/correction, decision, media and capability handoff.
Owner Gateway requires both Firebase owner and App Check; the private Validation
mount requires the Gateway token. Loopback uses its normal owner dependency.
Only bounded GET/POST routes are forwarded. Media is authenticated, SHA-checked
and private/no-store. JSON bodies are streamed into explicit byte limits.

Post-only and Landing-only requests reserve one definition. Combined creation
analyzes one reference once, then composes both surfaces in one bounded context.
Acceptance transactionally appends two separate definitions. Landing stores the
exact accepted Post `{template_id, template_version, template_sha256}`. An
independent Landing can also receive an exact existing Post template reference;
resolution exposes only identity, description, canvas and component roles.

A run persists analysis, composition, authoritative preview metadata, concrete
comparison differences, invocation sizes/attempts, and lifecycle transitions.
The Templates page lists every nonterminal run in a separate Drafts section above
the accepted gallery. Draft cards expose only bounded summaries: scope, localized
status, phase, comparison count, safe failure details and digest-bound preview
metadata. Active cards poll automatically. Failed, interrupted, paused,
capability-gap and proposed work remains directly openable; accepted and rejected
runs move to compact history. Only accepted versions enter the reusable gallery
and Project template picker.
Compose → render → compare repeats for meaningful solvable differences. A first
render is insufficient. Geometry validation rejects text overflow and out-of-
bounds components. Every proposal needs a completed comparison with no meaningful
unresolved differences or geometry errors. Accept and Reject are explicit owner
actions. Corrections such as moving a CTA or enlarging a photo use patches and
create another immutable version after review.

One worker admits one active creation run. A segment permits four render/compare
iterations, a run at most twelve iterations and 32 provider calls. The existing
420-second per-provider deadline and one corrective response attempt remain.
The worker checks its 900-second segment budget between calls. Timeout, transport
failure, no progress and exhausted segments persist resumable state. Startup
marks active runs interrupted and never replays inference or acceptance. Pending
adjustments survive iteration limits. Request UUIDs reconcile uncertain writes;
state hashes reject stale corrections/decisions. Failed UI mutations retain the
original request for retry; definite validation errors permit correction.
If compare fails, resume first verifies that every saved preview still matches
the current definition digest and reloads those exact immutable PNG bytes. It
does not rerender or increase the iteration count before a valid comparison is
returned. Failures persist only phase, category, model, pinned effort, attempt
count and a sanitized validation error; raw responses, stderr, credentials,
paths and pixels remain excluded.

## Reference and payload boundaries

PNG/JPEG/WebP references reuse the existing decoder: at most 8 MB, 64–8192 source
pixels and 16 megapixels; orient, decode, normalize to at most 2048 pixels and
strip metadata. Handles expire in ten minutes and capacity is bounded. Pixels
remain in operation memory or the provider's temporary attachment files, never
SQLite/PostgreSQL records, template versions, skills or browser history. Worker
completion/failure and restart discard them. After analysis, resumed work may
use the saved visual description without pixels; a fresh reference starts a new
analysis. Before analysis, an interrupted run needs the reference reattached.
Screenshot text is untrusted reference content. Typed response validation cannot
execute code or create arbitrary components, claims, contacts or evidence.

The `template_creation` mode shares `LocalCodexStructuredProvider` and
`StructuredBridge`. Its canonical skill is `skills/template-creation-agent`.
System/input/schema/total/response budgets are 6/40/8/52/20 KiB. The system share
includes room for the bounded second-attempt validation correction. Later calls contain
only the current definition, selected component capabilities, one analysis and
the latest comparison, plus necessary image attachments. They omit skills/rule
histories, graph rows, repository source and unrelated registries. Every call
preflights bytes before provider admission and persists measured sizes and
attempt counts. Analyze, compose and compare always use `xhigh`; model and effort
are bound into the provider request fingerprint and sanitized invocation
metadata. The bridge must explicitly advertise this optional JSON and multimodal
mode together with `reasoning_efforts.template_creation = xhigh`; existing
required modes retain their current effort and remain compatible without it.

## Reusable capability extension

The priority is existing settings, existing composition, a reusable parameter,
a reusable component, then an explicitly justified exceptional implementation.
An agent cannot execute generated code. A `capability_gap` requires a meaningful
unsolvable comparison, evidence, affected surfaces, a reusable abstraction and
an explanation of why existing composition is insufficient. Existing settings
cannot masquerade as a gap; reference-specific component names are rejected.

The owner can export a development handoff for Commander GOD mode. The separate
local `scripts/review_template_extension.py prepare|verify|apply` workflow creates
a disposable source snapshot including current uncommitted work. Its fixed
component/renderer/registry/test/documentation allowlist rejects unrelated writes,
deletions, symlinks and concurrent checkout changes. Verification requires focused
capability tests, an actual rendered capability PNG and the Studio geometry audit;
web changes also require web tests/build. Apply requires the exact verified review
digest after owner inspection. A source receipt binds implementation hashes;
apply rechecks that visual digest and rolls back source if a write fails.
Resume requires both that receipt and exposure in the live catalog. No browser
endpoint can register a capability or run a coding shell. Studio Manual Agent's
non-coding boundary is unchanged.

## Storage and verification

Forward migration `013_template_authoring.sql` adds append-only
`template_authoring_records` and `template_authoring_media`; it changes no existing
rows or applied migration. Short PostgreSQL advisory-locked transactions and
loopback SQLite transactions implement the same state/CAS/request contract.
Version acceptance and coordinated references are atomic. Database triggers
protect history and media from update/delete. Reference bytes are absent.

Focused tests cover normalization, bounded contexts with enormous unrelated
histories, all scopes, repeated comparison, capability gaps, versioning,
request reconciliation, authentication, timeout and recovery. The dedicated
Playwright suite uses real HTTP, persistence and native rendered PNGs; only model
inference is scripted. `scripts/verify_template_authoring.py` exercises the new
migration and save/restart behavior in disposable PostgreSQL. Native Phone and
Landing preview inspection accompanies the existing Studio visual audit.

The disposable real-Codex combined canary converged after two render/comparison
iterations, then resumed for another comparison with the saved analysis and no
retained reference pixels. All five successful calls needed one provider attempt.
Measured contract totals were 5,406 B for analysis, 15,410 B for composition,
16,367/17,093 B for comparison, and 18,074 B for the resumed comparison using the
final catalog and skill. Responses were 2,153, 2,660, 933, 443 and 418 B.
The final invocation comprised a 3,402 B system prompt, 11,360 B payload and
3,312 B schema; 125,123 B of preview attachments stayed outside JSON context.
These are actual measurements of the disposable neutral fixture, not a promise
of convergence for every uploaded design.

The saved owner run `fff155a8-b5c0-4313-a958-18aaf3c9e779` also exercised the
recovery path against real local Codex. Its failed compare reused the exact
57,359-byte persisted preview without increasing `iterations=2`. The first
`xhigh` response required the one allowed structured correction; reserving 6 KiB
for the corrected system prompt kept that retry inside the unchanged 52 KiB total
budget. The valid response supplied six solvable patches and identified a wave
divider capability. The owner correction chose an existing-decoration
approximation, after which compose and three comparison calls each completed in
one attempt. The final comparison returned no edits, differences or capability
gap. The proposed preview is 57,304 bytes with digest
`cb204e45c6cb7a0d67fdd443315be4d59beae5b5b523cefad12718a819c086a2`; it remains
an unaccepted draft.

Remaining bounds: galleries/version summaries return at most 200 records and
run history at most 30. Exact historical identity reads remain available.
Accepted Post templates are available in the existing Post editor through
Change template. Initial Brief generation and Landing template selection retain
their established composer definitions.
Source extensions require local owner review. Production inference additionally
requires the companion bridge to advertise `template_creation`.
