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
