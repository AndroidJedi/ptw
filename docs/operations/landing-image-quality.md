# Landing image output and visual quality

Status: implemented and verified locally; deployment and regeneration/publication
of an owner Landing remain separate actions. No migration or data rewrite.

## Contract and model routing

`PTW_VISUAL_AGENT_MODEL` defaults to `gpt-6-astra` in local and production
factories. It routes Post/Landing composition, their Manual Agents, Templates
and image workers independently of `VALIDATION_LLM_MODEL` / `LOCAL_CODEX_MODEL`
for Brief and Analytics. Existing per-workflow reasoning efforts are retained.
Agent provenance and pixel-model provenance are separate. The built-in tool's
pixel model is unknown when it does not report one; the API adapter keeps its
existing explicit image model.

`ptw.image-output.v1` adds a server-owned `output_spec` alongside the existing
`ptw.domain-image.v1` policy: dimensions, opaque/transparent background and four
safe-area fractions. All adapters transport it; fingerprints and provenance
include it. App screen interiors request 864×1872 (9:19.5), with a 6.5% top
camera margin and 4% other margins. Complete walkthrough devices request
1536×1152 (4:3), transparent surroundings and 4% safety margins. Post defaults
remain 1024×1024. Output validation bounds each dimension to 512–2048px and
allows 3% aspect deviation for built-in tool sizing. It never stretches pixels.

A shared screen-family specification fixes typography, palette, spacing,
controls and navigation. Lists and forms show Brief-grounded tasks with readable
Ukrainian or English labels, without invented results or decorative poster art.
The canonical hardware wraps app screen interiors; walkthroughs contain their
own hardware. Both template renderers use proportional fitting for device art.

Walkthrough preparation preserves meaningful native alpha. Opaque output uses
the existing SHA-pinned U2netp extractor; enclosed white screen holes are filled,
all detected device components are retained and unused canvas is trimmed with a
3% safety margin. Raw bytes stay private under `assets/raw`; preparation metadata
records raw/prepared SHA256, model digest when used, original size and crop.
History and approved versions protect their raw bytes from pruning. Approval
and public delivery use the exact prepared PNG. Failure or a stale state digest
preserves the previous selected image. This is deterministic preparation, not a
visual score or an automatic semantic retry loop.

## Independent companion artifact

`patches/platform/landing-image-output-v1.patch` is a separate companion commit
based on `8fc30c9a423255e1c43161edc691b84698b625e2`; the local isolated branch is
`codex/landing-image-output-v1` in `.local/platform-domain-images`. Do not merge
its history into PTW. This exact-base patch uses zero context to avoid storing
patch-context whitespace as source; apply it with `git apply --unidiff-zero`
in the isolated companion checkout at the stated base, then run its tests and
commit independently. The companion advertises `image_output_specs` and uses the
versioned geometry instead of its former square-only prompt/validation. Requests
without a specification retain legacy square behavior.

A future authorized preserving release must install the compatible companion
API/worker before PTW starts sending the new contract. The PTW adapter fails
before submitting a job when the worker lacks this capability. Roll back PTW
before rolling back the companion. The ordinary PTW-only fast release cannot
supply the companion change. Follow the existing preserving release controller;
never reset or rewrite approved image bytes/publication records.

`validation_pipeline.verify_bridge_contract` now routes visual canaries through
the visual model and exercises square generation/edit, portrait screen output,
landscape mockups and cutout preparation. Run it after an authorized deployment;
local tests are not evidence of the production worker accepting the new contract.

## Repeatable local visual review

Run the explicit real-provider fixture builder (one image call per missing slot):

```sh
.venv/bin/python scripts/verify_landing_image_quality.py \
  --snapshot-url https://commander.proove-them-wrong.com/api/v1/public/landings/morning-coffee \
  --output-dir .local/landing-image-quality-final --photo-focus-y 15
```

The script reads public copy/images only, preserves the source snapshot and
writes isolated local workspace files. Its public-copy input is an audit fixture,
not a fabricated approved Brief. Production generation uses the pinned Brief.
It never changes an owner Project or approval/publication. A completed directory
is reusable without new provider calls; use a new directory for a deliberate
manual revision. No automatic image-quality retry is permitted.

After `npm run build:template-preview` in `apps/commander-web`, the audit below
requires `after.json` plus an `original.json` fixture of the other template
(the inspected local original-template draft is retained in the audit directory):

```sh
node apps/commander-web/scripts/audit-landing-images.mjs .local/landing-image-quality-final
python3 -m http.server 42743 --bind 127.0.0.1 --directory .local/landing-image-quality-final/site
```

It loads fonts and all lazy images, captures every section at 1440/1280, 768,
360 and iPhone WebKit, and records geometry and screenshots. Inspect camera
clearance, supporting-photo crops, aligned captions, button wrapping, spacing,
logo contrast and long Ukrainian copy. Initial logo contrast is chosen against
both gradient endpoints; explicitly saved owner colors remain unchanged.

The linked Landing's sample-review block and contact fallback store destinations
are intentionally preserved. Visual improvements are engineering/generation
rules, not evidence of performance or a change to learning authorities.
