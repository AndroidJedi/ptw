# Catalog visual quality review

Status: local implementation, not deployed
Updated: 2026-09-24

The catalog contains four current designs: Phone & Metrics, an accepted authored
square Post, Project Landing and App Showcase. The audit also includes retained
App Showcase v1 and all three accepted authored Post versions: seven exact
definitions. Historical definitions and approved media remain immutable.

## Corrections and evidence

- Built-in Landing previews now demonstrate a coherent browse/request/review UI
  family in portrait interiors and canonical hardware. Walkthrough examples have
  native transparency and opaque screen interiors. These are explicitly neutral,
  code-drawn gallery fixtures, not generated Project assets or product evidence.
- Phone & Metrics gallery copy and controls use one language, a populated phone
  title and representative text density. Project Landing uses the pinned reference
  photo to demonstrate its supporting crop instead of abstract placeholder art.
- Complete declarative subjects, phones, brands, motifs and store badges use
  contain. Legacy stretch settings render proportionally; ordinary photo cover
  crops retain their selected focal point. The renderer contract is v7.
- Exact historical built-in requests resolve the requested definition. Preview
  cache keys include fixture and renderer content independently of template IDs;
  refresh appends media and never replaces saved preview or approved bytes.
- Project Landing hero and FAQ stack through 900px. Long Ukrainian headings no
  longer occupy narrow tablet columns. Both Landing templates now share this
  hero breakpoint.
- Post switching retains value/label context in standalone benefit fields and
  preserves existing authored text. The accepted square layout's tiny secondary
  text remains an explicit historical finding, not a silently rewritten version.
- An Astra `xhigh` analyze/compose/compare run produced a local review proposal
  for the square Post: larger explanatory/benefit boxes, separate subject space,
  unchanged gradient/footer/brand/badge assets. Tested body sizes are 32–38px and
  benefit labels 30px with real English/Ukrainian copy. Acceptance is pending the
  owner's choice; no existing Project was switched.
- A real raw photo exposed pinned cutout inference removing the laptop. A new
  native-alpha extraction preserves the complete interaction in the local review.
  This is a separate generated review asset, not a replacement for source bytes
  or proof that every inferred mask is semantically complete. No semantic retry
  loop was added. Other existing scene cutouts still require per-image inspection.
- Owner review rejected the fragmented hardhat portrait and unrelated blue
  gradient. Its replacement is a generated, complete person using a phone, with
  native alpha and a terracotta/charcoal palette. The three real-copy previews now
  use warm burgundy, navy and warm neutral gradients chosen for their actual art.
  White copy remains legible; original source bytes remain intact.
- Authored full-canvas gradients now expose two bounded per-Post colors in the
  editor. Overrides affect preview/save/approval and persist across reopening;
  they restore when returning to that template. Default renders remain unchanged.
  Template documents, logos, badges and approved PNGs are not recolored. Palette
  selection is explicit; no automatic image sampler or semantic retry was added.

The local evidence root is `.local/template-quality/final/`; port 42745 serves
`site/review.html` for before/after examples and `site/index.html` for native
renders and viewport/section captures. `astra-proposal.json` records the exact
pending run; `proposals/` includes the exact proposed PNG, definition and real-copy
checks. Generated review media lives in `.local/template-quality/review-assets/`.
None of these artifacts implies deployment, Project approval or publication.

## Reproduce

```sh
npm --prefix apps/commander-web run build:template-preview
.venv/bin/python scripts/audit_template_quality.py \
  --output-dir .local/template-quality/final \
  --template-store .local/template-authoring.sqlite3 \
  --workspace-root .local/studio-workspace/creatives
node apps/commander-web/scripts/audit-template-quality.mjs .local/template-quality/final
```

The exporter opens SQLite read-only and copies Project workspaces before rendering.
Omit private inputs for a built-in-only review. Native overflow checks and small
text review targets are separate. The browser audit loads all lazy images/fonts,
opens FAQs, checks proportional screens, aligned phone captions, reachable app
controls and responsive columns at 1440/1280, 768, 360 and iPhone WebKit. It covers
neutral and long-copy variants, historical App Showcase and the original template's
optional marketing sections. Inspect the screenshots as well as the measurements.
Visible font ink extending outside a line box is not automatically clipping.

Verification includes backend/provider tests, Owner/Public tests/builds, Templates
and Landing browser checks, disposable PostgreSQL template and Post persistence,
Commander tests/demo, deterministic Phone Metrics audit, skills and whitespace.
The browser restart fixture waits for pending preview reads and models temporary
proxy failures without orphaning a disposable server.

Completed evidence: 397 backend tests locally, 396 in the Linux image plus 11
palette/switch and six final quality checks, 125 Owner and six Public unit tests, both builds, 21
Templates/Post + 45 Landing + 28 Public browser tests, both disposable PostgreSQL
canaries, 43 Commander tests (five runtime skips), Commander demo, Phone Metrics
audit, skills and whitespace. The final browser matrix contains 35 views and
285 section captures with zero recorded geometry errors. Three prior accepted
authored records and all three original raw Post images compare unchanged.
The owner correction reran Post browser checks on all three browser profiles and
the disposable PostgreSQL Post persistence canary. The three corrected gradients
retain at least 5.9:1 white-copy contrast at both endpoints. The built-in image
tool generated `review-assets/commitment-hero.png`; its exact prompt is saved in
`review-assets/commitment-hero-prompt.txt`. `proposals/corrected-palettes.json`
records the explicit colors and contrast measurements.

Canonical generation/review rules live in `DESIGN_RULES.md`, the Template Creation
skill, Studio Visual Audit skill and the shared image policy. These are engineering
rules, not learned performance claims. Keep the chat-hosting runtime untouched;
code takes effect on a later safe restart or separately authorized deployment.
