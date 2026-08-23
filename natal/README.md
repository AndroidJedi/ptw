# Natal landing factory

This folder turns a bounded `brief.schema.json` product brief into a dependency-free, mobile-first
Natal landing page. The name, logo, icons, tokens, and accessibility baseline
are fixed; Idea Laval data supplies the audience, pain, promise, features,
steps, proof, FAQ, and CTA.

```sh
python3 -m natal.builder --list-templates
python3 -m natal.builder \
  --template product \
  --brief path/to/brief.json \
  --output output/landings/example
```

The build contains `index.html`, `styles.css`, `app.js`, the normalized
`brief.json`, the exact independent-block `page_content.json`, a
provenance-bearing `build.json`, and digest-verified Natal assets. The three JSON
files are internal metadata and are not published. The builder refuses a
non-empty output directory unless `--overwrite` is explicit.

`skills/natal-landing-builder/` is the Commander/Codex agent contract. The
Owner Console Landing workspace prepares one fresh, schema-bound builder-agent
turn from a completed Idea Laval evaluation and its append-only feedback memory
to populate private `product`, `community`, and `waitlist` snapshots. Preview
documents inline this kit for sandboxed `srcdoc` review. The owner can edit one
of seven content blocks at a time; only an explicit publish action creates an
immutable Landing revision through the server-pinned Firebase workflow.
