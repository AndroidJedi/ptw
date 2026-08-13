# PTW Commander Bootstrap Addendum
## Purpose
This document complements the initial PTW idea artifact. The current goal is **not** to build the whole autonomous system, but to validate the architecture using one vertical: Instagram ad post generation.

## Phase 1 Scope
The entire knowledge evolution pipeline is built around one experiment:

Creative → Publish → Metrics → Analysis → Hypothesis → Knowledge Graph → Next Creative

Every entity receives a permanent ID.

## Telegram Control Plane
Commander is controlled exclusively through Telegram.

Capabilities:
- Receive tasks.
- Show current queue.
- Approve/reject autonomous actions.
- Show experiment status.
- Show current hypotheses.
- Request deployment.
- Display reasoning before important decisions.
- Emergency stop.

Telegram is the only human interface.

## Knowledge Graph
Everything becomes graph entities.

Core entities:
- Creative
- Hook
- Hero Image
- Supporting Visual
- Caption
- CTA
- Audience
- Experiment
- Metrics
- Insight
- Hypothesis
- Decision

Every node receives a stable UUID.

Relations include:
- created_from
- tested_in
- generated_result
- supports
- contradicts
- supersedes

Nothing is deleted.
Knowledge only evolves.

## Experiment Pipeline
Each Instagram creative is decomposed into reusable components:

Creative
 ├── Hook
 ├── Hero Image
 ├── Secondary Visual
 ├── Caption
 ├── CTA

Each component is independently tracked.

Example:
Hook H-014 may later be reused with Hero HIMG-009.

## Decision Evolution
Commander never stores only conclusions.

For every decision store:
- decision id
- reasoning
- evidence
- confidence
- source entities
- experiment ids
- successor decision (if revised)

Decisions become versioned.

## Learning Loop
1. Generate creatives.
2. Publish.
3. Collect metrics.
4. Detect statistically meaningful changes.
5. Produce insights.
6. Generate hypotheses.
7. Approve automatically only within configured policy.
8. Update graph.
9. Generate next experiments.

## Automation Policy
Configuration must define:
- auto approval limits
- daily budget
- max simultaneous experiments
- confidence thresholds
- rollback rules
- notification rules

Commander reads policy instead of hardcoded logic.

## Deliverables
The CLI implementation should first produce:
1. Graph schema.
2. ID strategy.
3. Storage model.
4. Telegram command interface.
5. Experiment lifecycle.
6. Policy configuration.
7. Audit log.
8. Minimal Instagram creative pipeline.

The system should be generic so later product development, UI, growth and research reuse the same mechanism.
