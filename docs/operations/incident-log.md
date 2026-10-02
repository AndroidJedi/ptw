# PTW incident log

## 2026-10-02 — Landing composition timeout and older hero editor mismatch

Two of three preserving release attempts reached a 360-second Landing worker
deadline despite near-identical requests completing in 22–40 seconds on other
runs. The successful intervening attempt rolled back after a transient worker
database health probe failure. The accepted release stayed live. The owner also
could not edit the Hero eyebrow on existing v2 App Showcase pages, because that
control belongs to v3. The new candidate reduces the Landing AI contract,
retains strict server validation and the same model, and provides an explicit
JSON backup/restore path from v1/v2 to a private v3 draft. Nine production
Landing backups were exported and checked before rollout; three published v2
pages remain at their URLs. The resolver skills now require contract-size and
worker-health diagnosis, complete private backups, historical reads and fresh
canaries before accepting a preserving release. The audit also found that one
published v2 row belongs to a deleted Project and already returns HTTP 404;
the other two v2 URLs and one older Project Landing return HTTP 200. Keep the
deleted Project boundary unless the owner explicitly requests a change.
Deployment remains pending.

## 2026-10-02 — App Showcase preserving release rejected three times

The first attempt for PTW `4538f9a` rolled back after Landing composition
bridge job 1483 ended `failed`/`TimeoutExpired`. Its accepted source, Validation
and Gateway images and both Hosting versions were verified before one fresh
attempt with the same checked artifacts. The second attempt passed all real
bridge/Daddy and Pexels canaries, but the dependency audit found the companion
worker temporarily `unhealthy`. Its 5-second PostgreSQL health checks had timed
out; it recovered without restart, with empty `/tmp` and zero OOM events. The
deployer restored the accepted service images and marker, and Hosting did not
advance. A bounded two-probe recovery check was committed as `cc4b90d` before
the third preserving attempt. That attempt again stopped at Landing composition:
bridge job 1502 ended `failed`/`TimeoutExpired`. The receiver restored the
accepted Validation and Gateway images, row authority remained unchanged, and
the source checkout was restored under both locks with canonical skill links.
Both Hosting versions stayed exact. The repeated Landing deadline now requires
a reviewed contract repair; no further unchanged provider retry is justified.

## 2026-10-02 — Daddy manual-review release

Deployment completed for PTW `c39bc8e` and companion `06a99e5` under
`daddy-manual-review-20261002-c39bc8e`. The full production bridge, Daddy
scene/render canary, Pexels, dependency and resource audits passed. A late
silent service/image assertion in the preserving wrapper rolled back those
healthy candidate images. The same revision-labelled images were directly cut
over under the maintenance lock after image, readiness and health checks;
Firebase Owner Hosting was published and its live audit passed. The exact late
wrapper assertion is still unconfirmed and should be investigated separately.
The reported Creative was not retried: it remains failed at `asset:scene`, with
all four provider job references and error codes saved for owner-initiated
Retry. No other Post was changed by this deployment.

The first capacity-fix rollout passed image generation and file checks, then
rolled back when its Daddy AI screenshot-review call timed out. Accepted images
were restored; the source checkouts were subsequently reconciled to the
accepted revisions under the maintenance lock. Daddy now stops after required
assets and a deterministic render, recording its digest and layout findings.
AI image analysis and automatic polish are not part of generation or explicit
recomposition; owner review and tuning happen in Studio. Strict PNG integrity,
worker capacity checks and the real bridge image canary remain release gates.
The exact car-sharing Post is still failed pending the compatible deployment;
the owner will initiate any scene Retry. No design or Brief changes are authorized.

The next preserving release rejected structured bridge job 1450 during its
Product Brief canary, before Daddy. The durable job recorded `RuntimeError` after
28 seconds; a schema-bound worker probe exposed `workspace routing discovery
unauthorized (401)` and a refresh token already used. The auth service's
working test failed. A single official device authorization flow was started;
the owner must complete it before canaries can pass. Neither release attempt
retried or changed the reported Post. Per the owner's latest instruction, the
Post will now be left for owner-initiated Retry after deployment.

After the owner completed authorization, a schema-bound worker probe passed.
The following candidate canary completed the normal Daddy composition after
one bounded correction: its first response had an invalid `supporting_text`,
and the second satisfied the validator. The release gate nevertheless rejected
all corrected Daddy responses and rolled back. The Daddy-only canary now accepts
exactly that existing one-correction contract, recording the attempt count;
other structured canaries retain their first-attempt requirement. Image and
render integrity requirements are unchanged.

## 2026-10-02 — Daddy scene PNG truncated by worker tmpfs exhaustion

The diagnostic release passed its real image and Daddy canaries, then one
deliberate Retry of the reported car-sharing Post reached scene job 1434.
The worker's 64 MiB `/tmp` had 36,462,592 bytes free when generation began
and zero when the CLI exited successfully. Its saved PNG is 2,002,944 bytes,
a 4 KiB multiple, and has no IEND. A roughly 30 MiB shared Codex cache and
roughly 34 MiB isolated job home occupied the mount during generation.
The file-save boundary ran out of temporary space; the CLI success signal did
not guarantee complete pixels. The worker's strict validator rejected the
file and retained a root-only diagnostic copy. The Post remains failed at
`asset:scene`, with copy/layout intact and no visual review or approval.
This directly identifies the mechanism missing from the earlier host-disk and
OOM checks. Jobs 1182 and 1347 had the same 4 KiB-truncated signature; their
individual tmpfs state was not recorded, so their precise historical cause
remains an inference.

The capacity repair changes only the worker tmpfs from 64 to 256 MiB, adds a
96 MiB pre-generation headroom guard, and classifies a full temporary store
separately. The image validator remains strict. The next release must pass
two-job worker/resource checks, the real bridge/Daddy canary, affected suites,
Owner browser flows and preservation audits. Only after acceptance may one
UUID-bound Retry resume this exact scene and open a rendered manual-edit draft. Preserve
the old failure receipts, approved Brief and other Projects.

## 2026-10-01 — Daddy scene failed on a truncated completed bridge image

Creative `01a0f720-8768-71f7-ba4e-7e453fbde37d` retained its lifestyle
strategy and composed Ukrainian copy, then failed at `asset:scene`. Job 1347
stored 2,117,632 bytes with an incomplete IDAT chunk and no IEND, while the old
companion checked only the PNG signature/dimensions before marking it completed.
Validation rejected full decoding; ordinary Retry reused the broken cached job.
The visible background was a fallback, and visual polish had never run.

The repair validates structure, CRCs and pixels at the companion boundary and
classifies historical corrupt results in the PTW client. Durable slot attempts
allow one automatic replacement for confirmed corruption; uncertainty retains
the same key. Explicit UUID-bound Retry resumes saved work and is deduplicated.
The UI identifies the missing image and labels incomplete previews. The source
Brief is V2 and supplies the consultation offer; this repair does not rewrite it.
Release and exact-Creative recovery are pending; no approval or reset is required.

Two candidate releases passed the full Daddy production-bridge canary, then
rolled back on Pexels HTTP 500 responses; the standalone photo probe succeeded.
The readiness probe now permits three read-only attempts for upstream 5xx, with
one- and two-second backoff. It still requires a real decoded photo; credentials,
rate limits, malformed images and persistent upstream failures remain blocking.

## 2026-10-01 — Daddy Post strategy recorded as failed after completed inference

Creative `01a0f720-8768-71f7-ba4e-7e453fbde37d` belongs to the reported
Project and remains `failed` at `strategy`, with zero generation-run rows,
assets and approved versions. The independent bridge completed structured job
1307 at 11:02:24 UTC. Read-only inspection found the live
`studio_generation_runs_stage_check` still allows only `composition` and
`phone_image`, while the new Daddy generator writes `daddy_strategy` after
inference and again while recording the caught failure. Migration 022 added the
template but omitted those run stages.

The additive migration 023 admits the finite Daddy stage set. The
disposable database regression exercises each stage, an unknown-stage rejection
and existing-row/file/PNG preservation. The first owner-authorized serial
release applied migration 023 with a checksummed root-only backup and exact
pre-existing-row preservation, then rolled back source, images and Hosting after
a transient Codex Auth health check failed. The migration remains applied by
the additive rollback contract. The next two full release attempts rolled back
before application cutover because the Phone Metrics structured canary needed
a corrective response; both first responses left the second phone-button label
blank. All platform jobs completed, but the release correctly requires domain
validation on attempt 1. The third attempt exhausted the bounded retry for that
canary; its prompt now explicitly requires three nonblank labels, including for
disabled buttons. The next reviewed candidate passed Phone Metrics on attempt 1,
but a separate Landing canary reached its six-minute `TimeoutExpired`; source,
images and Hosting rolled back cleanly. One fresh full attempt passed all eleven
structured/media bridge canaries on attempt 1, Pexels, database preservation,
dependency/resource checks, 153 Owner unit and 156 browser cases, both Hosting
publications and the live authentication/CORS audit. Accepted revision
`82b8216291e0075cc15e6c8ae8158cde1e833391` is healthy on all six services;
the 24-hour resource timer is active. Migration 023 is checksummed in the live
ledger. The reported Creative remains `failed` at `strategy` with zero runs,
assets or approved versions. Its next step is the owner's authenticated Retry
action in the web console; no reset, deletion, approval or new Creative is
warranted.
The complete local release gates passed: 501 Validation, 54 Commander and 21
Gateway tests in the accepted images, 153 Owner and 15 public-shell unit tests,
156 Owner and 60 public browser cases, both builds, the disposable migration
and schema checks, Studio visual audit, skill verifier and whitespace check.

## 2026-09-30 — App Showcase template request stopped during composition

Read-only PostgreSQL inspection of Template run
`3fef5cae-57c1-42fc-85eb-9b6a7ac9f2ae` found a completed analysis followed by
two failed `compose` invocations, each on its first attempt with `gpt-6-astra` /
`xhigh`. The corresponding platform jobs ended with `TimeoutExpired` after about
six minutes each. The run has zero comparisons and no proposal; it remains failed
and resumable. Validation, Owner Gateway, worker and auth containers were healthy
when inspected, which does not prove inference readiness. No retry, acceptance,
template-authority write or production code change was made during diagnosis.

The requested reusable Hero controls were absent from the native App Showcase
definition: its eyebrow was hard coded and its body had only supporting text.
The local repair adds v3 with an editable eyebrow, three distinct bullets and a
text/bullets switch, preserving exact v1/v2 references. Template Creation guidance
now separates provider timeouts before comparison from capability gaps. The local
v3 implementation is tested but not deployed; the failed production run is not
silently converted into an accepted template.

## 2026-09-29 — Landing copy-only Agent rejected its own context

The owner's Ukrainian copy-improvement request failed during interpretation,
before any image job or result existed. Read-only production inspection found
two recent operations with `ValueError`, category `validation`, and retry disabled.
Rebuilding the latest operation's provider envelope without submitting inference
proved the cause: 21,354 B input exceeded the 20 KiB limit, and 33,979 B total
exceeded 32 KiB. The 295-character instruction itself was valid. The generic
dialog incorrectly asked the owner to correct it and described nonexistent
completed images.

The fix compacts Landing component semantics and the canonical shared
Manual Agent skill while preserving all editable copy and validation boundaries.
The first compact revision built a 19,209 B input / 30,146 B total contract.
At the owner's request, both editing surfaces now load the full approved source
Product Brief from their immutable lineage, pin its ID/canonical document digest,
and exclude raw-idea, audit and graph data. Explicit owner instructions and
current draft choices take precedence; the source Brief remains read-only
hypothesis context. Nested editable values preserve every leaf and array index
without repeated parent paths, retaining the original output path allowlist.
The frozen input with its full Brief now fits at 18,337 B input / 29,536 B total.
Landing and Post reserve 1 KiB for one corrective
response, keep the system skill unchanged, and bind the bounded server-owned
hint into the context digest/fingerprint on both bridge and local transports.
The skill verifier enforces a 5 KiB maintenance cap.

Provider output rejection is now a sanitized service failure on both surfaces;
oversized server envelopes have a separate non-retryable service-contract
category. Invalid editor input still fails its existing guard. The dialog
explains historical interpretation failures without blaming the owner and
reports retained completed images only when they exist. The canonical Manual
Agent skill records this diagnostic and copy-only behavior. Production source,
operations, drafts, images, approved versions and publications were not changed.
Local verification evidence is in `.local/agent-copy-recovery/`.

Verified locally: 463 built-image backend checks, 143 Owner unit checks/build,
nine focused API-mocked browser cases across desktop/360px/iPhone, native mobile
dialog inspection, 54 Commander checks (seven local dependency skips), demo,
canonical skills and whitespace. The real service envelope tests exercise
Landing, Phone Metrics and authored Post copy with full Brief context, unsaved
values and the corrective attempt without saved-state mutation. A later Project
Brief does not replace a draft's source Brief.
The owner-authorized selective release `studio-brief-context-20260929-f20b4ea`
is deployed at `f20b4ea58bb8de7e7da41c16e43d4eae5beea53d`. Only Validation
and Owner Hosting changed; other service images and public Hosting were retained.
All 11 live provider canaries, Pexels, exact database-authority comparison,
service/resource and approved-Post audits passed. The exact release checkout
passed 143 Owner unit tests/build and all 141 desktop/360px/iPhone browser cases.
Owner Hosting `18f60d15da474826` passed the live auth/CORS/bundle audit.

The separate desktop CLI replay timed out at its existing 420-second deadline
and left the temporary draft unchanged. A subsequent real `gpt-6-astra` / `high`
request through the deployed bridge used the candidate full-Brief envelope and
passed on attempt 1. Production's own Landing validator accepted two hero copy
edits and zero image actions; the saved page's complete detail remained identical.
Only the bridge's normal inference job was created. No PTW operation, checkpoint,
version, approval or publication was written, and no runtime source was changed.
The current accepted authored Post also passed a real full-Brief `gpt-6-astra` /
`high` call on attempt 1. Its candidate contract fits at 7,489 B input / 14,347 B
total. Deployed validation accepted title/support copy edits and zero image
actions, and the complete saved Post detail stayed identical. Both checks used
temporary workspace hydration and the existing bridge credentials at runtime.

After acceptance, fresh calls through the deployed Landing and authored Post
services verified automatic full-Brief context, canonical document digests and
every allowed editable leaf. Both completed on attempt 1 with copy-only edits,
zero image actions and identical saved draft detail. Their contracts fit at
28,808 B total (Landing) and 14,322 B (Post). No migration, reset, PTW operation,
checkpoint, version, approval or publication was created by these checks.
Evidence: `.local/agent-copy-recovery/deployed-brief-canaries.log` and
`.local/ptw-combined-release/.local/studio-brief-release.log`.

## 2026-09-29 — Domain feedback copy incorrectly removed its section

The shared renderer correctly stopped displaying unrelated rental testimonials,
but interpreted missing verified proof as permission to remove the owner's
requested feedback section. The owner clarified that its copy must be adapted
to the Water product while preserving the cards.

The correction separates verified customer quotes from labelled illustrative
expectations. Three editable bounded example cards remain visible for early-stage
products, with a legacy fallback to their own feature copy and an explicit hide
control. There are no invented names, ratings or past results. Water's reviewed
examples cover comparing labels, understanding composition and choosing by
taste/mineralization. A named, digest/UUID-bound publication helper retains the
original draft, versions and artwork; it never rewrites approved snapshots.

Template/composer/Manual Agent skills now require preserving the section during
domain adaptation. The VPS skill documents compatible-code-first deployment,
read-only review and the normal Save/Approve/Publish route. Canonical prompt
budgets remain unchanged; skill verification and correction-budget checks pass.
The preserving application release passed all 11 structured/media canaries,
Pexels, unchanged authority and dependency/resource audits. The owner-authorized
named publication then created a replacement approved version through normal
Save/Approve/Publish. The original draft/version, all artwork and other Project
Landings are preserved. Real desktop/360px/iPhone browser checks verify the three
exact Water examples, explicit labels, all five alpha dialogs, accepted Natal
events and new public image bytes matching the original selected digests.
Other page copy, settings and the exact template identity are unchanged.

Owner Hosting stayed withheld after the unchanged iPhone Commander screenshot
attachment test failed intermittently. Commander source/tests match the accepted
baseline; delayed initial chat installation can clear pending images. The focused
three-device recheck and complete 138-case rerun passed in the same clean, pushed
release checkout, before finishing its remaining Owner Hosting/live-audit steps.
No test or application gate was weakened or bypassed.

The first Owner Firebase upload reached finalization but its HTTPS request failed
at the transport layer before a release was created. The unchanged-source retry
finalized and published successfully. Owner Hosting is `26f5bac301a70154` and
public Hosting is `085a88ff58d3858e`; the live Owner audit verifies the current
bundle and auth/CORS boundary. No application source or tests changed on retry.

An initial audit incorrectly fetched prior public asset URLs after publication
moved; those URLs correctly returned 404 at the active-version boundary. The
audit now compares new public bytes to the original selected hashes, alongside
the helper's retained private-version checks. VPS guidance records that boundary.
No production asset was lost or rewritten.

Updated: 2026-09-29

## 2026-09-29 — Landing correction exhausted the prompt budget during release

The owner authorised deployment of all reviewed Landing and authored Post Agent
changes. The first combined preserving candidate passed 450 backend checks,
21 Gateway checks, both web builds and 138 Owner/60 public browser cases.
After the public shell was published and both APIs became healthy, the live
Landing composition canary rejected its first completed response. Its 8,144-byte
canonical skill left insufficient room for the bounded correction under the
unchanged 8 KiB mode limit; the second job was rejected before submission.

The normal guard restored both prior API images and verified unchanged database
authority. The manual publisher had already advanced its source checkout and
public Hosting. Under both maintenance locks, recovery restored the accepted
source and hosted checkout, canonical skill links/permissions and both accepted
Hosting versions using the accepted recovery helper. The deployed marker stayed
at the prior accepted revision and every service was healthy.

The Landing skill was compacted without removing its exact-content, evidence,
contact or visual boundaries. A 7 KiB skill-maintenance cap and a canonical-prompt
invalid-first/valid-second bridge regression now protect correction headroom.
The VPS skill also requires source/Hosting recovery after manual partial release;
image health alone cannot prove complete rollback. Runtime byte limits, models,
validators and first-attempt canary acceptance remain unchanged.

The corrected combined preserving release completed all 11 live canaries on
their first attempt, Pexels, dependency/resource and complete database-authority
preservation checks. The final local Owner gate had one intermittent desktop
screenshot-attachment failure; a focused recheck and the full 138-case suite
passed before the remaining Owner Hosting publication and live audit. Both web
shells, Validation and Owner Gateway are now deployed; every other application
image and the independent platform were preserved. Live desktop/360px/iPhone
Landing checks passed without storing inquiry contacts. Actual Natal events were
accepted, Meta SDK/configuration loaded and an iPhone beacon was observed; Meta's
automation filter prevents proving receipt in some headless browsers. Existing
published content, configuration, artwork and template identities are unchanged.

## 2026-09-29 — Full VPS caused widespread health failures and Owner 401s

The owner completed Google sign-in but Project and Landing template reads still
returned HTTP 401. The 24 GB root filesystem had zero available bytes, all 12
containers were unhealthy, and their healthcheck execution reported
`no space left on device`. Daily recovery copies occupied 7 GB and journald
about 2 GB. The legacy retention glob expected ten date digits instead of the
actual eight, so it matched no recovery directory. Cleanup was also conditional
on a successful backup; the final failed gzip attempt could not reach it.

Maintenance first enumerated all container image references and removed only
unreferenced images under the shared lock. This reclaimed just 53 MB, proving
image cache was not the accumulating source. Services recovered without any
application restart, Firebase owner lookup and key retrieval passed, and the
owner confirmed that the actual Landing opened after refresh. All 12 services
became healthy; the accepted application revision and Hosting were unchanged.

The owner explicitly requested recurrence prevention and skill updates.
`scripts/install_ptw_storage_guard.sh` installed the canonical root-owned
backup writer, replaced the obsolete checkout-based cron, enabled a persistent
15-minute storage guard, capped journald at 256 MiB with a 3 GiB keep-free
reserve, and added backup-log rotation. Retention keeps at most seven complete
copies within 4 GiB, verifies the newest two replacements before deletion and
preserves incomplete or symlinked records. Streaming exports enforce both
free-space and replacement byte budgets; failures remove only their own staging.
Low headroom or oversized protected recovery points fail visibly rather than
consuming the reserve. The pre-existing failed copy remains incident evidence.

A real new recovery copy contains the current complete PostgreSQL dump and
historical assets volume, accepted-revision metadata and a SHA-256 manifest.
The manifest, `pg_restore --list`, archive listing and private file modes passed.
Post-backup free space remained about 5 GiB. Timer enablement/next-elapse,
successful retention service, installed-script digest, all container health,
the quick dependency audit and public Owner auth/CORS/Hosting audit passed.
No domain row, credential, application image or publication was changed.

Verification: 54 Commander checks (five isolated receiver skips), 20 Gateway
tests, 12 focused built-image checks, Commander demo, canonical skill verifier,
both changed skill validators, Python compilation, shell syntax and whitespace.
The image-wide command also exposed its existing missing `git` dependency;
those Git-dependent cases passed in the local virtual environment, while the
FastAPI/storage cases passed in the image. Canonical Owner incident and VPS
skills now route this misleading 401 to storage diagnosis and require the
writer/retention/timer repair before closing recovery.

## 2026-09-28 — Policy links reached the public shell's visual 404

App Showcase's shared policy links were implemented locally but absent from
the deployed public shell. All three `/legal/*?lang=en` requests returned HTTP
200 while Chromium rendered **Page not found**. Checking only status codes or
local hrefs would have incorrectly reported working policies.

The owner-authorised preserving release published both web shells, with every
backend image reused, no service restart and no migration. It passed 129 Owner
and 19 public unit tests, both builds, 135 Owner and 56 public browser cases,
Commander checks/demo, skills and dependency/resource/auth/CORS audits. Twenty
live-origin checks verified the deployed renderer with mocked Landing snapshots
and actual bilingual policy documents. The real published `/water-quality`
Landing passed desktop/360px/iPhone WebKit checks without mocked traffic: its
benefits auto-scroll with zero navigation/playback buttons, its two store links
remain, and all three footer policies open actual documents. Publication digest,
exact template reference, settings, copy and selected asset URLs were unchanged.
Explicit owner policy URLs and the incomplete profile's draft status remain.

The canonical Studio visual-audit skill now requires actual footer clicks,
rendered document headings and a separate public-origin probe; HTTP 200 and local
routing alone do not prove deployment. Evidence is in
`.local/landing-auto-policy-release/.local/`.

## 2026-09-28 — Fixed benefit boxes produced uneven text and repeated marks

Independent benefit boxes shrank longer text and kept following items at fixed
positions. Dense repeated Natal motifs added more background marks than the
owner wanted. The owner requested equal benefit font sizes, wrapping with a
hanging bullet indent, equal spacing, and three smaller scattered marks.

Bounded template `text_groups` now share font controls and use the renderer's
actual text measurements to wrap and place following benefits. Template-owned
bullets keep continuation lines indented, and empty benefits consume no space.
Documents without groups keep their existing rendering. The immutable v5 Natal
template replaces the repeated regions with three individual small marks.
Project geometry remains advisory as requested in the preceding incident.

The preserving release passed 441 backend tests, 129 Owner unit tests, 132
desktop/mobile/WebKit browser cases, all eleven real provider canaries, Pexels,
and deployment audits. After a root-only checksummed PostgreSQL backup, normal
append-only Template Authoring acceptance and the Project apply API selected v5
for Creative `01a0dda1-04e1-722a-a8c2-6eb3edfbf6f6`. Existing text, settings,
assets, history and the one approved version were preserved; no Post approval
or publication ran. Unrelated application fingerprints across 72 tables were
unchanged. The live PNG matched the reviewed exact-image PNG byte for byte.
A guarded Validation restart preserved all 72 table fingerprints, Post state,
PNG digest, version history and accepted template reference.
The public Owner Console audit also passed after restart.

The canonical Template Creation and local Studio tuning skills now document
shared-size wrapping, hanging bullets, blank-item flow and the owner's sparse
motif request. Canonical skill verification passed.

## 2026-09-28 — Project Post overflow blocked the owner's preview

The authored water Post returned HTTP 400 with "Post text does not fit this
template" because Project rendering treated geometry findings as a blocking
template-quality failure. The owner requested direct visual review and a third
benefit position. Project Post layout findings are now advisory for preview,
Save and explicit Approve; schema, bounds, integrity and stale-state guards
remain enforced, as does the separate global Templates quality gate.

The preserving selective release changed only Validation's application image
and Owner Hosting, without migrations. All eleven real provider canaries,
Pexels, authority-preservation and deployment audits passed. An intentionally
overflowing live preview returned HTTP 200 without changing saved state or
approved versions. The exact image passed 437 Validation tests; the Owner suite
passed 128 unit and 132 desktop/mobile/WebKit browser cases.

After a checksummed root-only PostgreSQL backup, normal append-only Template
Authoring acceptance registered v4 and the Project apply API selected it for
Creative `01a0dda1-04e1-722a-a8c2-6eb3edfbf6f6`. Only `benefit_tertiary`
was added, initially empty. Existing copy/settings, images, history, the one
approved version and all unrelated application fingerprints across 72 tables
were preserved. No Post approval or publication ran.
A guarded Validation restart preserved the exact Post state and preview PNG
digests, version history and all 72 table fingerprints. The exact-version and
Studio catalog reads passed, and the public Owner audit passed again.

Registration initially rejected a desktop-generated renderer-contract digest
before any authority write. Preparing and reviewing the same components in the
exact deployed Linux image passed the unchanged guard. The canonical Owner
Console incident skill records advisory Project geometry, immutable benefit
revisions and exact-renderer registration; the local Studio skill preserves the
owner's preview decision and existing copy.

## 2026-09-25 — Landing performance release recovered after provider timeout

The paired migration-aware preserving release's first provider suite stopped at
Landing composition: bridge job 1144 reached terminal `failed`/`TimeoutExpired`.
The worker stayed healthy with no OOM indication. The tracked deployer restored
the accepted application/companion images, source revisions and Hosting, and the
hotel's public snapshot remained byte-for-byte identical. No Project application
was changed and the migration had not started.

After bounded status and rollback verification, one fresh full attempt passed all
eleven provider canaries, Pexels, migration row-preservation, dependency/resource
audits, and the full Owner browser suite. Model, reasoning and image quality were
unchanged. The owner-authorized hotel-only refresh then preserved copy/settings/
source PNGs, reduced display bytes by 91.65%, and left all other application
fingerprints unchanged. Live delivery and a guarded backend restart passed.
The VPS skill now records structured-timeout reconciliation and complete rollback
verification before the single fresh release attempt.

## 2026-09-22 — Template Creation correction exceeded prompt budget

The coupled in-place release passed its provider, Studio and media canaries,
preserved production rows, and deployed the two requested Owner accounts across
Gateway, Hosting and Firebase blocking functions. A subsequent real Template
Creation analysis job completed, but PTW rejected its component selection. The
provider tried to append the bounded domain error to the near-6 KiB canonical
system prompt, exceeding that prompt's budget locally before a second job was
queued. This was a retry-contract defect, not a bridge outage or lost reference.

The hotfix keeps the canonical prompt fixed, carries the bounded correction in
server-owned input context, reserves input/total budget on attempt one, and
includes the corrected payload in context and idempotency fingerprints. A focused
regression covers a near-limit prompt and completed invalid-first/valid-second
responses. Release acceptance requires a fresh production Template Creation
canary.

## 2026-09-22 — PTW candidate rolled back after bridge readiness failure

The owner-authorized mobile release passed its CI suites and migration rehearsal.
Production applied additive migrations 012–014 and verified preservation of
existing business rows, then replaced the application containers. A readiness
probe failed after their Docker health checks became green. The receiver
restored the accepted PTW source and application images and restored the prior
Owner Hosting version. Firebase auth-guard functions were not deployed, so the
two requested accounts do not yet have complete production access.

The candidate Validation contract requires `studio_manual_edit` and optionally
`template_creation` with `xhigh`, while the unchanged companion platform
advertises neither mode. The mobile publisher always reuses platform images,
so that channel cannot deliver this coupled release. A compatible platform
API/worker change was later deployed in a serial in-place release with both
repositories and successful live bridge canaries. The VPS operations skill
records this preflight.

## 2026-09-16 — First Brief creation on an empty Project returned HTTP 500

Creating the first Product Brief for an already-created empty Project returned
HTTP 500. Read-only production checks showed every application and provider
service healthy, no OOM event, no active mutable operation, and the Project
still had no source and no Briefs. Validation logs identified the PostgreSQL
trigger rejection: `immutable Validation Project fields cannot change`.

The baseline Project trigger incorrectly treated `owner_idea_source_id` as
immutable even for the required first attachment performed atomically with the
first Brief. The transaction rolled back before creating any source, Brief,
relationship, or generation job, so this was not a bridge/provider incident and
there is no authority repair or cleanup to perform.

The pending additive migration replaces only that trigger function. It permits
the single `NULL -> source UUID` transition needed by first-Brief creation and
continues to reject source replacement/removal and every other protected Project
field. The disposable PostgreSQL schema check proves both cases, the migration
runner proves idempotency and checksum enforcement, and an isolated real
ValidationRepository flow creates the first source and queued Brief correctly.
The canonical Owner Console incident skill now routes this symptom to trigger
diagnosis rather than provider recovery. A backup-preserving in-place release
is required before the owner retries the unchanged Project.

## 2026-09-16 — Mobile release exhausted disk while ingesting a candidate image

The first release of PTW revision
`57332cbb949a28c0a95bfff2ee14e2356d674137` passed every CI, migration,
browser, and isolated recovery gate, then failed while containerd ingested a
verified image archive. The 24 GB VPS had accumulated 478 tagged image
references; ordinary dangling-image and builder-cache pruning reclaimed nothing.
The receiver reported `no space left on device`, restored accepted PTW source,
all prior service images, skills, and both Hosting sites, and left the deployed
revision at `816e9bf8c5f3743bdb54eac4b9003b4cb1bd8b67`. Migration `010` had not
started and the database ledger remained at nine migrations.

Under the maintenance lock, `docker image prune -a --force` removed only images
unreferenced by any running or stopped container. It reduced the inventory from
478 references to the nine container-retained images, reclaimed 3.578 GB of
unique layers, and left roughly 11 GB free. No volume, database data, current
accepted image, or container was removed. The failed publish job was then rerun
against the same immutable CI artifacts. Its backup-preserving migration
rehearsal and live application installed migration `010`, preserved all prior
business rows, retained the root-only backup, passed the real provider, Pexels,
approved-Post, resource, bot-identity, Hosting, and public audits, and accepted
the revision with about 8.5 GB free.

Post-release checks matched production source, the deployed marker, GitHub
`main`, and the feature branch to the accepted SHA. All application and companion
services were healthy, the new Project-default table existed with zero rows, and
the live Owner Console audit passed. A real private GOD chat performed a harmless
Git read, persisted across a locked restart of only `commander-god`, and a live
branch-publication smoke test succeeded without deploying.

## 2026-09-14 — Website deployment reached image upload and stopped at Creative

The owner's corrected Website request created and retained PAUSED Campaign
`120251775220490671`, PAUSED Ad Set `120251776379740671`, and the exact approved
image hash, then stopped before Creative and Ad creation. Deployment
`01a09f65-28e3-7163-80b6-2b9a89471bb4` stored HTTP 400/code `100` from the
Ad Account `adcreatives` reconciliation read. A read-only production
differential proved Campaign, Ad Set, and Ad exact-name filters return HTTP 200,
while the same filter on `adcreatives` returns HTTP 400; the unfiltered Creative
edge returns HTTP 200 and contains no matching PTW name.

The correction scans bounded Creative pages and matches the complete immutable
PTW name client-side, following only opaque cursors so Meta's credential-bearing
next URL is never reused or exposed. Production-like adapter tests now make a
server-side Creative filter fail and cover later-page reconciliation plus the
complete Website Campaign → Ad Set → approved image → Creative → PAUSED Ad
path without duplicate provider writes.

An exact non-mutating `validate_only` request for the saved Creative payload
then exposed the independent provider gate: HTTP 400/code `100`, subcode
`1885183`, classified from Meta's bounded fields as the issuing app remaining
in Development mode. PTW now maps that subcode to the precise App Dashboard →
Live instruction, shows it even for the already-persisted failure, and replaces
the generic retry label with an explicit post-Live retry of the same deployment.
That retry will reuse the saved Campaign, Ad Set, and image. Real Creative/Ad
completion remains blocked until the owner changes **PTW Local Ads** to Live;
no retry, activation, spend change, or duplicate Meta object was performed
during diagnosis.

The preserving release accepted PTW revision
`31ff9ab127f610000c2766a96dcdfb8824a97a20`, Validation image
`meta-creative-recovery-20260914-9ca2243`, and Firebase Hosting version
`176cfad6c2db2878` with Owner cache v14. The backend passed all 281 tests in the
real Linux/amd64 Validation image plus the live bridge/media and Pexels canaries;
the Owner Console passed 104 component tests and all 87 desktop/mobile/WebKit
browser flows. A compatibility guard recognizes the exact legacy saved
reconciliation error even though its persisted provider context predates the
later `1885183` validation, so the current deployment shows the Live-mode action
without mutating history. Post-release reads confirmed exactly three stage
records, zero retry/control records, no Creative/Ad ID, and provider status
`PAUSED`/`PAUSED` for both saved parent objects.

## 2026-09-14 — Meta Ads request appeared to loop and created only a Campaign

The owner clicked `Create PAUSED campaign structure` for a Website ad and saw
repeated Project workspace requests without nearby completion or failure
feedback. Ads Manager showed a generic `New Traffic Ad` with no image or Website
URL. The staging POST did return HTTP 202 and persisted its immutable request,
but the latest deployment failed while creating the Ad Set. PTW created one
PAUSED Campaign and no Ad Set, image hash, Creative, or Ad; the approved render
and frozen Landing URL remained present in PTW authority.

The provider failure was Meta HTTP 400, code `100`, subcode `1885272`. The saved
preset used `200` UAH minor units (₴2.00), while the live Ad Account exposed a
minimum of `4491` (₴44.91). Exact non-mutating `validate_only` calls against the
same Ad Set shape failed below `4491` and passed at `4491`. Because execution
stopped before image upload, the blank generic Ads Manager draft was unrelated
to the PTW lineage and could not contain the approved image or Landing URL.

The apparent loop was a separate client defect. The Project workspace took
roughly 2.4–7.8 seconds while the UI started another request every 2.5 seconds;
each new request invalidated the prior response, so terminal status could be
discarded indefinitely. Production logs showed 115 successful CORS preflights,
five successful workspace GETs, and one successful staging POST in the observed
window.

The deployed correction serializes polling, coalesces same-Project refreshes,
accepts completed responses, and reuses the verified connection during quiet
polls. It keeps the latest result visible at the top, collapses healthy setup
diagnostics, reviews the selected image/Landing/audience before the click, and
shows Campaign, Ad Set, image, Creative, and Ad as five visible steps with one
next action; technical IDs and digests remain available secondarily.
It reads the account's live minimum, labels currency and minor units, blocks a
low preset before reservation, offers a new compliant immutable preset, maps
subcode `1885272` to that safe action, and suppresses unchanged retries. Exact
Meta links now select the deepest created PTW object instead of opening only a
generic manual workspace. Full affected domain/Gateway/Commander/web suites,
all 84 desktop/mobile/WebKit flows, both disposable database journeys, the Owner
build, and skill/compile/whitespace checks pass.

The first preserving pass accepted the Validation image after nine fresh bridge
and media canaries plus Pexels, dependency, resource, authority, and approved-
Post checks, but correctly withheld Firebase Hosting when the full Ads browser
test retained an obsolete blocked-setup heading. The follow-up keeps unavailable
setup expanded as **What is still needed** while healthy setup remains collapsed
as **Meta setup**. The complete browser gate passed and Owner Hosting version
`66a5b23c6fa82191` is live with cache v11. Live bundle, Gateway, authentication,
private-route, and CORS audits pass. The accepted revision is `bb51985`; all
three historical deployment rows predate the release, the existing Campaign
remains PAUSED, no Ad Set/image/Creative/Ad exists for the latest request, and no
retry, control action, activation, data deletion, or spend change occurred.

## 2026-09-13 — Performance-learning schema rejected before model execution

The first Analytics/Creative Skills rollout reached the fresh companion bridge
canary but failed its performance-learning request before any PTW migration or
application cutover. The outer rollback restored prior platform images, but the
old Validation image initially became unhealthy because candidate source had
removed the retired mounted learning skills it expected. Bounded recovery
restored accepted PTW/platform revisions and accepted skill links before
restarting Validation, then restored both Firebase sites. All prior services
were healthy, the migration ledger remained at six, and the failed bridge job
was retained as append-only evidence.

The exact local Codex CLI boundary reproduced the cause: the new strict output
schema left nested target, evidence, and confidence objects open, which the CLI
rejects before inference even while authorization and ordinary health checks
pass. The schema now closes every object recursively, enumerates the bounded
target variants, and has a regression requiring declared properties and
required fields to match at every object depth. The performance learner skill
documents the exact closed evidence/confidence shapes. Release cleanup now
restores accepted source and skill links before prior images, and the serial
publisher snapshots accepted Hosting versions before changing the public shell.

The single corrected retry passed the exact CLI probe and all nine fresh bridge
canaries on attempt 1, applied additive migrations 007 and 008, preserved every
pre-existing Commander business row and five immutable approved PNGs, and left
all six application/bridge services healthy. Local and Linux/amd64 verification
passed 276 Validation, 40 Commander, 14 Gateway, 45 companion-platform, 101
Owner unit, 84 Owner browser, and eight public Landing unit tests plus builds,
the Commander demo, migration rehearsals, skill checks, live web audits, Pexels,
authorization, dependency, and 1 GB resource checks. One real cookieless Landing
view and one existing Instagram insight appeared in Analytics; publication,
Meta deployment/control, and stage counts were unchanged, so no post/ad was
created or changed and no spend occurred.

## 2026-09-11 — Unified workspace controlled-release acceptance

The unified Commander bootstrap is live. Hosted native dialogue, questions,
steering, model/effort changes and restart persistence pass. The controlled
chat deployment preserved the owner's earlier Phone Metrics edits and exposed
three release-boundary defects: disposable PostgreSQL readiness could precede
target database creation; an inventory helper inherited and consumed the binary
artifact stream; and rollback Git checkout reset group-write permissions on
changed skill files. The candidate now uses a real target-database TCP query,
reserves artifact input on a separate descriptor with helper stdin closed, and
repairs/verifies accepted skill permissions before recovery service restart.
The stream fix was installed through the owner-authorized receiver bootstrap,
with its prior entrypoint retained for recovery. Candidate host helpers and Git
hooks cannot replace accepted recovery authority before acceptance.

The latest controlled release passed CI and reached healthy service cutover,
then stopped on structured bridge job 718 (`RuntimeError`, eight seconds).
The worker retained only the bounded error type, so its underlying provider
cause is not established. The receiver durably recorded `rolled_back` and
restored accepted revision `3c06ee8`, component images and Hosting. Credential
handoff equality, authorization verification and a fresh schema-bound worker
probe subsequently passed without a new login. Full provider acceptance is
being rechecked before retry; no production data reset or credential rotation
was performed. Release completion is not yet claimed.

A subsequent retry readiness check exposed depth-one hosted checkout refresh:
the candidate commit remained present but Git no longer recognized its accepted
ancestor after rollback. Preparation now retains complete history and upgrades
clean legacy shallow clones. A real disposable-Git regression verifies ancestry
after refresh, complete fresh clones and preservation of unfinished owner edits.
All nine fresh structured/media canaries subsequently passed as jobs 719–727;
no authorization change or provider-code change was required.

The next chat release passed every CI gate but was rejected before rollout by
the maintenance lock while a separate owner-directed Meta LPV release was in
progress. Its artifact verification passed; exit 73 applied no source or data
changes. The Commander candidate now preserves that parallel source through a
clean merge and will be frozen only against the newly accepted production base.
The combined web checks and all 21 focused Commander/Phone Metrics browser
flows pass. Owner cache v9 forces installed consoles to pick up the final UI.

The following combined release passed every CI gate and reached healthy service
cutover, but its GitHub publish job was externally cancelled while the receiver
was active. Termination correctly entered recovery, but the new permission
check invoked the verifier from the archived snapshot; because that directory
is not a Git worktree, verification stopped before restoring images and Hosting.
The retained snapshot was intact. A bounded recovery first proved both index
and worktree exactly matched accepted revision `96abe02`, moved only the
detached HEAD reference to that already-present tree, then restored and verified
all prior images and Hosting. The recovery helper now invokes the verifier from
the restored accepted repository, with a regression. No data or credential was
changed.

The next retry passed all CI checks and stopped during artifact receipt with
`ENOSPC` while loading the GOD image. Its rollback completed normally and left
accepted revision `96abe02`, all prior images and Hosting healthy. The host had
673 MB free after accumulated failed-release layers. Maintenance reclaimed 1.4
GB of unused builder cache and dangling layers, leaving 2.4 GB free; no tagged
image, volume, database, credential or conversation state was removed. The
tracked receiver now performs that bounded reclaim under its maintenance lock
before reading image artifacts, and regression coverage forbids all-image or
volume pruning.

After storage remediation, the next rollout loaded and started all candidate
images, and every structured/media canary completed, including enhancement.
The CI-to-VPS SSH session then broke after nearly five silent minutes, before
Hosting/infrastructure acceptance, causing another rollback. The accepted
marker remained `96abe02`; the retained snapshot restored the clean accepted
source, prior images and Hosting. The publisher now sends 15-second SSH
server-alive probes with a bounded 40-miss window and TCP keepalive. Canaries
remain mandatory; the keepalive fixes transport silence instead of weakening
acceptance.

Protocol keepalives alone did not satisfy the CI channel: the next rollout again
completed all nine provider jobs but disconnected at the same five-minute silent
boundary before scoped-canary completion. Recovery restored accepted source,
images and Hosting. The selective deployer now emits only a fixed, non-sensitive
20-second progress line while the unchanged structured/media canary runs,
propagates its exact exit status, and stops/reaps the heartbeat afterward.

That candidate-side heartbeat could not protect its own first rollout because
the preserving receiver correctly executes deployment machinery from the last
accepted revision until acceptance. Its rollout therefore reached the final
media enhancement job and the outer SSH channel again broke at five minutes;
bounded recovery restored revision `96abe02` and prior images/Hosting. The CI
publisher now emits the same fixed 20-second heartbeat locally for the entire
SSH transport, independently of which accepted receiver version is running,
and still propagates the SSH pipeline's exact failure status.

The accepted request branch also correctly retained the previous publisher, so
the next self-update could not install that outer heartbeat through its own
workflow. The documented preserving operations bootstrap deployed the exact
candidate instead. All nine fresh provider canaries, remaining production
audits, 95 Owner tests, 81 browser flows, Firebase publication and the live web
audit passed; production accepted `317dfc0` and canonical `main` was promoted to
the same revision. Release reconciliation now recognizes this exact externally
accepted and promoted candidate even if its earlier CI attempt is terminal.

The first normal GOD follow-up proved that the new outer heartbeat remained
visible and that GOD, Plan and release-controller candidate containers became
healthy. Its audit then rejected the release because merging a changed skill
reset that file to Git mode 0644 before the group-write verifier ran. Rollback
restored the accepted images and source. The selective deployer now invokes the
accepted skill installer after candidate cutover and before dependency/skill
audits, so candidate skill files regain their required group permissions without
executing candidate control code before acceptance.

## 2026-09-11 — LPV rollout rejected by media enhancement canary

The first preserving rollout of the Meta landing-page-view automation passed
preflight and started a healthy candidate Validation container, but the fresh
external image-enhancement canary returned a bounded `failed` state. The tracked
deployer rejected the release and restored the prior Validation image. The
authoritative deployed revision remained unchanged and the restored container
was healthy; no Meta campaign was created or activated. A single fresh full
preserving retry is allowed only after that rollback proof, with the same
provider canary retained as a release gate.

The bounded retry subsequently passed all provider checks and was accepted at
revision `96abe02`. Validation and the platform worker are healthy. Commander
release work now uses that revision as its accepted base, preserving the LPV
changes rather than overwriting them.

## 2026-09-11 — Saved Meta secret was unreadable inside Validation

After the hidden-prompt configurator succeeded, a Validation restart still
reported `configured: false`. The root-owned host secret existed with the
intended mode 440 and group 10001, and the directory mount pointed at the same
inode, but the Validation image's service user had primary group 999. It could
not traverse the mode-750 secret directory, so the file appeared absent to the
application. The image now creates the service user with explicit GID 10001,
and the release contract binds that identity to the configurator's ownership.
The Linux/amd64 candidate reports identity `10001:10001`, reads a synthetic
root-owned mode-440 secret through the intended directory permissions, and
passes all 11 Instagram publication plus both configurator tests. The saved
token remains intact and does not need to be entered again. Preserving release
`84dfd6a` restarted only Validation and passed all provider, resource, authority,
database, and approved-asset checks. The live process runs as `10001:10001`, can
read the mounted secret, and reports `configured: true`, `verified: true`, and
`media_ready: true` for Instagram actor `17841468586410037` / `natal_service`.

## 2026-09-11 — Curl expanded Meta nested fields after Page discovery rollout

The first Page-discovery correction still reported that the professional
Instagram account was not linked. The Page match had succeeded, so the failure
was narrower than token or assignment validity: curl interpreted Meta's nested
`instagram_business_account{id,username}` field expression as URL glob syntax
and issued expanded requests. Those responses retained the Page but omitted the
linked-account object. The configurator now disables curl URL globbing, and its
network-boundary regression requires that option. No secret was written by the
failed attempt, and the owner does not need another token or Meta configuration
change. All 231 Validation tests, 24 Commander checks plus the demo, canonical
skill validation, shell syntax, compilation, and whitespace checks pass. Both
configurator tests also pass in the actual Linux/amd64 Validation candidate
image. Preserving release `dff9d6d` completed in 41 seconds with no service
restart; all audits passed, the deployed helper contains `--globoff`, and the
production secret was still absent at that checkpoint pending owner entry.

## 2026-09-11 — Valid Meta system-user token failed organic Instagram setup

The owner generated a fresh Meta system-user token after assigning the Natal
Facebook Page, professional Instagram account, and PTW app. The hidden-prompt
configurator still returned Meta HTTP 400 and wrote no production secret.
A token-safe `GET /me/accounts` succeeded and returned Page
`1337006432822527` linked to Instagram actor `17841468586410037`, proving the
token and asset assignments were usable without disclosing the token.

The organic-only configurator and runtime connection check then performed a
direct `/{page_id}` read. Meta rejects that form for this system-user token even
though the supported Page-discovery response contains the exact Page and linked
Instagram account. The committed example also retained obsolete Page ID
`61593990040727`, which made the generic failure harder to isolate.

The prepared fix uses `/me/accounts` for both hidden-prompt configuration and
runtime binding verification, matches the configured Page and username exactly,
adds `pages_show_list` to the organic permission contract, corrects the example
Page ID, and preserves the six-key secret-file boundary. Regression coverage
uses the exact successful discovery response shape and rejects an unassigned
Page without writing a secret. All 231 Validation tests, 24 local Commander
checks plus the demo, canonical skill validation, shell syntax, compilation,
and whitespace checks pass. The actual Validation candidate image passes all 11
Instagram publication tests and both configurator tests. The generic Commander
image passes 23 of 24 checks; its sole git-dependent planner check cannot run
because that older image lacks `git`, while the same check passes locally.
The preserving release completed at revision `3dee45b`; only Validation
restarted, and all canaries, audits, approved-asset checks, and database checks
passed. Production was still unconfigured at that checkpoint until the owner
reran the hidden prompt; no reset or database mutation was involved.

## 2026-09-10 — Studio draft validation hid the last successful preview

The owner reported HTTP 400 from Phone Metrics preview after clearing CTA.
The normalizer required 1–60 characters, while a debounced effect rendered every
field change. The editor hid its previous PNG immediately when the draft state
changed; a rejected request therefore left a loading placeholder indefinitely.

Phone Metrics now accepts empty CTA copy and removes the whole band. Both Post
editors batch control changes until **Update preview**, retain the previous PNG
on failure, label unpreviewed edits, and support manual retry. The requested
snapshot is tracked independently of edits made while rendering. Composer and
renderer bounds agree, preview cannot create learning, and the canonical Tune
and visual-audit skills preserve these requirements.

Resolved in production by `studio-preview-20260910-ce8706f`. The preserving
release took 493 seconds, replaced only Validation, and published Owner cache
v7. All 229 local and Linux-image Validation tests, 24 built-image Commander
tests, 93 Owner unit tests/build, 81 browser flows, canonical skills, and visual
checks passed, alongside nine fresh provider canaries, Pexels, dependency/resource
checks, full authority preservation, and approved-Post access.

The exact affected Creative `01a07f55-20a5-755c-bbec-17a3f158ef4b` reproduced
HTTP 400 before rollout and returns HTTP 200 afterward for empty CTA. A second
invalid-then-corrected draft also recovers. Its saved state digest
`3f28b7a8156bb93feb2ce224a550e16a1f0e32b2ca360c46bc4a050dcbce5327` and all three
immutable versions remain identical. Live pixels confirm the CTA band disappears
while the upper canvas is unchanged. The public bundle matches the tested build.
No Save, Approve, reset, or learning action was performed during acceptance.

## 2026-09-10 — Mobile receiver reported failure after a successful rollout

A documentation-only GOD-mode acceptance candidate passed every GitHub gate and
the restricted receiver completed its preserving rollout, but the workflow then
reported failure. Production had already advanced to the exact candidate, so
blindly retrying or treating the old revision as live would have been unsafe.

The receiver's Hosting helper declared its positional locals and a derived path
in one Bash `local` statement. Under nounset, the derived expression expanded
before the new `target` local existed. This failed even for a reused Hosting
artifact, after the deployed-revision commit point. The helper now declares each
input before deriving the temporary config path. The release contract locks in
that ordering, and the VPS operations skill requires deployed-revision
reconciliation whenever a forced receiver exits after the inner rollout.

Verification included the full GitHub Python, Commander, release, Owner Console
Chromium/Firefox/mobile-WebKit, selective-build, and immutable-Hosting gates.
The preserving receiver's health, dependency, resource, bot-identity, and
deployed-revision checks had completed successfully before the false failure.
The corrected receiver is deployed through the normal preserving path before a
fresh mobile canary is accepted. No database reset or business-data mutation
occurred.

## 2026-09-10 — Studio learning replay blocked a guarded fast rollout

An owner Save persisted its Creative and immutable checkpoint, but learning
rejected a privacy-safe global proposal as though it contained Project-specific
content. The UI showed no error because Save itself had succeeded and the
failure remained in the queued learning state. A later release correctly
refused to restart Validation while that checkpoint lacked a completed learning
run.

The first Retry appended a second failed run but replayed the same completed
provider response. Studio learning used one checkpoint-wide idempotency key, so
deterministic PTW validation could never obtain corrected output. The retry now
keeps the same provider attempt after transport, provider, timeout, or
persistence uncertainty, while a prior `ValueError` advances the provider
attempt and includes only the bounded validation error as correction context.
Inspection of all four completed provider responses showed generalized rules
about logo visibility. The privacy filter had treated the generic asset slot
value `logo` as a private identifier. It now checks exact copy plus selected
asset provenance identifiers and still rejects IDs, digests, URLs, provider
identity, and owner visual direction without rejecting ordinary Studio terms.
The failed runs and saved Creative/checkpoint remain append-only and intact. A
tracked one-off command can recover that exact checkpoint through the normal
database and provider services before rollout.

The rejected release also exposed deployment bookkeeping defects. Its receiver
advanced Git before preflight, so later planning could mistake candidate source
for running source, and cleanup recreated old containers even though cutover had
not begun. Successful deployments now atomically record their exact revision;
legacy installs infer it from the running Validation image. Rollback is armed
only after preflight. Already loaded candidate images can be verified by amd64
architecture and source-revision label and reused without another upload.

Local verification passes all 220 Validation tests, 23 Commander tests (two
dependency-skipped locally), the Commander demo, shell and Python syntax,
canonical skill validation, release-contract checks, and whitespace checks.
The exact checkpoint completed on its fourth append-only learning run and
created one pending global proposal; the Creative remained unchanged. Release
`fast-release-20260910-64de1e8` then replaced only Validation and hosted GOD,
left all five unchanged application/provider images running, passed nine fresh
provider/media canaries, Pexels, dependency/resource, authority, immutable-Post,
and live Owner checks, and completed in 7m19s end to end. A post-restart query
confirmed the checkpoint remains completed and no mutable operation is active.
Status: resolved in production.

## 2026-09-10 — Hosted Commander turns failed at two nested runtime boundaries

The GOD-mode release passed service health, public authentication denial,
provider, dependency, resource, and Hosting checks, but its first real private
turn failed before producing a reply or editing the isolated checkout. The Codex
binary and published credential were readable. The missing contract was a
writable `CODEX_HOME`: the credential source is intentionally read-only, while
the CLI still needs private runtime files during ephemeral execution.

The runner now copies only the published `auth.json` into its persistent private
state before every turn, atomically refreshes that copy, and points `CODEX_HOME`
there. The credential source and standalone binary remain read-only, and the
isolated source checkout has no runtime `.env` files. A regression verifies the
first copy, credential refresh, private runtime path, and completed execution.

The credential repair allowed a real turn to reach the model, but its first Git
command then failed because the CLI's nested Linux workspace sandbox requires
namespace and mount operations denied by the deliberately capability-free
container. The hosted runner now uses Codex's execution mode for externally
sandboxed environments. This applies only to hosted Commander; the local runner
keeps `workspace-write` with shell network disabled. The container remains the
hosted boundary: read-only root, isolated checkout and state mounts, no Docker
socket or production data, dropped capabilities, resource limits, and a bounded
environment allowlist. Regression coverage distinguishes the two execution
modes.

Release `god-mode-sandbox-20260910-faf77f9` passed the preserving rollout and
all provider, Pexels, dependency, resource, authority, and approved-Post checks.
A real private hosted turn read `AGENTS.md`, reported the exact release HEAD and
a clean checkout, and made no edits. The same completed chat and reply remained
available after restarting only `commander-god` under the maintenance lock; the
checkout was still clean. Status: resolved in production.

## 2026-09-10 — Legacy editor Save rejected after successful read-only restore

The owner reported that Save creative edits disappeared after reloading. The
Gateway recorded three Save requests at 05:39, 05:45, and 05:47 UTC, all HTTP 409;
the latest stored save checkpoint remained from the previous day. Validation
had not restarted since the previous release. The changes were rejected before
persistence, rather than lost from a committed checkpoint on restart.

The previous compatibility repair correctly restored the original v8 files
without mutating PostgreSQL. However, the Creative service merged stored
metadata over the normalized renderer detail, replacing the editor's state
hash with its older stored hash. Checkpoint Save compared that hash directly
against the normalized hash, unlike the existing legacy-aware preview validator.
Read-only inspection of the affected Creative confirmed those hashes differ.

The local fix gives renderer fields precedence in editor responses and uses
the existing bounded state validator for Save/Approve, including clients already
holding the verified older hash. An explicit unchanged legacy Save persists the
normalized files before advancing metadata. GET remains read-only; actual stale
edits still fail closed. Tests cover edited and unchanged Saves, fresh adapter
and service/cache restoration, completed learning and checkpoint lineage, no
duplicate checkpoints, and unchanged immutable PNG bytes. The standalone
`scripts/verify_studio_save_restart.py` runs real HTTP/domain/database operations
against an automatically created and removed disposable PostgreSQL instance.

Separate latency evidence: one Creative GET returned Gateway 503, while later
internal reads took 0.066 seconds for Projects and 0.763 seconds for the Creative.
The 961 MiB VPS had 164 MiB available and 617 MiB swap used during inspection.
These observations justify resource investigation but do not prove that memory
pressure or the image-generation lock caused the original timeout.

The owner also reported seeing no error. Both Post editors placed action errors
above the template selector without moving focus or scrolling, so a failure
could remain outside the mobile viewport. The local UI now places feedback
beside Save, focuses and scrolls to errors, retains pending edits, and tells the
owner to copy them before reloading. Preview failures have a separate display
and cannot replace a Save error or negate confirmed persistence. Both templates'
Save/Approve deadlines now match the Gateway's bounded 480-second learning
deadline. Candidate shell cache v5 and the build marker identify this UI fix.

Verification: 218 local Validation tests, 21 focused Linux-image Studio tests,
18 built-image Commander tests plus demo, disposable PostgreSQL Save/restore,
canonical skill validation, and whitespace checks pass.
The companion UI passes 88 web unit tests, 78 mocked browser/UI flows, production
build verification, and the deterministic Studio visual audit. Actual delayed
409 screenshots were inspected at desktop/360px/iPhone WebKit; feedback is in
view with no horizontal overflow and the pending headline remains intact.

Release `studio-save-20260910-2d18dfc` passed the preserving rollout, provider,
Pexels, dependency, 1 GB resource, approved-Post, and live Hosting checks. Owner
cache v5 is live. A bounded unchanged Save normalized the affected legacy
workspace, retained its state and both immutable approved version/render hashes,
and completed one learning checkpoint. The same state, checkpoint, versions, and
renders survived a Validation restart; a second identical Save returned HTTP 200
without another checkpoint or version. Rejected browser edits were never stored,
were not recoverable, and were not invented.

## 2026-09-09 — Legacy Post reads failed after renderer schema uplift

The first full Instagram release preserved all prior database rows and PNGs,
but its authenticated Post-derived workspaces returned HTTP 409. The stored
Phone Metrics configuration was v8; normalization to the current editor schema
changed the computed state hash before the database adapter verified the
original snapshot. The bounded legacy hash matched the stored digest exactly.

The database restore now uses the existing legacy-aware state validator and
never persists an existing workspace during reads. Only explicit owner mutations
write the normalized state. Regression coverage checks repeated restores,
unchanged stored files/digest/approved PNG, and rejection of changed content.
Both preserving deployers now require authenticated Ads/Instagram source reads
and PNG digests to match PostgreSQL before reporting success. The new canary is
read-only and does not require Meta credentials.

The final Hosting audit also observed a transient HTTP-200 HTML SPA fallback at
a newly published hashed App URL. It passed once assets propagated; the auditor
now requires JavaScript MIME inside its existing bounded retry window, covered
by a fallback-then-JavaScript regression. Security marker checks remain required.

Verification and release: 217 Validation tests and 18 built-image Commander tests
pass. The compatibility release `instagram-restore-20260909-a4af6b2` passed both
preservation comparisons, all nine fresh generation canaries, Pexels, dependency
and resource audits, and authenticated access to the existing Project's two
approved PNGs in both Ads and Instagram. Their digests match PostgreSQL, and the
current published Landing resolves correctly. All six services are healthy;
Owner cache v4 and both Hosting sites are live. Meta credentials remain absent,
so no real Instagram publication or paid-ad creation is claimed.

## 2026-09-08 — Monolithic Landing composition repeatedly exhausted the worker deadline

**Symptom:** expanded pre-cutover canaries passed all retained structured and
media modes, but post-cutover Landing composition alone failed at the worker
deadline. It failed once at 300 seconds, again after the bounded worker timeout
was raised to 360 seconds, and again with explicit server-owned low reasoning.
Each preserving rollout rejected the candidate and restored the prior images;
the owner Creative and append-only state were unchanged.

**Cause:** the Landing model contract asked one structured call to return both
marketing content and the complete renderer configuration while also receiving
the live catalog, frozen Post configuration/assets, defaults, and skill
documents. Queue alignment, authentication, schema validation, and reasoning
were healthy. The repeated exact-deadline signature isolated excess contract
shape and model ownership, rather than a data, auth, or recoverability problem.

**Durable fix:** Landing composition v5 makes AI responsible only for strict
bounded content. The server preserves configuration, layout, theme,
presentation, components, image styles, phone layout, routing, Natal identity,
and asset policy. One canonical payload builder is shared by runtime and release
canary; it sends the approved Brief, bounded frozen Post copy, current content
defaults, and at most eight recent lessons per scope, never the live catalog,
Post configuration, or assets. Append-only learning history is retained. The
bridge now rejects any structured contract over 512 KB before submission and
records only prompt/input/schema byte counts. Landing has stricter compact
canary limits. Both incident skills now route repeated deadline failures to an
AI/server ownership split instead of longer timeouts or blind retry.

**Verification:** unit coverage proves content-only schema enforcement, AI
configuration rejection, exact preservation of current server configuration,
bounded lesson context, exclusion of catalog/config/assets, pre-submission
contract rejection, and byte-count provenance. All 169 Validation tests pass
(162 in the Git-free production image plus seven Tune tests in the same image
with ephemeral Git), together with 15 Commander/deployer, 6 Gateway, 72 web
unit, 67 browser, two build, four-migration idempotency, syntax, compilation,
and whitespace gates. The deployer tests cover active-work refusal, `-T`,
failed-path authority fingerprints, full app/platform rollback verification,
persisted-tag restoration, and refusal to bypass the backup-bearing path when a
migration is pending. The live preserving rollout at PTW revision
`153b1dc6417a4c26b36ca9af4f8aac5d00d8b591` completed without a migration or
reset. Fresh jobs 514–522 all completed on attempt 1; the compact Landing
contract was 8,444 bytes. Full-row authority was unchanged, all six services are
healthy on `contract-budget-20260908-153b1dc`, and the exact affected Creative
retained its ID, draft status, state digest, zero immutable versions, and five
append-only generation runs across a controlled Validation restart.

The first promotion attempt also exposed a release-control defect before any
service cutover: `psql -c` did not expand the migration-name variable in the
new pending-migration guard. The fail-closed preflight left production on all
six prior images with no database change. The query now uses stdin SQL, the
static regression forbids the broken `-c` form, and both incident skills require
an exact-production preflight plus a new tested commit instead of an interactive
VPS bypass. Scheduled monitoring is checked by its real transient unit,
`ptw-validation-24h-audit.timer`, which is active/waiting for the 24-hour audit.

## 2026-09-08 — Phone Metrics replayed a completed response outside renderer bounds

**Symptom:** the first approved Phone Metrics Post remained `failed` with a
`ValueError` saying that texture intensity must be between `0.04` and `0.24`.
Owner retries preserved the Post but repeated the same error.

**Cause:** the strict Studio generation schema described the field only as a
number, while the renderer enforced the narrower range. The provider therefore
completed a schema-valid response with zero intensity. Every retry reused the
same completed `:attempt:1` bridge job because the composition idempotency key
did not change, so no corrected composition was generated.

**Durable fix:** this is treated as a contract-drift class, not a one-field
exception. Provider schemas and runtime normalizers now consume the same domain
constants for Studio and Landing bounds, enums, colors, typography, fixed device
constraints, content lengths, and privacy-sensitive blank fields. Every
structured Product Brief, Studio composition, Landing composition, Studio
learning, and Landing learning call requires a deterministic domain validator.
Every local and production bridge request is keyed by a canonical fingerprint
of its mode, model, complete system prompt, input, output schema, prompt version,
and referenced asset digests; a contract change therefore cannot replay an old
completed response. Image generation and enhancement use the same fingerprint
rule. One fresh `:attempt:2` is permitted only when a completed response is
rejected by deterministic domain validation; transport, timeout, cancellation,
CLI, and provider failures do not cause an unsafe blind retry. A successful
retry clears stale current error fields while append-only failed runs remain.
Raw provider HTTP bodies are never reflected. Both incident skills encode these
system-wide diagnostics, release gates, and same-entity recovery without reset.

**Verification:** focused provider and Studio tests prove strict texture bounds,
separate corrective idempotency keys, a successful corrected response, and no
second attempt after transport/provider failure. The complete Validation,
Commander, Owner Gateway, web unit/build/browser, schema-idempotency, skill,
compilation, whitespace, demo, and Studio visual checks pass. Pre- and
post-cutover production canaries completed Phone Metrics composition on fresh
`:attempt:1` jobs and passed image generation, exact-reference enhancement,
Pexels, dependency, and resource audits. Retrying the affected Post used the
new versioned key once, accepted texture intensity `0.08`, and completed its
phone image. The original three failed runs remain append-only beside the two
new completed runs. The exact Creative ID and state digest survived a
Validation recreate, with one Creative for the Brief and no approved version
invented. No reset ran.

The generalized follow-up adds automated fingerprint dependency, bounded-key,
mandatory-validator, no-blind-retry, stale-error cleanup, secret-reflection,
strict Landing schema, and media-integrity coverage. Release acceptance now
requires fresh attempt-1 real canaries for both Product Brief modes, both Studio
templates, Landing composition, Studio learning, Landing learning, new image
generation, and exact-reference enhancement before and after cutover.
Normal rollouts now use a tracked preserving deploy path rather than an
SSH-stdin control stream: Compose one-off jobs disable TTY/stdin consumption,
active mutations block cutover, every authoritative row is fingerprinted before
and after, any incomplete exit rolls back images and persisted tags, and the
destructive reset script is never called.
The bridge client also serializes submissions to the single production worker,
and the worker execution timeout is configurable only within a tested bound
below the client deadline. This prevents queue wait from consuming a parallel
request's entire timeout while still allowing the largest Landing contract to
finish.
Production bridge jobs pin the Codex reasoning effort to the explicit bounded
`low` setting rather than inheriting an ambient CLI default. Strict schemas,
domain validators, and attempt-1 canaries remain the acceptance authority.

## 2026-09-06 — Landing reservation passed a relationship label as a UUID

**Symptom:** creating the first private Landing from a valid Project and
approved Post returned HTTP 400 with `badly formed hexadecimal UUID string`.

**Cause:** the PostgreSQL-only Landing reservation path called the graph-edge
helper with `relation` and `target_id` reversed for the approved Post lineage.
It therefore attempted to parse the literal relationship name `derived_from`
as a UUID. The local loopback path used the correct ordering, so existing local
workspace tests did not exercise the production failure.

**Durable fix:** corrected the database graph call and added a database-path
regression that asserts the Project `contains` edge and both Brief/Post
`derived_from` edges by semantic argument position. The Owner Console incident
and VPS operations skills now route this exact UUID signature to graph-edge
ordering and require rollback verification before retry, without resetting the
Project.

**Verification:** 128 Validation tests, 10 Commander tests plus demo, 4 Owner
Gateway tests, 58 web tests/build, 48 browser checks, schema idempotency, the
Studio visual audit, compilation, skill validation, and whitespace checks pass.
The versioned production rollout preserved the database. Retrying the same
approved Post returned HTTP 202, persisted the three typed lineage edges, and
completed composition plus both visuals; a duplicate reservation returned the
same Landing ID without creating another row. The draft and exact asset/state
digests survived a Validation restart with an empty recovery queue. The full
dependency audit, schema-bound worker probe, public Hosting boundary, live
Pexels canary, and 1 GB resource audit pass. No reset ran.

## 2026-09-06 — HTTP 200 masked a failed structured provider execution

**Symptom:** the project Brief list returned HTTP 200, but its persisted Brief
was failed after repeated `structured bridge request N failed` attempts. The UI
showed an internal bridge string without explaining that the successful HTTP
response represented only a successful read or how the owner could recover.

**Cause:** all containers were healthy and the auth service passed its working
test, but a benign probe using the worker's exact schema-bound Codex execution
path returned unauthorized. The worker used a single-file bind of the primary
credential; Codex atomically replaced that file after device login, leaving the
running worker pinned to its stale inode. The frontend also normalized transport
errors only partially, treated a readable failed entity separately, and omitted
the persisted Landing generation error.

**Durable fix:** centralized localized API failures into outcome, explanation,
safe next action, and bounded technical context; applied the same contract to
persisted Brief, Studio, phone-image, Landing, and Landing-learning failures;
and suppressed raw 5xx/provider details. The auth service now keeps the primary
credential root-only and publishes a separate copy through a dedicated directory
mount that remains current across atomic replacement. The production dependency
audit compares the handoff internally and runs a token-safe schema-bound worker
probe. Both incident resolver skills record the HTTP-200/failed-state and stale
single-file-mount diagnoses before any generation retry.

**Verification:** 58 web unit tests, 48 browser checks, the production web build,
10 Commander checks, Commander demo, 38 platform tests, skill validation, script
syntax, and whitespace checks pass. The public Hosting audit confirms Landing
and the actionable-error markers. Production auth reports `authorized`/`passed`;
the dedicated published credential matches the worker mount; the schema-bound
worker probe and complete dependency audit pass. One explicit retry changed the
same Brief from failed to completed: its third append-only attempt and latest
structured provider invocation are completed, with document digest, quality
gates, and completion timestamp present. No reset ran.

## 2026-09-06 — Mixed production release broke generation, Landing, and ChatGPT authorization

**Symptom:** a Brief remained readable over HTTP 200 but its persisted state was
failed with `structured bridge request N failed`; Landing was absent from the
navigation; and ChatGPT Authorization remained required while Refresh appeared
to do nothing. An earlier request to the retired Studio route also returned 404.

**Cause:** production combined stale and incompatible Commander/platform/web
releases. The bridge job number was misread as an HTTP status, the deployed
database did not contain the Landing migration, and the live bridge exposed the
wrong mode set. Device login also lacked a pseudo-terminal and outbound network;
ANSI styling hid its one-time code, login status did not prove model execution,
and the regenerated root credential was unreadable by the non-root worker.
Finally, the current Codex JSON stream did not expose nested image-tool arguments,
so the old enhancement proof rejected a valid observable flow.

**Durable fix:** deployed one versioned compatible set for Commander, Validation,
Owner Gateway, platform API/worker/auth, both schema migrations, and Firebase
Hosting. The private auth service now uses a pseudo-terminal, outbound edge
access, ANSI-safe parsing, bounded real-request retries, and a root-owned
group-readable credential handoff to the non-root worker. Enhancement acceptance
uses exact private reference validation plus a distinct output digest. The
serial publisher stops before reset whenever provider canaries fail. The
owner-confirmed irreversible reset ran only after every canary passed.

**Verification:** all six services are healthy on the same release; exact bridge
capabilities, ChatGPT/Codex working authorization, secure worker credential
readability, all structured/media/Pexels canaries, public Hosting markers, App
Check/CORS/auth boundaries, schema idempotency, local suites, Commander demo, and
skill checks pass. The reset left every Brief, Studio, Landing, and graph business
table empty while the independent platform database snapshot remained unchanged.
Both emergency stops are false, the resource audit passed, and its 24-hour
follow-up timer is active.

The retired Social posts/Result incident history is available only in Git
history. Record future Product Brief, Studio, Owner Gateway, Firebase, Commander,
or Telegram emergency incidents here with symptom, cause, durable fix,
verification, and the narrowest reusable skill update. Never record secrets or
ephemeral release hashes.
