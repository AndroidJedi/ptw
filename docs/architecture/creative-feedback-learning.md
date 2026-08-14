# Creative feedback learning

Human feedback is a first-class signal, not a direct overwrite of knowledge.
After Commander sends a generated creative, the owner replies to that Telegram
image or text hook:

```text
/feedback 4 Strong hook, CTA needs work
```

Commander resolves the replied Telegram `(chat_id, message_id)` through
`commander_telegram_deliveries` to the permanent Creative UUID. The graph then
records:

```text
HumanFeedback UUID ──evaluates──> Creative UUID
Creative UUID ──contains────────> CreativeComponent UUID
WeightUpdate UUID ──derived_from─> HumanFeedback UUID
WeightUpdate UUID ──adjusts──────> CreativeComponent UUID
```

Every WeightUpdate stores previous weight, delta, new weight, rating, and
algorithm version. Nothing overwrites prior updates. Current weight is a
projection of the latest update; components begin at 0.50. Version 1 owner
ratings apply a bounded delta from -0.10 (rating 1) to +0.10 (rating 5).

Components with identical vertical, kind, and value are reused by ID, allowing
feedback to accumulate across creatives. `rank_creative_components` provides a
deterministic weight-first ordering for later generation workflows. Owner
feedback informs ranking but remains separate from platform metrics,
observations, insights, hypotheses, and decisions.

The explicit administrative form remains available:

```text
/feedback <creative-uuid> <1-5> optional comment
```

Duplicate feedback from the same actor for the same Creative UUID is rejected.

Text-only `/creative hook [brief]` results include the same reply instruction
as rendered images. Their Telegram text delivery is linked to the Creative UUID,
and each hook Creative contains a reusable hook component so the reply creates
an append-only WeightUpdate that can influence later component ranking.

Inspect learned state from Telegram with `/graph`, `/graph weights`, or
`/graph creative <creative-uuid>`. Reply-based feedback hides UUID management
from the owner, while graph inspection displays permanent IDs for auditability.
