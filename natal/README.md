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
Owner Console Landing tab prepares that skill invocation from completed Idea
Laval evaluations through the normal plan-and-approval job lifecycle. It does
not publish or deploy a page.
