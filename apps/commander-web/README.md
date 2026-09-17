# PTW Owner Console

The Owner Console exposes exactly two destinations:

1. Product Briefs — create a Project and immutable Brief, correct/retry it, then
   choose a common template and approve it.
2. Post — follow the reserved creative through Studio AI composition and
   optional phone-image generation, edit its bounded template, Save/Approve
   checkpoints, and decide whether a proposed lesson becomes global.

The Project selector is present in both destinations. Every creative route
contains Project and creative IDs. Internal primitives, prompts, model controls,
provider secrets, and reasoning remain hidden. The browser never publishes,
schedules, creates campaigns, adds UTMs, runs analytics, or optimizes.

Run:

```sh
npm run check
npm run test:e2e
```

To inspect the local frontend against the production Owner Gateway, use a
Firebase App Check debug token that is registered for the PTW web app and keep
it only in the local environment:

```sh
VITE_PRODUCTION_BACKEND=true \
VITE_APPCHECK_DEBUG_TOKEN='<registered UUIDv4>' \
npm run dev -- --host localhost --port 5174 --strictPort
```

This mode proxies every `/api` request to production, so signed-in actions can
change live records and invoke real providers. The dev server refuses to start
without a validly shaped debug token and refuses to build this mode for
deployment. Do not add `localhost` to the production reCAPTCHA allowlist, commit
the token, or put it in a command-line argument.
