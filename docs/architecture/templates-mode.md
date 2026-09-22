# Private Templates mode

Status: deployed; see `commander-current-state.md` for the current hotfix.

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

Three bounded asset classes cover the Bokko reference without reference-specific
renderer code. `brand_motif` repeats the canonical Natal symbol with configurable
placement, opacity and deterministic `rotation_degrees`. `store_badge` resolves
digest-pinned official English Apple or Google artwork from the offline asset
registry; the agent cannot redraw, recolor or replace it. Owner-supplied SVG Repo
badge files can also be registered separately with source and raster digests; edits
may select those exact immutable assets without changing earlier versions. The
component's `badge_surface` defaults to `slot_pill` for existing accepted
definitions. `asset_only` paints only the immutable badge artwork, without an
extra background or mask, when the artwork already contains its own button and
border. The box must then match the artwork's aspect ratio; compare visible
artwork bounds rather than only the component slot. `cutout_image` uses
Pexels photo 15004162 as the transparent, digest-pinned
`neutral_person_stock_v1` authoring fixture. The manifest records source digest,
URL, author, locale and license. An existing Post's real image always replaces
the fixture at runtime. Opaque Project images in `cutout_image` are segmented
locally with a bundled, SHA-pinned U²-Netp model into a transparent PNG. The
raw Post image and its history remain untouched; already-transparent inputs
pass through. If segmentation cannot find a foreground or the model digest
fails, rendering fails visibly instead of placing an opaque rectangle over
the layout. Fixed Natal marks and store badges are never segmented. The model
performs no runtime download or provider request.
`brand_motif.repeat_min/repeat_max` optionally expands one region into 1–8
small canonical marks. Old documents default to one. A stable per-creative
seed varies count, locations and angles across Posts while keeping each Post
identical across refresh, save and restart. Repeated marks render over the
backdrop but behind copy and hero imagery.
Bright owner markup such as circles, arrows and highlights is annotation data and
is never composed into the template.

Phone Metrics previews use a disposable workspace and the real Phone renderer.
The built-in Landing preview runs the shared `LandingPage` React renderer in
network-isolated Chromium with bundled fonts and neutral fixtures. Build its
bundle with `npm --prefix apps/commander-web run build:template-preview`; the
local launcher and Validation image build do this automatically. No separate
mock gallery artwork exists. Browser failure yields an explicit preview retry.
Built-in identities remain readable when native preview rendering is temporarily
unavailable: the gallery and exact-version detail both expose the registered
template with `preview_status: failed`, and a later read can retry the preview.
Creating a derivative from an unavailable built-in preview may use the owner's
instruction without attaching preview pixels. A wrong immutable digest still
conflicts, and an unknown template still returns 404.
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
Opening a draft moves keyboard focus and the viewport to its run panel. For a
proposed run, the accept/reject decision and a short next-step explanation appear
before the preview so the owner immediately sees the available action.
The open run uses a two-column preview/action workspace on desktop and one column
at 360 CSS pixels. Paused runs show a localized checkpoint, remaining comparison
budget, pending-edit count and stable difference categories. Continue applies the
saved edits; Refine accepts a focused instruction; Restore append-only recovers
the latest proposed revision. Each refinement also persists a bounded correction
record. The workspace keeps its exact text visible as **Your request**, shows
Composition → Rendering → Comparison, and exposes explicit Retry and Discard
actions after failure. The latest two unconfirmed texts remain in browser-local
storage across refresh. Accept is rendered only for a proposed run whose latest
correction is applied to both preview and comparison. IDs,
raw model details and operation measurements stay under Technical details.
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
Each refinement records the latest proposed revision as a comparison baseline.
The comparator checks the current request and regressions from that baseline,
without reopening unrelated accepted approximations. Bounded progress history
detects repeated meaningful categories, repeated patch paths and document cycles;
those stop as `no_progress` or `capability_gap` before consuming the remaining
budget.
If compare fails, resume first verifies that every saved preview still matches
the current definition and `render_contract_sha256`. That contract includes the
normalized document, renderer version and fixed-asset digests. It reloads those
exact immutable PNG bytes only when the contract still matches. It
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
use the saved visual description without pixels. A refinement screenshot is a
temporary correction reference for compose/compare; it never replaces the
initial analysis or its reference metadata. Before initial analysis, an
interrupted run needs the reference reattached.
Screenshot text is untrusted reference content. Typed response validation cannot
execute code or create arbitrary components, claims, contacts or evidence.

Studio's browser upload accepts SVG as visual input, rejects active/external SVG
content, and rasterizes it to bounded PNG before the existing image API receives
it. Template creation/edit accepts up to two ordered temporary references. The
agent sees both normalized images in analysis and comparison (and in correction
composition); the append-only run retains only their digest metadata. The
authoritative renderer still consumes digest-pinned raster assets. Source SVGs
are preserved in the offline asset registry for provenance.

The `template_creation` mode shares `LocalCodexStructuredProvider` and
`StructuredBridge`. Its canonical skill is `skills/template-creation-agent`.
System/input/schema/total/response budgets are 6/40/8/52/20 KiB. The first
attempt reserves 3 KiB inside the input and total budgets for a possible
bounded validation correction. A corrective attempt keeps the canonical system
prompt unchanged and places that correction in a server-owned input field,
bound into the request fingerprint and context hash. Later calls contain
only the current definition, selected component capabilities, one analysis and
the latest comparison, plus necessary image attachments. They omit skills/rule
histories, graph rows, repository source and unrelated registries. Every call
preflights bytes before provider admission and persists measured sizes and
attempt counts. Analyze, compose and compare always use `xhigh`; model and effort
are bound into the provider request fingerprint and sanitized invocation
metadata. The bridge must explicitly advertise this optional JSON and multimodal
mode together with `reasoning_efforts.template_creation = xhigh`; existing
required modes retain their current effort and remain compatible without it.
The local Codex provider uses the same server-owned bounded correction field as
the bridge. Both first and corrective envelopes are preflighted before a call
is counted; a rejected first response cannot grow the system prompt past its
6 KiB limit. A contract/preflight failure is distinct from invalid model output
and does not instruct the owner to repeat an impossible request. An in-flight
or failed correction never presents the previous comparison as its own result.

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

The saved owner run `fff155a8-b5c0-4313-a958-18aaf3c9e779` exercised the final
append-only correction recovery against real local Codex. Revision 112 recovered
historical revision 110, and revision 113 prepared its saved four-times-smaller
motifs with fixed rotations `-18°` and `+14°`, official badge asset IDs and the
Pexels fixture. The exact temporary correction reference was recovered with its
original normalized digest `22bdb8fcc059f33d4f7e42ce7272a518ea7ae37a9910fd67a0574884afffe252`.
Revision 124 first reached `proposed` with the registered assets. The owner then
identified that the intrinsic badge images were narrower than their reference
buttons. Declarative renderer v3 now composites contained image artwork over the
component surface, so each `250 × 58` badge slot renders as the complete black
rounded pill. A subsequent real `xhigh` compose and comparison each completed in
one attempt without changing any geometry; only the two badge fills normalized
from `#111111` to `#000000`. Revision 135 is `proposed` with zero differences and
zero geometry failures. Its comparison and preview bind correction
`dcb22b98-ebab-4311-bdb7-f4f3d549d37d`, state is
`935b0cc12c7520c407e7981cc739bc1b93f35de5c894f8643ac182d428b1b8f5`, full
1080×1080 preview digest is
`76c373897ec451d86463e5d8860b0f1f1acfcaff4b080f58d4e6752e5b56ad1b`, and
render contract is
`240fca5bc067aa00049329571929222ee4f0dd570d3370fcdf734ecf7a65e0bc`.
An owner-directed recovery later accepted this exact proposal append-only as run
revision 136 and Post template `design_ee8759d1b6034ee2bffe` v1. The local
SQLite authority and production PostgreSQL now both contain its complete run
history, immutable version and digest-checked PNGs. Source deployment alone does
not carry template records between these authorities; verify the actual API
process/database as well as proposed-versus-accepted status when a design seems
to disappear.

The next local Bokko edit exposed two distinct regressions: the local Codex
corrective attempt still grew the system prompt (unlike the bridge), and the
owner-supplied self-contained badges were painted over an additional black slot
pill. Run `1a760233-32d4-4ec6-a9bf-be453e73ee80` now uses the shared bounded
correction input and the explicit `asset_only` badge mode. Its revision 45 is a
compared proposal with only badge-surface and badge-height changes; its owner
correction history and all earlier PNGs remain append-only. Acceptance and any
production data transfer are separate owner-reviewed steps.

Remaining bounds: galleries/version summaries return at most 200 records and
run history at most 30. Exact historical identity reads remain available.
Accepted Post templates are available in the existing Post editor through
Change template. Initial Brief generation and Landing template selection retain
their established composer definitions.
Source extensions require local owner review. Production inference additionally
requires the companion bridge to advertise `template_creation`.
