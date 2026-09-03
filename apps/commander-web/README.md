# PTW Owner Console

Production exposes Product Briefs and the standalone Universal Studio. The
loopback local app adds one deliberately small Post step:

1. Product Briefs — create one Project and immutable Brief from one raw idea,
   correct/retry it, and approve only after confirming its promise and offer.
2. Post (local only) — generate one Studio-rendered draft from the approved
   Brief, tune it through one natural-language comment below the preview, and
   create an immutable asset only through explicit approval.
3. Studio — edit the bounded universal-ad configuration and approve immutable
   reusable versions independently from Product Briefs and Post.

Post comments resolve to exact Studio setting/content commands and optionally
one semantic Pexels background query. Internal primitives, provider prompts,
model controls, and chain-of-thought remain hidden. The browser does not
publish, schedule, create campaigns, add UTMs, run analytics, or optimize.

Run:

```sh
npm run check
npm run test:e2e
```
