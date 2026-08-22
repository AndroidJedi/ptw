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
`brief.json`, a provenance-bearing `build.json`, and digest-verified Natal
assets. The builder refuses a non-empty output directory unless `--overwrite`
is explicit.

`skills/natal-landing-builder/` is the Commander/Codex agent contract. The
Owner Console Landing workspace prepares a fresh, schema-bound builder-agent
turn from a completed Idea Laval evaluation and its append-only feedback
memory. The owner may apply `product`, `community`, and `waitlist` repeatedly
in any order. Every immutable revision is then published through the
server-pinned Firebase workflow; no Commander plan or global Jobs redirect is
involved.
