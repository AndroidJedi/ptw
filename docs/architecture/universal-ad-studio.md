# Universal Studio

Universal Studio is an owner-only, standalone workspace. It does not depend on
Product Brief approval and does not create posts, content runs, review sets, or
publication records.

## Contract

The server owns one fixed semantic structure: background, optional sticker,
hero title, supporting text, optional benefits, CTA, and optional logo. The API
accepts only strict `ptw.studio.universal-ad-config.v5` configuration and
semantic content. Catalog v6 maps stable component IDs to typed setting IDs,
bounds, steps, enum values, and English/Ukrainian aliases. Unknown fields and
out-of-range values fail closed.

The internal primitive tree is built server-side by
`build_universal_template()`. API callers cannot import templates or mutate
arbitrary nodes. The shared `StudioRenderer` renders this primitive tree to PNG.
Geometry and visual audit guard clipping, overflow, unsafe bounds, and
responsive preview regressions.

## Assets and persistence

The workspace has fixed `background`, `sticker`, and `logo` asset slots. Owner
uploads and Pexels imports validate decoded media, size, dimensions, digest, and
provenance. A saved version stores exact configuration, content, asset digests,
template digest, and PNG bytes below `.local/studio-workspace`; authenticated
render responses are private/no-store.

The canonical Natal logo/font are deterministic defaults. A sticker may be
isolated from an approved photographic object while retaining source and
transformation provenance. Studio never receives provider credentials in the
browser.

## Local Tune

`STUDIO_TUNE_MODE=1` enables the loopback Tune wizard. It captures one requested
Studio implementation, runs Codex in an isolated worktree, enforces a Studio-only
allowlist, verifies focused tests/build checks, and presents a preview before
copy-back. Only explicit owner approval may persist a generalized rule in
`skills/studio-tune-local/references/owner-approved-rules.md`. Production Owner
Gateway does not expose Tune routes.
