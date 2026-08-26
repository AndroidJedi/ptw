# PTW Owner Console

The authenticated PWA has two Project-scoped workspaces:

1. Product Briefs — create one Project and immutable Brief from one raw idea,
   correct/retry it, and approve only after confirming its promise and offer.
2. Result — select an approved Brief, choose Text or Instagram post, enter one
   task, follow three bounded progress stages, and receive one final result.

Internal candidates, templates, sliders, UUID entry, recipes, layers, provider
prompts, and model controls stay hidden from the normal journey. A bounded
owner-only debug section exposes IDs, versions, scores, gates, actions, digests,
retries, and lineage without chain-of-thought or raw source/attachment data.

The browser does not perform research, publishing, traffic, campaigns, UTMs,
analytics, optimization, or direct image generation. PostgreSQL behind Owner
Gateway remains authoritative.

Run:

```sh
npm run check
npm run test:e2e
```
